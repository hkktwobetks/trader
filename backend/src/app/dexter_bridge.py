from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent

import httpx

# __DEXTER_DIR__ は run_dexter_once 内で実際のパスに置換される
DEXTER_RUNNER_TS = """\
import { config } from 'dotenv';
import { Agent } from '__DEXTER_DIR__/src/agent/index.ts';

config({ quiet: true });

const query = process.argv[2];
if (!query) {
  console.error('query is required');
  process.exit(2);
}

const model = process.env.DEXTER_MODEL || undefined;
const agent = await Agent.create({ maxIterations: 3, ...(model ? { model } : {}) });
let answer = '';
for await (const event of agent.run(query)) {
  if (event.type === 'done') {
    answer = event.answer;
  }
}
console.log(JSON.stringify({ answer }));
"""

DEXTER_SIGNAL_SUFFIX = dedent(
    """
    Return either:
    1. A single trade idea in this exact format on the first line: $TICKER BUY
       or: $TICKER SELL
    2. Then one short reason on the second line.
    3. If you do not have a clear trade, output exactly: NO_SIGNAL
    Do not include markdown fences, bullet points, or extra commentary.
    """
).strip()


def build_dexter_query(base_query: str) -> str:
    return f"{base_query.strip()}\n\n{DEXTER_SIGNAL_SUFFIX}"


def get_dexter_dir_from_env() -> Path:
    dexter_dir = os.getenv("DEXTER_DIR", "").strip()
    if not dexter_dir:
        raise RuntimeError("DEXTER_DIR is not set.")
    path = Path(dexter_dir).expanduser()
    if not path.is_dir():
        raise RuntimeError(f"Dexter directory not found: {path}")
    return path


def run_dexter_once(dexter_dir: Path, query: str) -> str:
    if shutil.which("bun") is None:
        raise RuntimeError("bun is not installed. Install Bun before running Dexter.")

    runner_content = DEXTER_RUNNER_TS.replace("__DEXTER_DIR__", str(dexter_dir))

    # dexter_dir が :ro マウントでも動くよう /tmp に書く
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ts", delete=False, encoding="utf-8"
    ) as f:
        f.write(runner_content)
        runner_path = Path(f.name)

    try:
        proc = subprocess.run(
            ["bun", "run", str(runner_path), query],
            cwd=dexter_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=1500,
        )
    finally:
        runner_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Dexter execution failed")

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("Dexter returned no output")
    payload = json.loads(lines[-1])
    answer = str(payload.get("answer", "")).strip()
    if not answer:
        raise RuntimeError("Dexter returned an empty answer")
    return answer


def post_dexter_signal(api_base_url: str, text: str, broker_env: str, original_query: str, origin: str) -> str:
    payload = {
        "text": text,
        "source": "dexter",
        "meta": {
            "broker_env": broker_env,
            "origin": origin,
            "query": original_query,
        },
    }
    response = httpx.post(f"{api_base_url.rstrip('/')}/signals", json=payload, timeout=20)
    response.raise_for_status()
    return response.text
