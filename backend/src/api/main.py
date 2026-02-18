import hashlib
import logging
from pathlib import Path
from typing import Iterable, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.db import init_db, get_session
from app.models import Order, Position, Signal
from app.config import settings
from app.schemas import SignalIn, ExtractedSignal
from app.utils import naive_extract
from app.risk import risk_guard
from app.cookie_store import save_cookies, load_cookies, get_version
from llm.base import LLM
from broker import get_broker
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

        llm_client = OpenAILLM(
            settings.openai_model,
            settings.openai_api_key,
            settings.openai_api_base or None,
        )
        logger.info("OpenAI LLM initialised: %s (base_url=%s)", settings.openai_model, settings.openai_api_base or "default")
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


# ── Twitter Cookie 管理 ─────────────────────────────

class CookieIn(BaseModel):
    auth_token: str
    ct0: str


@app.post("/settings/twitter-cookies")
def set_twitter_cookies(payload: CookieIn):
    """Cookie を受け取り保存。簡易テストも行う"""
    if len(payload.auth_token) < 20 or len(payload.ct0) < 20:
        raise HTTPException(status_code=422, detail="Cookie の値が短すぎます")

    save_cookies(payload.auth_token, payload.ct0)

    # 簡易テスト: Scraper を作ってユーザー情報取得
    ok = False
    error = None
    try:
        from twitter.scraper import Scraper
        s = Scraper(cookies={"auth_token": payload.auth_token, "ct0": payload.ct0})
        info = s.users(["Twitter"])  # 公開アカウントで疎通確認
        if info and info[0].get("data", {}).get("user"):
            ok = True
    except Exception as e:
        error = str(e)

    return {"status": "saved", "valid": ok, "error": error, "version": get_version()}


@app.get("/settings/twitter-cookies")
def get_twitter_cookie_status():
    """現在の Cookie ステータスを返す"""
    auth_token, ct0 = load_cookies()
    has_cookies = bool(auth_token and ct0)
    return {
        "has_cookies": has_cookies,
        "version": get_version(),
        "auth_token_preview": auth_token[:8] + "..." if auth_token else None,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Cookie 入力 + ステータス表示のダッシュボード"""
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


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

    # 自動注文実行（信頼度閾値を超えた場合のみ）
    order_result = None
    
    if settings.auto_trade_enabled and parsed.confidence is not None and parsed.confidence >= settings.min_confidence:
        try:
            # 注文数量を計算（default_order_usd / price、価格がなければ1株）
            qty = 1.0  # デフォルト1株
            
            # リスクチェック
            if not risk_guard.can_open(parsed.ticker, qty if parsed.side == "BUY" else -qty):
                logger.warning("risk check failed for %s, skipping order", parsed.ticker)
            else:
                broker = get_broker()
                order_result = broker.place_order(
                    ticker=parsed.ticker,
                    side=parsed.side,
                    qty=qty,
                    price=None,  # 成行注文
                    order_type="MARKET",
                    tif="DAY",
                )
                
                # 注文をDBに保存
                with get_session() as s:
                    order = Order(
                        broker=broker.name,
                        ticker=parsed.ticker,
                        side=parsed.side,
                        qty=qty,
                        price=order_result.get("price"),
                        status=order_result.get("status", "NEW"),
                        reason=order_result.get("reason"),
                        signal_id=signal.id,
                    )
                    s.add(order)
                    s.commit()
                
                logger.info(
                    "auto order placed signal_id=%s ticker=%s side=%s status=%s",
                    signal.id,
                    parsed.ticker,
                    parsed.side,
                    order_result.get("status"),
                )
        except Exception as e:
            logger.error("auto order failed for signal_id=%s: %s", signal.id, e)

    return {"signal": signal, "order": order_result}
