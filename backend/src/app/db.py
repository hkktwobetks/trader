from sqlalchemy import event, inspect, text
from sqlmodel import SQLModel, create_engine, Session
from .config import settings


engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 10},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")   # readers never block writers
    cur.execute("PRAGMA busy_timeout=5000")  # wait up to 5s instead of immediate error
    cur.close()


def init_db():
    SQLModel.metadata.create_all(engine)
    _migrate_orders_table()
    _migrate_env_columns()


def get_session():
    return Session(engine)


def _migrate_env_columns() -> None:
    """Add broker_env to execution, position, pnl tables if missing."""
    inspector = inspect(engine)
    ddl: list[str] = []
    for table, col, default in [
        ("execution", "broker_env", "SIMULATE"),
        ("position", "broker_env", "SIMULATE"),
        ("position", "acc_type", "MARGIN"),
        ("pnl", "broker_env", "SIMULATE"),
    ]:
        try:
            cols = {c["name"] for c in inspector.get_columns(table)}
        except Exception:
            continue
        if col not in cols:
            ddl.append(f"ALTER TABLE \"{table}\" ADD COLUMN {col} VARCHAR DEFAULT '{default}'")
    if ddl:
        with engine.begin() as conn:
            for stmt in ddl:
                conn.execute(text(stmt))


def _migrate_orders_table() -> None:
    inspector = inspect(engine)
    try:
        columns = {col["name"] for col in inspector.get_columns("order")}
    except Exception:
        return

    ddl_statements: list[str] = []
    if "broker_env" not in columns:
        ddl_statements.append("ALTER TABLE \"order\" ADD COLUMN broker_env VARCHAR DEFAULT 'SIMULATE'")
    if "order_id" not in columns:
        ddl_statements.append("ALTER TABLE \"order\" ADD COLUMN order_id VARCHAR")

    if not ddl_statements:
        return

    with engine.begin() as conn:
        for ddl in ddl_statements:
            conn.execute(text(ddl))
