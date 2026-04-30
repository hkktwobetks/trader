import base64
import datetime
import hashlib
import logging
import socket as _socket
from pathlib import Path
from typing import Iterable, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.db import init_db, get_session
from app.models import Execution, Order, PnL, Position, Signal
from app.config import settings
from app.schemas import SignalIn, ExtractedSignal
from app.utils import naive_extract
from app.risk import risk_guard
from app.state_sync import sync_executions, sync_orders, sync_positions, sync_pnl, sync_trading_state
from app.cookie_store import save_cookies, load_cookies, get_version
from llm.base import LLM
from broker import get_broker, reset_broker_cache
from sqlmodel import select

logger = logging.getLogger("api")

# Runtime overrides — take precedence over env-var defaults from settings
_rt: dict[str, object] = {}

# Worker heartbeat timestamps (UTC)
_worker_last_seen: dict[str, datetime.datetime] = {}


def _get(key: str) -> object:
    return _rt.get(key, getattr(settings, key))


app = FastAPI(title="Discord-LLM-Trader")


@app.on_event("startup")
def on_startup():
    init_db()
    logger.setLevel(logging.INFO)


llm_client: LLM | None = None
if settings.llm_provider == "ollama":
    try:
        from llm.ollama_client import OllamaLLM  # type: ignore

        base_url = settings.openai_api_base or "http://127.0.0.1:11434/v1"
        model = settings.openai_model or "qwen3:14b"

        llm_client = OllamaLLM(model, base_url)
        logger.info("LLM initialised: provider=%s model=%s base_url=%s", settings.llm_provider, model, base_url)
    except Exception as e:  # pragma: no cover - logging/optional dependency
        logger.warning("Ollama LLM initialisation failed: %s", e)
elif settings.llm_provider in {"openai", "local_openai"}:
    try:
        from llm.openai_client import OpenAILLM  # type: ignore

        base_url = settings.openai_api_base or None
        api_key = settings.openai_api_key
        model = settings.openai_model

        if settings.llm_provider == "local_openai":
            base_url = base_url or "http://127.0.0.1:11434/v1"
            api_key = api_key or "ollama"
            model = model or "qwen3:14b"

        llm_client = OpenAILLM(
            model,
            api_key,
            base_url,
        )
        logger.info("LLM initialised: provider=%s model=%s base_url=%s", settings.llm_provider, model, base_url or "default")
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


