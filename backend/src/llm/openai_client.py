from typing import Optional
import json
from app.schemas import ExtractedSignal
from .base import LLM

PROMPT = """
あなたは株式トレード用の情報抽出器です。以下の投稿から、銘柄コード（US株ティッカー）、売買方向（BUY/SELL）、信頼度0-1、timeframe（任意）、stop（任意, 数値）、take（任意, 数値）をJSONで返してください。
出力のみ：{"ticker":"", "side":"BUY|SELL", "confidence":0.0, "timeframe":"", "stop":null, "take":null}
投稿: <<<{text}>>>
"""

class OpenAILLM(LLM):
    def __init__(self, model: str, api_key: str):
        # importをここに置くと、OpenAI未インストールでも他の実装で進められる
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def extract(self, text: str) -> Optional[ExtractedSignal]:
        try:
            rsp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": PROMPT.format(text=text)}],
                temperature=0,
            )
            content = rsp.choices[0].message.content.strip()
            data = json.loads(content)
            return ExtractedSignal(**data)
        except Exception:
            # 失敗時は None（上位で naive_extract にフォールバック可能）
            return None
