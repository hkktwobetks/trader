# Dockerfile
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# uv を入れる
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存解決（キャッシュ効かせるために先に requirements.txt だけコピー）
COPY requirements.txt .
RUN /root/.local/bin/uv pip install --system -r requirements.txt

# アプリ本体
COPY src ./src
COPY run_api.sh run_bot.sh ./
RUN mkdir -p /app/data
ENV PYTHONPATH=/app/src TZ=Asia/Tokyo

EXPOSE 8000
# 起動（compose で上書き可能）
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
