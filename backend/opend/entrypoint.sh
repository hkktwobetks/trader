#!/bin/bash
set -e

cd /opt/opend/FutuOpenD

mkdir -p /opt/opend/FutuOpenD/Log
chmod 777 /opt/opend/FutuOpenD/Log

if [ "$#" -gt 0 ]; then
	exec ./OpenD "$@"
fi

args=()

if [ -n "${MOOMOO_LOGIN_ACCOUNT:-}" ]; then
	args+=("-login_account=${MOOMOO_LOGIN_ACCOUNT}")
fi

if [ -n "${MOOMOO_LOGIN_PASSWORD:-}" ]; then
	args+=("-login_pwd=${MOOMOO_LOGIN_PASSWORD}")
elif [ -n "${MOOMOO_LOGIN_PASSWORD_MD5:-}" ] && [[ "${MOOMOO_LOGIN_PASSWORD_MD5}" =~ ^[0-9a-fA-F]{32}$ ]]; then
	args+=("-login_pwd_md5=${MOOMOO_LOGIN_PASSWORD_MD5}")
fi

if [ -n "${MOOMOO_LOGIN_REGION:-}" ]; then
	args+=("-login_region=${MOOMOO_LOGIN_REGION}")
fi

args+=("-lang=${MOOMOO_LANG:-en}")
args+=("-log_level=${MOOMOO_LOG_LEVEL:-info}")
if [ "${MOOMOO_CONSOLE:-0}" = "1" ]; then
	args+=("-console=1")
fi
args+=("-api_port=${MOOMOO_API_PORT:-11111}")
args+=("-api_ip=${MOOMOO_API_IP:-0.0.0.0}")
args+=("-telnet_port=${MOOMOO_TELNET_PORT:-22222}")
args+=("-telnet_ip=${MOOMOO_TELNET_IP:-127.0.0.1}")

# Create a named pipe so we can send console commands at any time
FIFO=/tmp/opend_input
rm -f "$FIFO"
mkfifo "$FIFO"

# If a verify code is provided, schedule it to be sent after startup
if [ -n "${MOOMOO_PIC_VERIFY_CODE:-}" ]; then
	(sleep "${MOOMOO_PIC_VERIFY_DELAY:-5}" && echo "input_pic_verify_code -code=${MOOMOO_PIC_VERIFY_CODE}" > "$FIFO") &
fi

# Keep feeding the FIFO to OpenD stdin; tail -f keeps it open indefinitely
exec tail -f "$FIFO" | ./OpenD "${args[@]}"
