from abc import ABC, abstractmethod
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from schemas.raw_record import RawRecord


class BaseExtractor(ABC):
    """
    Strategy Pattern base class.
    Every extractor MUST return a list of RawRecord objects.
    On any error (missing file, API failure, malformed data),
    log the error and return an empty list. NEVER raise to caller.
    """
    SOURCE_TYPE: str = "UNKNOWN"
    RELIABILITY_WEIGHT: float = 0.5

    @abstractmethod
    def extract(self, source: str) -> list[RawRecord]:
        """
        source: file path, URL, username, or raw text
        returns: list of RawRecord (empty list on failure)
        """
        pass

    def _make_source_id(self, suffix: str) -> str:
        return f"src_{self.SOURCE_TYPE.lower()}_{suffix}"
