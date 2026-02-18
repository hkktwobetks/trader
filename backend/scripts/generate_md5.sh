#!/usr/bin/env bash
set -Eeuo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <password>" >&2
  exit 1
fi

python3 - "$1" <<'PY'
import hashlib
import sys
password = sys.argv[1]
print(hashlib.md5(password.encode('utf-8')).hexdigest())
PY
