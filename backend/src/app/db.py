from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine, Session
from .config import settings


def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        return create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 10},
        )
    return create_engine(url, echo=False, pool_pre_ping=True)


engine = _make_engine()


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    return Session(engine)
