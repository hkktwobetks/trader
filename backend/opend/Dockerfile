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

COPY moomoo_OpenD_9.6.5618_Ubuntu18.04.tar.gz /opt/opend/
COPY entrypoint.sh /opt/opend/entrypoint.sh

RUN tar -xzf moomoo_OpenD_9.6.5618_Ubuntu18.04.tar.gz \
    && rm moomoo_OpenD_9.6.5618_Ubuntu18.04.tar.gz \
    && mv moomoo_OpenD_9.6.5618_Ubuntu18.04/moomoo_OpenD_9.6.5618_Ubuntu18.04 FutuOpenD \
    && rm -rf moomoo_OpenD_9.6.5618_Ubuntu18.04 \
    && chmod +x FutuOpenD/OpenD \
    && chmod +x /opt/opend/entrypoint.sh

WORKDIR /opt/opend/FutuOpenD

EXPOSE 11111 22222

ENTRYPOINT ["/opt/opend/entrypoint.sh"]
