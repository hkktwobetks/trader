from fastapi import FastAPI
from app.db import init_db, get_session
from app.models import Order, Position, Signal
from sqlmodel import select


app = FastAPI(title="Discord-LLM-Trader")


@app.on_event("startup")
def on_startup():
    init_db()


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