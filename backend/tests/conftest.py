import os

# Use in-memory SQLite so tests don't touch the real DB
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
