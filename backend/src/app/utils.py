import re
from .schemas import ExtractedSignal


PATTERN = re.compile(r"(?P<ticker>\$?[A-Z]{1,6}).*(?P<side>BUY|LONG|SELL|SHORT)", re.I)


def naive_extract(text: str) -> ExtractedSignal | None:
    m = PATTERN.search(text)
    if not m:
        return None
    ticker = m.group("ticker").lstrip("$").upper()
    side_raw = m.group("side").upper()
    side = "BUY" if side_raw in {"BUY", "LONG"} else "SELL"
    return ExtractedSignal(ticker=ticker, side=side)