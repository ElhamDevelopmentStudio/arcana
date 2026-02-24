import csv
import io
import json
from dataclasses import dataclass


@dataclass
class ParsedCharacter:
    name: str
    verbalized_form: str
    gender: str


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
