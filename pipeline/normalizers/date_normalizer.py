import logging
import re
from typing import Optional
import dateparser

logger = logging.getLogger(__name__)


def normalize_date(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    # Year-only: return YYYY-01
    if re.fullmatch(r'\d{4}', raw):
        return f"{raw}-01"

    try:
        parsed = dateparser.parse(
            raw,
            settings={
                "RETURN_TIME_AS_PERIOD": False,
                "PREFER_DAY_OF_MONTH": "first",
                "PREFER_DATES_FROM": "past",
            },
        )
        if parsed:
            return parsed.strftime("%Y-%m")
    except Exception as e:
        logger.warning(f"Date parse error for '{raw}': {e}")

    logger.warning(f"Could not normalize date: '{raw}'")
    return None
