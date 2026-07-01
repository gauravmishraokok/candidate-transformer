import csv
import logging
from pathlib import Path
from .base import BaseExtractor
from schemas.raw_record import RawRecord

logger = logging.getLogger(__name__)


class CsvExtractor(BaseExtractor):
    SOURCE_TYPE = "CSV"
    RELIABILITY_WEIGHT = 0.90

    def extract(self, source: str) -> list[RawRecord]:
        records = []
        try:
            path = Path(source)
            if not path.exists():
                logger.error(f"CSV file not found: {source}")
                return []

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_index, row in enumerate(reader):
                    try:
                        record = self._parse_row(row, row_index)
                        records.append(record)
                    except Exception as e:
                        logger.error(f"Error parsing CSV row {row_index}: {e}")
                        continue

        except FileNotFoundError:
            logger.error(f"CSV file not found: {source}")
        except Exception as e:
            logger.error(f"CSV parse error: {e}")

        return records

    def _clean(self, value) -> str | None:
        if value is None:
            return None
        v = str(value).strip()
        return v if v else None

    def _parse_row(self, row: dict, row_index: int) -> RawRecord:
        source_id = self._make_source_id(str(row_index))

        name = self._clean(row.get("name"))
        email = self._clean(row.get("email"))
        phone = self._clean(row.get("phone"))
        current_company = self._clean(row.get("current_company"))
        title = self._clean(row.get("title"))
        location = self._clean(row.get("location"))
        linkedin_url = self._clean(row.get("linkedin_url"))
        github_url = self._clean(row.get("github_url"))
        years_exp_raw = self._clean(row.get("years_experience"))

        years_experience = None
        if years_exp_raw:
            try:
                years_experience = float(years_exp_raw)
            except (ValueError, TypeError):
                logger.warning(f"Cannot parse years_experience '{years_exp_raw}' in row {row_index}")

        experience = []
        if current_company or title:
            experience.append({
                "company": current_company,
                "title": title,
                "start_raw": None,
                "end_raw": None,
                "summary": None,
            })

        return RawRecord(
            source_id=source_id,
            source_type=self.SOURCE_TYPE,
            reliability_weight=self.RELIABILITY_WEIGHT,
            full_name=name,
            emails=[email] if email else [],
            phones=[phone] if phone else [],
            location_raw=location,
            linkedin_url=linkedin_url,
            github_url=github_url,
            years_experience=years_experience,
            experience=experience,
        )
