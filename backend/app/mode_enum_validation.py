from __future__ import annotations

from pathlib import Path
import re

from app.modes import DEFAULT_MODE, MODE_PERSISTENCE_PATHS, MODE_VALUES


DOC_SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+MODE-001 System Mode Enum Contract\s*$")
FIELD_PATTERN = re.compile(r"(?m)^\s*-\s+([a-z_]+):\s+(.+?)\s*$")

REQUIRED_FIELD_KEYS = {"allowed_modes", "default_mode", "project_mode_path", "run_config_path"}


class ModeEnumValidationError(ValueError):
    pass


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _parse_modes(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def extract_mode_001_section(markdown: str) -> str:
    section_match = DOC_SECTION_HEADING_PATTERN.search(markdown)
    if section_match is None:
        raise ModeEnumValidationError("Could not find 'MODE-001 System Mode Enum Contract' section.")
    return markdown[section_match.end() :]


def parse_mode_contract(section_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field_match in FIELD_PATTERN.finditer(section_text):
        key = _normalize_text(field_match.group(1))
        value = _normalize_text(field_match.group(2))
        fields[key] = value
    return fields


def validate_mode_001_contract(path: Path) -> dict[str, int]:
    markdown = path.read_text(encoding="utf-8")
    section = extract_mode_001_section(markdown)
    fields = parse_mode_contract(section)

    missing = REQUIRED_FIELD_KEYS - set(fields.keys())
    if missing:
        raise ModeEnumValidationError(f"MODE-001 contract is missing required fields: {sorted(missing)}")

    declared_modes = _parse_modes(fields["allowed_modes"])
    if declared_modes != list(MODE_VALUES):
        raise ModeEnumValidationError(
            f"allowed_modes mismatch. expected={list(MODE_VALUES)} actual={declared_modes}"
        )

    default_mode = fields["default_mode"]
    if default_mode != DEFAULT_MODE:
        raise ModeEnumValidationError(f"default_mode mismatch. expected={DEFAULT_MODE} actual={default_mode}")

    project_mode_path = fields["project_mode_path"]
    if project_mode_path not in MODE_PERSISTENCE_PATHS:
        raise ModeEnumValidationError(
            f"project_mode_path mismatch. expected one of {list(MODE_PERSISTENCE_PATHS)} actual={project_mode_path}"
        )

    run_config_path = fields["run_config_path"]
    if run_config_path not in MODE_PERSISTENCE_PATHS:
        raise ModeEnumValidationError(
            f"run_config_path mismatch. expected one of {list(MODE_PERSISTENCE_PATHS)} actual={run_config_path}"
        )

    return {
        "mode_count": len(declared_modes),
        "persistence_paths": len(MODE_PERSISTENCE_PATHS),
    }
