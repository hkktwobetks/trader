import json
import logging
from typing import Optional

import requests

from app.schemas import ExtractedSignal
from .base import LLM

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "あなたは株式トレード用の情報抽出器です。"
    "投稿から銘柄コード（US株ティッカーまたは日本株4桁コード）と売買方向（BUY/SELL）を読み取り、"
    "JSONのみ出力してください（説明不要、思考過程の出力禁止）。"
    '形式: {"ticker":"AAPL","side":"BUY","confidence":0.8,"timeframe":null,"stop":null,"take":null}'
    "\n日本語の表現では『イン』『買い』『ロング』『ブレイクでイン』『反発狙い』は BUY 寄り、"
    "『売り』『ショート』『空売り』『利確売り』は SELL 寄りとして扱ってください。"
    "\n『ターゲット』『利確』『TP』は take、『逆指値』『損切り』『SL』は stop に対応させてください。"
    "\nニュースや決算コメントのように売買意図が弱い場合は confidence を 0 にしてください。"
    "\nside は必ず BUY か SELL のどちらかにしてください。LONG/SHORT は使わないでください。"
)


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


class OllamaLLM(LLM):
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = (base_url or "http://127.0.0.1:11434/v1").rstrip("/")
        self.generate_url = self.base_url.removesuffix("/v1") + "/api/generate"

    def extract(self, text: str) -> Optional[ExtractedSignal]:
        prompt = f"{SYSTEM_PROMPT}\n\n投稿本文:\n{text}\n"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": 0,
                "num_predict": 96,
            },
        }
        try:
            rsp = requests.post(self.generate_url, json=payload, timeout=240)
            rsp.raise_for_status()
            data = rsp.json()
            response_text = (data.get("response") or "").strip()
            if not response_text:
                log.warning("Ollama returned empty response")
                return None
            parsed = json.loads(response_text)
            parsed["side"] = _normalize_side(parsed.get("side"))
            result = ExtractedSignal(**parsed)
            if not result.confidence or result.confidence < 0.1:
                return None
            return result
        except Exception as e:
            log.warning("Ollama extract error: %s", e)
            return None
