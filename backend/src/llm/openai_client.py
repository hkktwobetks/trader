import json
import logging
import re
from typing import Optional

from app.schemas import ExtractedSignal
from .base import LLM

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "あなたは株式トレード用の情報抽出器です。"
    "投稿から銘柄コード（US株ティッカーまたは日本株4桁コード）と売買方向（BUY/SELL）を読み取り、"
    "JSONのみ出力してください（説明不要、思考過程の出力禁止）。"
    '形式: {"ticker":"AAPL","side":"BUY","confidence":0.8,"timeframe":null,"entry":null,"stop":null,"take":null,"targets":[]}'
    "\n日本語の表現では『イン』『買い』『ロング』『ブレイクでイン』『反発狙い』は BUY 寄り、"
    "『売り』『ショート』『空売り』『利確売り』は SELL 寄りとして扱ってください。"
    "\n『エントリー』『指値』『〜でイン』『〜を超えたら』は entry に単一数値で設定。"
    "\n『ターゲット』『利確』『TP』が複数ある場合は targets に数値の配列で設定し、take には targets[0] を入れてください。"
    "例: ターゲット：3.93/4.15/4.63 → targets:[3.93,4.15,4.63], take:3.93"
    "\n『逆指値』『損切り』『SL』は stop に対応させてください。"
    "\nニュースや決算コメントのように売買意図が弱い場合は confidence を 0 にしてください。"
    "\nside は必ず BUY か SELL のどちらかにしてください。LONG/SHORT は使わないでください。"
)


def _extract_json_object(text: str) -> Optional[dict]:
    content = text.strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 3:
            content = parts[1].removeprefix("json").strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _normalize_side(value: str | None) -> str | None:
    if not value:
        return value
    side = value.strip().upper()
    mapping = {
        "LONG": "BUY",
        "SHORT": "SELL",
        "BUY": "BUY",
        "SELL": "SELL",
        "買い": "BUY",
        "売り": "SELL",
    }
    return mapping.get(side, side)


class OpenAILLM(LLM):
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        from openai import OpenAI
        resolved_api_key = api_key or (
            "ollama"
            if base_url and ("127.0.0.1" in base_url or "localhost" in base_url)
            else ""
        )
        client_kwargs = {"api_key": resolved_api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.base_url = base_url or ""

    def _prepare_user_text(self, text: str) -> str:
        # qwen3 on Ollama may emit reasoning by default; /no_think suppresses it.
        if "qwen3" in self.model.lower() and (
            "127.0.0.1" in self.base_url or "localhost" in self.base_url
        ):
            return f"/no_think\n{text}"
        return text

    def extract(self, text: str) -> Optional[ExtractedSignal]:
        try:
            rsp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._prepare_user_text(text)},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = rsp.choices[0].message.content.strip()
            data = _extract_json_object(content)
            if not data:
                log.warning("LLM extract produced non-JSON content: %r", content[:300])
                return None
            data["side"] = _normalize_side(data.get("side"))
            result = ExtractedSignal(**data)
            if not result.confidence or result.confidence < 0.1:
                return None
            return result
        except Exception as e:
            log.warning("LLM extract error: %s", e)
            return None
