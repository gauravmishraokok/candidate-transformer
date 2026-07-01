import logging
from typing import Any

logger = logging.getLogger(__name__)


class OutputValidator:
    def validate(self, output: dict, config: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        fields_spec = config.get("fields", [])

        for field_def in fields_spec:
            key = field_def["path"]
            required = field_def.get("required", False)
            expected_type = field_def.get("type", "string")

            value = output.get(key)

            if required and (value is None or key not in output):
                errors.append(f"Required field '{key}' is missing or null")
                continue

            if value is None:
                continue

            # Type checks
            if expected_type == "string":
                if not isinstance(value, str):
                    errors.append(f"Field '{key}' expected string, got {type(value).__name__}")
            elif expected_type == "string[]":
                if not isinstance(value, list):
                    errors.append(f"Field '{key}' expected list, got {type(value).__name__}")
            elif expected_type == "number":
                if not isinstance(value, (int, float)):
                    errors.append(f"Field '{key}' expected number, got {type(value).__name__}")
            elif expected_type in ("object", "object[]"):
                pass  # flexible

        # Semantic validations on known fields
        overall_conf = output.get("overall_confidence")
        if overall_conf is not None:
            if not isinstance(overall_conf, (int, float)) or not (0.0 <= overall_conf <= 1.0):
                errors.append(
                    f"overall_confidence must be 0.0-1.0, got {overall_conf}"
                )

        emails = output.get("emails") or (
            [output["primary_email"]] if "primary_email" in output and output["primary_email"] else []
        )
        if isinstance(emails, list):
            for email in emails:
                if isinstance(email, str) and "@" not in email:
                    errors.append(f"Email '{email}' does not contain '@'")

        phones = output.get("phones") or (
            [output["phone"]] if "phone" in output and output["phone"] else []
        )
        if isinstance(phones, list):
            for phone in phones:
                if isinstance(phone, str) and not phone.startswith("+"):
                    errors.append(f"Phone '{phone}' is not in E.164 format (missing '+')")

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Validation failed with {len(errors)} error(s): {errors}")

        return is_valid, errors
