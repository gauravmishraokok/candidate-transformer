import logging
from typing import Optional

logger = logging.getLogger(__name__)

COUNTRY_LOOKUP: dict[str, str] = {
    "india": "IN",
    "indian": "IN",
    "bangalore": "IN",
    "bengaluru": "IN",
    "mumbai": "IN",
    "delhi": "IN",
    "new delhi": "IN",
    "hyderabad": "IN",
    "chennai": "IN",
    "pune": "IN",
    "kolkata": "IN",
    "ahmedabad": "IN",
    "jaipur": "IN",
    "surat": "IN",
    "lucknow": "IN",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "america": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "germany": "DE",
    "deutschland": "DE",
    "france": "FR",
    "canada": "CA",
    "australia": "AU",
    "singapore": "SG",
    "japan": "JP",
    "china": "CN",
    "brazil": "BR",
    "brasil": "BR",
    "netherlands": "NL",
    "holland": "NL",
    "sweden": "SE",
    "switzerland": "CH",
    "uae": "AE",
    "united arab emirates": "AE",
    "dubai": "AE",
    "abu dhabi": "AE",
    "russia": "RU",
    "spain": "ES",
    "italy": "IT",
    "mexico": "MX",
    "south korea": "KR",
    "korea": "KR",
    "indonesia": "ID",
    "pakistan": "PK",
    "bangladesh": "BD",
    "nigeria": "NG",
    "south africa": "ZA",
    "turkey": "TR",
    "türkiye": "TR",
    "argentina": "AR",
    "colombia": "CO",
    "chile": "CL",
    "poland": "PL",
    "ukraine": "UA",
    "portugal": "PT",
    "denmark": "DK",
    "finland": "FI",
    "norway": "NO",
    "austria": "AT",
    "belgium": "BE",
    "israel": "IL",
    "new zealand": "NZ",
    "malaysia": "MY",
    "thailand": "TH",
    "vietnam": "VN",
    "philippines": "PH",
    "egypt": "EG",
    "kenya": "KE",
    "ghana": "GH",
    "ireland": "IE",
    "czech republic": "CZ",
    "czechia": "CZ",
    "hungary": "HU",
    "romania": "RO",
    "greece": "GR",
}


def normalize_country(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    # Try "City, Country" format — take last token
    parts = [p.strip() for p in raw.split(",")]
    candidates = [raw] + (parts if len(parts) > 1 else [])

    for candidate in candidates:
        key = candidate.lower().strip()
        if key in COUNTRY_LOOKUP:
            return COUNTRY_LOOKUP[key]

    logger.debug(f"Could not normalize country from: '{raw}'")
    return None
