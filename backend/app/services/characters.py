import csv
import io
import json
from ast import literal_eval
from dataclasses import dataclass
from typing import Any

ALLOWED_GENDER_VALUES = frozenset({"male", "female", "neutral", "unknown", "custom"})


@dataclass
class ParsedCharacter:
    name: str
    verbalized_form: str
    gender: str
    aliases: list[str]
    notes: str | None
    source: str
    confidence: float
    inferred_gender: str
    inferred_confidence: float
    inferred_source_trace: list[dict[str, Any]]


def _parse_aliases(raw_aliases: Any) -> list[str]:
    if raw_aliases is None:
        return []

    if isinstance(raw_aliases, list):
        cleaned = [str(alias).strip() for alias in raw_aliases if str(alias).strip()]
        return list(dict.fromkeys(cleaned))

    if not isinstance(raw_aliases, str):
        return []

    text = raw_aliases.strip()
    if not text:
        return []

    try:
        parsed = literal_eval(text)
    except (SyntaxError, ValueError):
        parsed = None

    if isinstance(parsed, list):
        cleaned = [str(alias).strip() for alias in parsed if str(alias).strip()]
        return list(dict.fromkeys(cleaned))

    cleaned = [piece.strip() for piece in text.split(",") if piece.strip()]
    return list(dict.fromkeys(cleaned))


def _parse_confidence(raw_value: Any, row_number: int, *, default: float) -> float:
    if raw_value is None:
        return default

    if isinstance(raw_value, (int, float)):
        confidence = float(raw_value)
    else:
        if str(raw_value).strip() == "":
            return default
        try:
            confidence = float(str(raw_value).strip())
        except ValueError as exc:
            raise ValueError(f"Row {row_number} has invalid confidence: {raw_value}") from exc

    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Row {row_number} has confidence outside range [0.0, 1.0]: {confidence}")

    return round(confidence, 4)


def _resolve_field(row: dict[str, str], field_names: list[str]) -> str:
    for field in field_names:
        value = row.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_gender(row_number: int, raw_value: str) -> str:
    normalized = str(raw_value).strip().lower()
    if not normalized:
        return ""
    if normalized not in ALLOWED_GENDER_VALUES:
        raise ValueError(
            f"Row {row_number} has unsupported gender '{raw_value}'. "
            f"Supported values are: male, female, neutral, unknown, custom"
        )
    return normalized


def _normalize_optional_gender(row_number: int, raw_value: str | None, *, field: str) -> str:
    normalized = str(raw_value).strip().lower() if raw_value is not None else ""
    if not normalized:
        return "unknown"
    if normalized not in ALLOWED_GENDER_VALUES:
        raise ValueError(
            f"Row {row_number} has unsupported {field} '{raw_value}'. "
            f"Supported values are: male, female, neutral, unknown, custom"
        )
    return normalized


def _coerce_source_trace(raw_source_trace: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_source_trace, list):
        return []

    normalized: list[dict[str, Any]] = []
    for trace in raw_source_trace:
        if not isinstance(trace, dict):
            continue
        normalized.append(
            {
                "kind": str(trace.get("kind") or ""),
                "chapter_index": int(trace.get("chapter_index", 0) or 0),
                "span_start": int(trace.get("span_start", 0) or 0),
                "span_end": int(trace.get("span_end", 0) or 0),
                "excerpt": str(trace.get("excerpt") or ""),
                "weight": float(trace.get("weight", 0.0) or 0.0),
            }
        )
    return normalized


def _validate_row(row: dict[str, str], row_number: int) -> ParsedCharacter:
    name = _resolve_field(row, ["name"])
    verbalized_form = _resolve_field(row, ["verbalized_form", "verbalized"])
    gender = _normalize_gender(row_number, _resolve_field(row, ["gender"]))

    required_fields = [
        ("name", name),
        ("verbalized_form", verbalized_form),
        ("gender", gender),
    ]
    missing = [field_name for field_name, value in required_fields if not value]
    if missing:
        missing_csv = ", ".join(missing)
        raise ValueError(f"Row {row_number} is missing required fields: {missing_csv}")

    return ParsedCharacter(
        name=name,
        verbalized_form=verbalized_form,
        gender=gender,
        aliases=_parse_aliases(row.get("aliases")),
        notes=row.get("notes") and str(row["notes"]).strip() or None,
        source=str(row.get("source") or "user_import").strip() or "user_import",
        confidence=_parse_confidence(row.get("confidence"), row_number, default=1.0),
        inferred_gender=_normalize_optional_gender(
            row_number=row_number,
            raw_value=row.get("inferred_gender"),
            field="inferred_gender",
        ),
        inferred_confidence=_parse_confidence(
            row.get("inferred_confidence"),
            row_number,
            default=0.0,
        ),
        inferred_source_trace=_coerce_source_trace(row.get("inferred_source_trace")),
    )


def _parse_json(payload: bytes) -> list[ParsedCharacter]:
    decoded = payload.decode("utf-8")
    data = json.loads(decoded)
    rows: list[dict[str, str]] = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                rows.append(
                    {
                        "name": value.get("name", key),
                        "verbalized_form": value.get("verbalized_form")
                        or value.get("verbalized")
                        or "",
                        "gender": value.get("gender", ""),
                        "aliases": value.get("aliases"),
                        "notes": value.get("notes"),
                        "source": value.get("source"),
                        "confidence": value.get("confidence"),
                        "inferred_gender": value.get("inferred_gender"),
                        "inferred_confidence": value.get("inferred_confidence"),
                        "inferred_source_trace": value.get("inferred_source_trace"),
                    }
                )
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append(
                    {
                        "name": item.get("name", ""),
                        "verbalized_form": item.get("verbalized_form")
                        or item.get("verbalized")
                        or "",
                        "gender": item.get("gender", ""),
                        "aliases": item.get("aliases"),
                        "notes": item.get("notes"),
                        "source": item.get("source"),
                        "confidence": item.get("confidence"),
                        "inferred_gender": item.get("inferred_gender"),
                        "inferred_confidence": item.get("inferred_confidence"),
                        "inferred_source_trace": item.get("inferred_source_trace"),
                    }
                )

    parsed: list[ParsedCharacter] = []
    for row_number, row in enumerate(rows, start=1):
        parsed.append(_validate_row(row, row_number))
    return parsed


def _parse_csv(payload: bytes) -> list[ParsedCharacter]:
    decoded = payload.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    parsed: list[ParsedCharacter] = []
    for row_number, row in enumerate(reader, start=1):
        parsed.append(_validate_row(row, row_number))
    return parsed


def parse_character_file(filename: str, payload: bytes) -> list[ParsedCharacter]:
    lowered = filename.lower()
    if lowered.endswith(".json"):
        parsed = _parse_json(payload)
    elif lowered.endswith(".csv"):
        parsed = _parse_csv(payload)
    else:
        raise ValueError("Unsupported character map format. Use JSON or CSV.")

    if not parsed:
        raise ValueError("Character map file did not contain any valid rows.")

    deduped: dict[str, ParsedCharacter] = {}
    for row in parsed:
        deduped[row.name.lower()] = row
    return list(deduped.values())
