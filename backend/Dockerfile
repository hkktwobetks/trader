# Dockerfile — 依存関係は pyproject.toml + uv.lock（ローカルは `uv sync`）
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates unzip && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    curl -fsSL https://bun.com/install | bash && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.bun/bin:/root/.local/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-group dev --no-install-project

COPY src ./src
COPY run_api.sh run_bot.sh ./
RUN mkdir -p /app/data
RUN uv sync --frozen --no-group dev

ENV PYTHONPATH=/app/src \
    TZ=Asia/Tokyo \
    PATH="/app/.venv/bin:/root/.local/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
