import re
from .schemas import ExtractedSignal


# $AAPL のように $ 付きティッカーを優先マッチ
TICKER_PATTERN = re.compile(r"\$(?P<ticker>[A-Z]{1,6})")
SIDE_PATTERN = re.compile(r"\b(?P<side>BUY|LONG|SELL|SHORT)\b", re.I)
# フォールバック: $ なしでも BUY/SELL の近くにあるティッカーを拾う
FALLBACK_PATTERN = re.compile(r"(?P<ticker>\b[A-Z]{2,5}\b).*?(?P<side>BUY|LONG|SELL|SHORT)", re.I)


def naive_extract(text: str) -> ExtractedSignal | None:
    # 1. $TICKER を探す
    ticker_m = TICKER_PATTERN.search(text)
    side_m = SIDE_PATTERN.search(text)

    if ticker_m and side_m:
        ticker = ticker_m.group("ticker").upper()
        side_raw = side_m.group("side").upper()
        side = "BUY" if side_raw in {"BUY", "LONG"} else "SELL"
        return ExtractedSignal(ticker=ticker, side=side)

    # 2. フォールバック
    fb = FALLBACK_PATTERN.search(text)
    if fb:
        ticker = fb.group("ticker").upper()
        side_raw = fb.group("side").upper()
        side = "BUY" if side_raw in {"BUY", "LONG"} else "SELL"
        return ExtractedSignal(ticker=ticker, side=side)

    return None