def ensure_float(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
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


def resolve_signal_policy(source: str, meta: dict) -> tuple[str, bool]:
    requested_env = str(meta.get("broker_env") or meta.get("target_env") or "").strip().upper()
    if requested_env in {"SIMULATE", "REAL"}:
        broker_env = requested_env
    elif source == "twitter":
        broker_env = str(_get("twitter_broker_env")).upper()
    elif source == "dexter":
        broker_env = str(_get("dexter_broker_env")).upper()
    else:
        broker_env = str(_get("broker_env")).upper()

    if source == "twitter":
        auto_trade_enabled = bool(_get("twitter_auto_trade_enabled"))
    elif source == "dexter":
        auto_trade_enabled = bool(_get("dexter_auto_trade_enabled"))
    else:
        auto_trade_enabled = bool(_get("auto_trade_enabled"))

    return broker_env, auto_trade_enabled


@app.get("/health")
def health():
    return {"ok": True}


# ── Trading Settings ────────────────────────────────

class TradingSettingsOut(BaseModel):
    broker: str
    broker_env: str
    twitter_broker_env: str
    dexter_broker_env: str
    auto_trade_enabled: bool
    twitter_polling_enabled: bool
    twitter_auto_trade_enabled: bool
    dexter_auto_trade_enabled: bool


class TradingSettingsPatch(BaseModel):
    broker_env: str | None = None
    twitter_broker_env: str | None = None
    dexter_broker_env: str | None = None
    auto_trade_enabled: bool | None = None
    twitter_polling_enabled: bool | None = None
    twitter_auto_trade_enabled: bool | None = None
    dexter_auto_trade_enabled: bool | None = None


def _build_trading_settings() -> TradingSettingsOut:
    return TradingSettingsOut(
        broker=str(_get("broker")),
        broker_env=str(_get("broker_env")).upper(),
        twitter_broker_env=str(_get("twitter_broker_env")).upper(),
        dexter_broker_env=str(_get("dexter_broker_env")).upper(),
        auto_trade_enabled=bool(_get("auto_trade_enabled")),
        twitter_polling_enabled=bool(_get("twitter_polling_enabled")),
        twitter_auto_trade_enabled=bool(_get("twitter_auto_trade_enabled")),
        dexter_auto_trade_enabled=bool(_get("dexter_auto_trade_enabled")),
    )


@app.get("/settings/trading", response_model=TradingSettingsOut)
def get_trading_settings():
    return _build_trading_settings()


@app.patch("/settings/trading", response_model=TradingSettingsOut)
def patch_trading_settings(payload: TradingSettingsPatch):
    for env_key in ("broker_env", "twitter_broker_env", "dexter_broker_env"):
        val = getattr(payload, env_key)
        if val is not None:
            v = val.upper()
            if v not in {"SIMULATE", "REAL"}:
                raise HTTPException(status_code=422, detail=f"{env_key} must be SIMULATE or REAL")
            _rt[env_key] = v
            reset_broker_cache()
    for bool_key in ("auto_trade_enabled", "twitter_polling_enabled", "twitter_auto_trade_enabled", "dexter_auto_trade_enabled"):
        val = getattr(payload, bool_key)
        if val is not None:
            _rt[bool_key] = val
    return _build_trading_settings()


# ── OpenD Management ───────────────────────────────

_OPEND_HOME = Path("/mnt/opend_home")
_OPEND_TELNET_HOST = "127.0.0.1"


def _opend_telnet_port() -> int:
    import os
    return int(os.getenv("MOOMOO_TELNET_PORT", "22222"))


def _opend_api_port() -> int:
    return settings.moomoo_opend_port


def _find_captcha_image() -> Path | None:
    if not _OPEND_HOME.exists():
        return None
    for png in _OPEND_HOME.glob("*/PicVerifyCode.png"):
        return png
    return None


@app.get("/opend/status")
def opend_status():
    from broker import _is_host_reachable
    connected = _is_host_reachable(_OPEND_TELNET_HOST, _opend_api_port(), timeout=1.0)
    captcha = _find_captcha_image()
    return {
        "connected": connected,
        "captcha_pending": captcha is not None,
        "captcha_path": str(captcha) if captcha else None,
    }


@app.get("/opend/captcha-image")
def opend_captcha_image():
    captcha = _find_captcha_image()
    if captcha is None:
        raise HTTPException(status_code=404, detail="キャプチャ画像が見つかりません")
    data = base64.b64encode(captcha.read_bytes()).decode()
    return {"image": f"data:image/png;base64,{data}"}


class CaptchaSubmit(BaseModel):
    code: str


@app.post("/opend/submit-captcha")
def opend_submit_captcha(payload: CaptchaSubmit):
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="code is required")
    port = _opend_telnet_port()
    try:
        with _socket.create_connection((_OPEND_TELNET_HOST, port), timeout=5) as sock:
            sock.sendall(f"input_pic_verify_code -code={code}\n".encode())
            import time as _time
            _time.sleep(0.8)
            response = sock.recv(4096).decode(errors="replace").strip()
        return {"ok": True, "response": response}
    except OSError as e:
        raise HTTPException(status_code=503, detail=f"OpenD telnet ({port}) に接続できません: {e}")


# ── Worker Status ──────────────────────────────────

@app.post("/workers/twitter/heartbeat")
def twitter_heartbeat():
    _worker_last_seen["twitter"] = datetime.datetime.utcnow()
    return {"enabled": bool(_get("twitter_polling_enabled"))}


@app.get("/workers/status")
def workers_status():
    now = datetime.datetime.utcnow()

    def _entry(name: str, enabled_key: str) -> dict:
        ts = _worker_last_seen.get(name)
        seconds_ago = int((now - ts).total_seconds()) if ts else None
        return {
            "last_seen": ts.isoformat() if ts else None,
            "seconds_ago": seconds_ago,
            "alive": seconds_ago is not None and seconds_ago < 90,
            "enabled": bool(_get(enabled_key)),
        }

    return {
        "twitter": _entry("twitter", "twitter_polling_enabled"),
    }


# ── Dexter ─────────────────────────────────────────

class DexterQueryIn(BaseModel):
    query: str


@app.post("/dexter/query")
def dexter_query(payload: DexterQueryIn):
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="query is empty")
    try:
        from app.dexter_bridge import get_dexter_dir_from_env, run_dexter_once
        dexter_dir = get_dexter_dir_from_env()
        answer = run_dexter_once(dexter_dir, payload.query.strip())
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    return {"status": "saved", "valid": True, "error": None, "version": get_version()}


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
def list_orders(broker_env: str | None = Query(default=None)):
    with get_session() as s:
        rows = sync_orders(s)
        if broker_env:
            env = broker_env.upper()
            rows = [r for r in rows if r.broker_env == env]
        return jsonable_encoder(rows)


