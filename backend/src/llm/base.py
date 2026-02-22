from abc import ABC, abstractmethod
from typing import Optional
from app.schemas import ExtractedSignal

class LLM(ABC):
    @abstractmethod
    def extract(self, text: str) -> Optional[ExtractedSignal]:
        """Return structured trading signal or None."""
        raise NotImplementedError
