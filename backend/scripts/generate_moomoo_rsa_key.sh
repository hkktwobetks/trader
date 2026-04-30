#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KEY_DIR="${ROOT_DIR}/opend_keys"
KEY_PATH="${KEY_DIR}/conn_key.pem"

mkdir -p "$KEY_DIR"

if [ -f "$KEY_PATH" ]; then
  echo "Key already exists: $KEY_PATH" >&2
  exit 1
fi

openssl genrsa -traditional -out "$KEY_PATH" 1024
chmod 600 "$KEY_PATH"
echo "Created: $KEY_PATH"
