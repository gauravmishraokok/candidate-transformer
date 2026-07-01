import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_TAXONOMY_PATH = Path(__file__).parent.parent.parent / "data" / "skills_taxonomy.json"


class SkillNormalizer:
    def __init__(self, taxonomy_path: Path = _TAXONOMY_PATH):
        self._canonical_names: list[str] = []
        self._reverse_lookup: dict[str, str] = {}
        self._embeddings = None
        self._model = None

        self._load_taxonomy(taxonomy_path)
        self._load_model()

    def _load_taxonomy(self, path: Path):
        try:
            with open(path, encoding="utf-8") as f:
                taxonomy: dict[str, list[str]] = json.load(f)

            self._canonical_names = list(taxonomy.keys())

            for canonical, aliases in taxonomy.items():
                self._reverse_lookup[canonical.lower()] = canonical
                for alias in aliases:
                    self._reverse_lookup[alias.lower().strip()] = canonical

            logger.info(f"Loaded skill taxonomy: {len(self._canonical_names)} canonical skills, "
                        f"{len(self._reverse_lookup)} total aliases")
        except Exception as e:
            logger.error(f"Failed to load skills taxonomy: {e}")

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            logger.info("Loading sentence-transformers model: all-MiniLM-L6-v2")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._embeddings = self._model.encode(
                self._canonical_names,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            logger.info("Skill embeddings pre-computed")
        except Exception as e:
            logger.warning(f"Could not load sentence-transformers model: {e}. Semantic matching disabled.")
            self._model = None
            self._embeddings = None

    def normalize(self, raw_skill: str) -> Optional[str]:
        if not raw_skill or not raw_skill.strip():
            return None

        raw_skill = raw_skill.strip()
        key = raw_skill.lower()

        # Step 1: exact reverse lookup
        if key in self._reverse_lookup:
            return self._reverse_lookup[key]

        # Step 2: fuzzy via cosine similarity
        if self._model is not None and self._embeddings is not None:
            try:
                import numpy as np

                embedding = self._model.encode([raw_skill], convert_to_numpy=True)
                norm_emb = embedding / (np.linalg.norm(embedding, axis=1, keepdims=True) + 1e-10)
                norm_canon = self._embeddings / (
                    np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-10
                )
                similarities = norm_emb @ norm_canon.T
                best_idx = int(np.argmax(similarities[0]))
                best_score = float(similarities[0][best_idx])

                if best_score >= 0.80:
                    canonical = self._canonical_names[best_idx]
                    logger.debug(f"Fuzzy matched '{raw_skill}' → '{canonical}' (score={best_score:.3f})")
                    return canonical
            except Exception as e:
                logger.warning(f"Semantic skill matching error for '{raw_skill}': {e}")

        # Step 3: unknown skill
        logger.debug(f"Skill not recognized: '{raw_skill}'")
        return None

    def normalize_batch(self, skills: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for skill in skills:
            canonical = self.normalize(skill)
            if canonical and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
        return result