@app.get("/positions")
def list_positions(broker_env: str | None = Query(default=None)):
    env = (broker_env or str(_get("broker_env"))).upper()
    with get_session() as s:
        rows = sync_positions(s, broker_env=env)
        return jsonable_encoder(rows)


@app.get("/executions")
def list_executions(broker_env: str | None = Query(default=None)):
    env = (broker_env or str(_get("broker_env"))).upper()
    with get_session() as s:
        sync_orders(s)
        sync_executions(s)
        sync_pnl(s, broker_env=env)
        rows = s.exec(
            select(Execution)
            .where(Execution.broker_env == env)
            .order_by(Execution.executed_at.desc())
        ).all()
        return jsonable_encoder(rows)


@app.get("/pnl")
def list_pnl(broker_env: str | None = Query(default=None)):
    env = (broker_env or str(_get("broker_env"))).upper()
    with get_session() as s:
        sync_trading_state(s, broker_env=env)
        rows = s.exec(select(PnL).where(PnL.broker_env == env).order_by(PnL.date.asc())).all()
        return jsonable_encoder(rows)


@app.post("/sync")
def sync_state():
    with get_session() as s:
        synced = sync_trading_state(s)
        return {
            "orders": jsonable_encoder(synced["orders"]),
            "executions": jsonable_encoder(synced["executions"]),
            "positions": jsonable_encoder(synced["positions"]),
            "pnls": jsonable_encoder(synced["pnls"]),
        }


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

    broker_env, source_auto_trade_enabled = resolve_signal_policy(payload.source, payload.meta)

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
        "signal stored id=%s source=%s ticker=%s side=%s broker_env=%s auto_trade=%s meta=%s parsed=%s",
        signal.id,
        payload.source,
        parsed.ticker,
        parsed.side,
        broker_env,
        source_auto_trade_enabled,
        payload.meta,
        parsed.model_dump(),
    )

    # 自動注文実行（信頼度閾値を超えた場合のみ）
    order_result = None
    
    if source_auto_trade_enabled and parsed.confidence is not None and parsed.confidence >= settings.min_confidence:
        try:
            broker = get_broker(broker_env=broker_env)

            requested_qty = ensure_float(payload.meta.get("qty"))
            order_type = str(payload.meta.get("order_type") or "MARKET").upper()
            limit_price = ensure_float(payload.meta.get("limit_price") or payload.meta.get("price"))
            tif = str(payload.meta.get("tif") or "DAY").upper()

            # 注文数量を計算（default_order_usd / price、価格がなければ1株）
            qty = requested_qty if requested_qty and requested_qty > 0 else 1.0
            quote_last_price = getattr(broker, "quote_last_price", None)
            if requested_qty is None and callable(quote_last_price):
                try:
                    last_price = float(quote_last_price(parsed.ticker))
                    if last_price > 0:
                        qty = max(settings.default_order_usd / last_price, 1.0)
                        logger.info(
                            "calculated order qty from live quote ticker=%s last_price=%s qty=%s",
                            parsed.ticker,
                            last_price,
                            qty,
                        )
                except Exception as quote_exc:
                    logger.warning("failed to fetch live quote for %s: %s", parsed.ticker, quote_exc)

            # リスクチェック
            if not risk_guard.can_open(parsed.ticker, qty if parsed.side == "BUY" else -qty):
                logger.warning("risk check failed for %s, skipping order", parsed.ticker)
            else:
                order_result = broker.place_order(
                    ticker=parsed.ticker,
                    side=parsed.side,
                    qty=qty,
                    price=limit_price,
                    order_type=order_type,
                    tif=tif,
                )
                
                # 注文をDBに保存
                with get_session() as s:
                    order = Order(
                        broker=broker.name,
                        broker_env=broker_env,
                        order_id=order_result.get("order_id"),
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
                    "auto order placed signal_id=%s ticker=%s side=%s broker_env=%s status=%s",
                    signal.id,
                    parsed.ticker,
                    parsed.side,
                    broker_env,
                    order_result.get("status"),
                )
        except Exception as e:
            reset_broker_cache()
            logger.error("auto order failed for signal_id=%s: %s", signal.id, e)

    return {
        "signal": signal,
        "broker_env": broker_env,
        "auto_trade_enabled": source_auto_trade_enabled,
        "order": order_result,
    }
