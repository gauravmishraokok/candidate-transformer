import logging
import re
from urllib.parse import urlparse
import httpx
from .base import BaseExtractor
from schemas.raw_record import RawRecord

logger = logging.getLogger(__name__)


class GithubApiExtractor(BaseExtractor):
    SOURCE_TYPE = "GITHUB_API"
    RELIABILITY_WEIGHT = 0.85

    def extract(self, source: str) -> list[RawRecord]:
        username = self._parse_username(source)
        if not username:
            logger.error(f"Could not parse GitHub username from: {source}")
            return []

        source_id = f"src_github_{username}"

        try:
            with httpx.Client(timeout=10.0) as client:
                user_data = self._fetch_user(client, username)
                if user_data is None:
                    return []

                repos_data = self._fetch_repos(client, username)

        except httpx.ConnectError as e:
            logger.error(f"GitHub API connect error for {username}: {e}")
            return []
        except httpx.TimeoutException as e:
            logger.error(f"GitHub API timeout for {username}: {e}")
            return []
        except Exception as e:
            logger.error(f"GitHub API unexpected error for {username}: {e}")
            return []

        skills_raw = []
        if repos_data:
            languages = set()
            for repo in repos_data:
                lang = repo.get("language")
                if lang:
                    languages.add(lang)
            skills_raw = list(languages)

        name = user_data.get("name") or None
        bio = user_data.get("bio") or None
        location_raw = user_data.get("location") or None
        blog = user_data.get("blog") or None
        email = user_data.get("email") or None
        html_url = user_data.get("html_url") or None
        company = user_data.get("company") or None

        emails = [email.strip()] if email and email.strip() else []

        experience = []
        if company:
            experience.append({
                "company": company.strip().lstrip("@"),
                "title": None,
                "start_raw": None,
                "end_raw": None,
                "summary": None,
            })

        record = RawRecord(
            source_id=source_id,
            source_type=self.SOURCE_TYPE,
            reliability_weight=self.RELIABILITY_WEIGHT,
            full_name=name,
            emails=emails,
            phones=[],
            location_raw=str(location_raw).strip() if location_raw else None,
            github_url=html_url,
            headline=bio,
            skills_raw=skills_raw,
            experience=experience,
        )

        if blog and blog.strip():
            record = record.model_copy(update={"summary": blog.strip()})

        return [record]

    def _parse_username(self, source: str) -> str | None:
        source = source.strip()
        if source.startswith("http://") or source.startswith("https://") or "github.com/" in source:
            parsed = urlparse(source if "://" in source else "https://" + source)
            path = parsed.path.strip("/")
            parts = path.split("/")
            return parts[0] if parts and parts[0] else None
        return source if source else None

    def _fetch_user(self, client: httpx.Client, username: str) -> dict | None:
        try:
            response = client.get(
                f"https://api.github.com/users/{username}",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if response.status_code == 404:
                logger.warning(f"GitHub user not found: {username}")
                return None
            if response.status_code == 403:
                logger.warning("GitHub API rate limited")
                return None
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise
        except httpx.TimeoutException:
            raise
        except Exception as e:
            logger.error(f"GitHub user fetch error: {e}")
            return None

    def _fetch_repos(self, client: httpx.Client, username: str) -> list[dict]:
        try:
            response = client.get(
                f"https://api.github.com/users/{username}/repos?per_page=20",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if response.status_code in (403, 404):
                return []
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"GitHub repos fetch error for {username}: {e}")
            return []
