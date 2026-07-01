import json
import logging
from pathlib import Path
from typing import Any, Optional
from schemas.canonical import CanonicalProfile

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "fields": [
        {"path": "candidate_id", "from": "candidate_id", "type": "string", "required": True},
        {"path": "full_name", "from": "full_name", "type": "string", "required": True},
        {"path": "emails", "from": "emails", "type": "string[]"},
        {"path": "phones", "from": "phones", "type": "string[]"},
        {"path": "location", "from": "location", "type": "object"},
        {"path": "links", "from": "links", "type": "object"},
        {"path": "headline", "from": "headline", "type": "string"},
        {"path": "years_experience", "from": "years_experience", "type": "number"},
        {"path": "skills", "from": "skills", "type": "object[]"},
        {"path": "experience", "from": "experience", "type": "object[]"},
        {"path": "education", "from": "education", "type": "object[]"},
    ],
    "include_confidence": True,
    "include_provenance": True,
    "on_missing": "null",
}


def _resolve_path(profile: CanonicalProfile, path_expr: str) -> Any:
    """
    Resolve path expressions against CanonicalProfile:
      "full_name"           → profile.full_name
      "emails[0]"           → profile.emails[0]
      "skills[].name"       → [s.name for s in profile.skills]
      "location.country"    → profile.location.country
      "links.github"        → profile.links.github
      "experience[0].company" → profile.experience[0].company
    """
    expr = path_expr.strip()

    # Array extraction: "skills[].name" or "experience[].title"
    if "[]." in expr:
        parts = expr.split("[].", 1)
        array_path = parts[0]
        sub_field = parts[1]
        array_val = _resolve_simple(profile, array_path)
        if array_val is None:
            return None
        if isinstance(array_val, list):
            result = []
            for item in array_val:
                val = _get_nested(item, sub_field)
                if val is not None:
                    result.append(val)
            return result
        return None

    # Indexed access: "emails[0]" or "experience[0].company"
    import re
    indexed = re.match(r'^(\w+)\[(\d+)\](?:\.(.+))?$', expr)
    if indexed:
        array_name = indexed.group(1)
        idx = int(indexed.group(2))
        sub = indexed.group(3)
        array_val = _resolve_simple(profile, array_name)
        if array_val is None or not isinstance(array_val, list):
            return None
        if idx >= len(array_val):
            return None
        item = array_val[idx]
        if sub:
            return _get_nested(item, sub)
        return item

    # Nested dot access: "location.country", "links.github"
    if "." in expr:
        parts = expr.split(".", 1)
        parent = _resolve_simple(profile, parts[0])
        if parent is None:
            return None
        return _get_nested(parent, parts[1])

    # Simple field
    return _resolve_simple(profile, expr)


def _resolve_simple(profile: CanonicalProfile, field: str) -> Any:
    try:
        val = getattr(profile, field)
        # Convert pydantic models to dicts for serialization
        if hasattr(val, "model_dump"):
            return val.model_dump()
        if isinstance(val, list):
            result = []
            for item in val:
                if hasattr(item, "model_dump"):
                    result.append(item.model_dump())
                else:
                    result.append(item)
            return result
        return val
    except AttributeError:
        return None


def _get_nested(obj: Any, field: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        val = obj.get(field)
    else:
        try:
            val = getattr(obj, field)
        except AttributeError:
            return None
    if hasattr(val, "model_dump"):
        return val.model_dump()
    return val


class OutputProjector:
    def __init__(self, config: dict | str | Path | None = None):
        self.config = self._load_config(config)

    def _load_config(self, config) -> dict:
        if config is None:
            return DEFAULT_CONFIG
        if isinstance(config, dict):
            return config
        path = Path(config)
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load projector config from {path}: {e}")
                return DEFAULT_CONFIG
        logger.warning(f"Config path not found: {path}, using default")
        return DEFAULT_CONFIG

    def project(self, profile: CanonicalProfile) -> dict:
        fields_spec = self.config.get("fields", DEFAULT_CONFIG["fields"])
        on_missing = self.config.get("on_missing", "null")
        include_confidence = self.config.get("include_confidence", True)
        include_provenance = self.config.get("include_provenance", True)

        output: dict[str, Any] = {}

        for field_def in fields_spec:
            out_key = field_def["path"]
            src_path = field_def.get("from", out_key)
            required = field_def.get("required", False)

            value = _resolve_path(profile, src_path)

            if value is None:
                if on_missing == "omit":
                    continue
                elif on_missing == "error":
                    if required:
                        raise ValueError(
                            f"Required field '{out_key}' (from '{src_path}') is missing"
                        )
                    output[out_key] = None
                else:  # "null"
                    output[out_key] = None
            else:
                output[out_key] = value

        if include_confidence:
            output["overall_confidence"] = profile.overall_confidence

        if include_provenance:
            output["provenance"] = [p.model_dump() for p in profile.provenance]

        return output
