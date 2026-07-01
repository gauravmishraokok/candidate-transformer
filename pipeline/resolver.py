import logging
from typing import Optional
import jellyfish
from schemas.raw_record import RawRecord

logger = logging.getLogger(__name__)

NAME_SIMILARITY_THRESHOLD = 0.88


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> bool:
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        return True


def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return url.lower().rstrip("/").strip()


def _normalize_email(email: str) -> str:
    return email.lower().strip()


class EntityResolver:
    def resolve(self, records: list[RawRecord]) -> list[list[RawRecord]]:
        n = len(records)
        if n == 0:
            return []
        if n == 1:
            return [records]

        uf = UnionFind(n)

        # Build index sets for Tier 1 deterministic anchors
        email_index: dict[str, list[int]] = {}
        linkedin_index: dict[str, list[int]] = {}
        github_index: dict[str, list[int]] = {}

        for i, rec in enumerate(records):
            for email in rec.emails:
                key = _normalize_email(email)
                if key:
                    email_index.setdefault(key, []).append(i)

            if rec.linkedin_url:
                key = _normalize_url(rec.linkedin_url)
                if key:
                    linkedin_index.setdefault(key, []).append(i)

            if rec.github_url:
                key = _normalize_url(rec.github_url)
                if key:
                    github_index.setdefault(key, []).append(i)

        # Tier 1: merge on exact anchor matches
        for email, indices in email_index.items():
            for j in range(1, len(indices)):
                if uf.union(indices[0], indices[j]):
                    logger.info(
                        f"Merged records {indices[0]} and {indices[j]} via email anchor: {email}"
                    )

        for url, indices in linkedin_index.items():
            for j in range(1, len(indices)):
                if uf.union(indices[0], indices[j]):
                    logger.info(
                        f"Merged records {indices[0]} and {indices[j]} via LinkedIn URL: {url}"
                    )

        for url, indices in github_index.items():
            for j in range(1, len(indices)):
                if uf.union(indices[0], indices[j]):
                    logger.info(
                        f"Merged records {indices[0]} and {indices[j]} via GitHub URL: {url}"
                    )

        # Tier 2: probabilistic name similarity fallback
        for i in range(n):
            for j in range(i + 1, n):
                if uf.find(i) == uf.find(j):
                    continue  # already linked

                name_i = records[i].full_name
                name_j = records[j].full_name
                if not name_i or not name_j:
                    continue

                try:
                    score = jellyfish.jaro_winkler_similarity(
                        name_i.lower().strip(),
                        name_j.lower().strip(),
                    )
                except Exception:
                    score = 0.0

                if score >= NAME_SIMILARITY_THRESHOLD:
                    uf.union(i, j)
                    logger.warning(
                        f"Merged records {i} and {j} via name similarity "
                        f"('{name_i}' ↔ '{name_j}', score={score:.3f}) — verify manually"
                    )
                    # Tag the records with the match note
                    if not hasattr(records[i], "_match_notes"):
                        records[i].__dict__.setdefault("_match_notes", [])
                    records[i].__dict__["_match_notes"].append(
                        f"Merged via name similarity ({score:.2f}) — verify manually"
                    )

        # Build groups from union-find
        groups: dict[int, list[RawRecord]] = {}
        for i, rec in enumerate(records):
            root = uf.find(i)
            groups.setdefault(root, []).append(rec)

        result = list(groups.values())
        logger.info(f"Entity resolution: {n} records → {len(result)} candidate groups")
        return result
