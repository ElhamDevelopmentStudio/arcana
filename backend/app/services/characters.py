import csv
import io
import json
from dataclasses import dataclass
from ast import literal_eval
from typing import Any


@dataclass
class ParsedCharacter:
    name: str
    verbalized_form: str
    gender: str
    aliases: list[str]
    notes: str | None
    source: str
    confidence: float


def _parse_aliases(raw_aliases: Any) -> list[str]:
    if raw_aliases is None:
        return []

    if isinstance(raw_aliases, list):
        return [str(alias).strip() for alias in raw_aliases if str(alias).strip()]

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
        return [str(alias).strip() for alias in parsed if str(alias).strip()]

    return [piece.strip() for piece in text.split(",") if piece.strip()]


def _parse_confidence(row: dict[str, str], row_number: int) -> float:
    raw_value = row.get("confidence")
    if raw_value is None:
        return 1.0

    if isinstance(raw_value, (int, float)):
        confidence = float(raw_value)
    else:
        if str(raw_value).strip() == "":
            return 1.0
        try:
            confidence = float(str(raw_value).strip())
        except ValueError as exc:
            raise ValueError(f"Row {row_number} has invalid confidence: {raw_value}") from exc

    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Row {row_number} has confidence outside range [0.0, 1.0]: {confidence}")

    return round(confidence, 4)


def _validate_row(row: dict[str, str], row_number: int) -> ParsedCharacter:
    required_fields = ["name", "verbalized_form", "gender"]
    missing = [field for field in required_fields if not str(row.get(field, "")).strip()]
    if missing:
        missing_csv = ", ".join(missing)
        raise ValueError(f"Row {row_number} is missing required fields: {missing_csv}")

    return ParsedCharacter(
        name=row["name"].strip(),
        verbalized_form=row["verbalized_form"].strip(),
        gender=row["gender"].strip().lower(),
        aliases=_parse_aliases(row.get("aliases")),
        notes=row.get("notes") and str(row["notes"]).strip() or None,
        source=str(row.get("source") or "user_import").strip() or "user_import",
        confidence=_parse_confidence(row, row_number),
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
