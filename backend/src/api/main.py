import hashlib
import logging
from typing import Iterable, List

from fastapi import FastAPI, HTTPException
from app.db import init_db, get_session
from app.models import Order, Position, Signal
from app.config import settings
from app.schemas import SignalIn, ExtractedSignal
from app.utils import naive_extract
from llm.base import LLM
from sqlmodel import select

logger = logging.getLogger("api")


app = FastAPI(title="Discord-LLM-Trader")


@app.on_event("startup")
def on_startup():
    init_db()
    logger.setLevel(logging.INFO)


llm_client: LLM | None = None
if settings.llm_provider == "openai" and settings.openai_api_key:
    try:
        from llm.openai_client import OpenAILLM  # type: ignore

        llm_client = OpenAILLM(settings.openai_model, settings.openai_api_key)
        logger.info("OpenAI LLM initialised: %s", settings.openai_model)
    except Exception as e:  # pragma: no cover - logging/optional dependency
        logger.warning("OpenAI LLM initialisation failed: %s", e)


def extract_signal(text: str) -> ExtractedSignal | None:
    if llm_client:
        try:
            result = llm_client.extract(text)
            if result:
                return result
        except Exception as e:  # pragma: no cover - defensive logging
            logger.warning("LLM extraction failed: %s", e)
    return naive_extract(text)


def ensure_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def has_duplicate(session, keys: Iterable[str], url: str | None) -> bool:
    for key in keys:
        if not key:
            continue
        existing = session.exec(select(Signal.id).where(Signal.message_id == key)).first()
        if existing:
            logger.info("duplicate signal detected via key=%s", key)
            return True
    if url:
        existing = session.exec(select(Signal.id).where(Signal.content.contains(url))).first()
        if existing:
            logger.info("duplicate signal detected via url=%s", url)
            return True
    return False


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/orders")
def list_orders():
    with get_session() as s:
        rows = s.exec(select(Order).order_by(Order.created_at.desc())).all()
        return rows


@app.get("/positions")
def list_positions():
    with get_session() as s:
        rows = s.exec(select(Position)).all()
        return rows


@app.get("/signals")
def list_signals():
    with get_session() as s:
        rows = s.exec(select(Signal).order_by(Signal.created_at.desc()).limit(100)).all()
        return rows


@app.post("/signals")
def receive_signal(payload: SignalIn):
    parsed = extract_signal(payload.text)
    if not parsed:
        logger.warning(
            "signal extraction failed source=%s meta=%s", payload.source, payload.meta
        )
        raise HTTPException(status_code=422, detail="Failed to extract signal from text")

    url = payload.meta.get("url")
    message_id_candidates: List[str] = []
    for key in (payload.meta.get("message_id"), payload.meta.get("id"), url):
        if key:
            message_id_candidates.append(str(key))

    message_id = message_id_candidates[0] if message_id_candidates else None
    if not message_id:
        message_id = f"{payload.source}:{hashlib.sha256(payload.text.encode('utf-8')).hexdigest()}"

    author = (
        payload.meta.get("username")
        or payload.meta.get("author")
        or payload.meta.get("user")
        or payload.source
    )
    channel_id = ensure_int(
        payload.meta.get("channel_id")
        or payload.meta.get("chat_id")
        or payload.meta.get("user_id")
    )

    content = payload.text
    if url and url not in content:
        content = f"{content}\n\nSource: {url}"

    with get_session() as s:
        if has_duplicate(s, [message_id, *message_id_candidates[1:]], url):
            logger.info(
                "duplicate signal skipped source=%s message_id=%s meta=%s",
                payload.source,
                message_id,
                payload.meta,
            )
            return {"status": "duplicate"}

        signal = Signal(
            message_id=message_id,
            author=str(author),
            channel_id=channel_id,
            content=content,
            ticker=parsed.ticker,
            side=parsed.side,
            confidence=parsed.confidence,
            timeframe=parsed.timeframe,
            stop=parsed.stop,
            take=parsed.take,
        )
        s.add(signal)
        s.commit()
        s.refresh(signal)

    logger.info(
        "signal stored id=%s source=%s ticker=%s side=%s meta=%s parsed=%s",
        signal.id,
        payload.source,
        parsed.ticker,
        parsed.side,
        payload.meta,
        parsed.model_dump(),
    )
    return signal
