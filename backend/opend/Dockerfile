# ビルドコンテキストはリポジトリルート（docker-compose で指定）
# 展開済みの OpenD ディレクトリを backend/opend/ に置く
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    libfuse2 \
    ca-certificates \
    locales \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8

ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

WORKDIR /opt/opend

COPY backend/opend/moomoo_OpenD_10.4.6408_Ubuntu18.04/moomoo_OpenD_10.4.6408_Ubuntu18.04 /opt/opend/FutuOpenD
COPY backend/opend/entrypoint.sh /opt/opend/entrypoint.sh

RUN chmod +x FutuOpenD/OpenD \
    && chmod +x FutuOpenD/WebSocket \
    && chmod +x FutuOpenD/Update \
    && chmod +x /opt/opend/entrypoint.sh

WORKDIR /opt/opend/FutuOpenD

EXPOSE 11111 22222

ENTRYPOINT ["/opt/opend/entrypoint.sh"]
