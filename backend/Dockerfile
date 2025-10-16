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
ENV PYTHONPATH=/app/src TZ=Asia/Tokyo

EXPOSE 8000
# イメージは共通で作り、起動コマンドは compose 側で分ける
CMD ["bash","-lc","bash run_api.sh"]
