import logging
from typing import Optional
import phonenumbers
from phonenumbers import NumberParseException

logger = logging.getLogger(__name__)


def normalize_phone(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    for region in ("IN", "US"):
        try:
            parsed = phonenumbers.parse(raw, region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            continue
        except Exception as e:
            logger.warning(f"Phone parse error for '{raw}': {e}")
            continue

    logger.warning(f"Could not normalize phone: '{raw}'")
    return None
