#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ALLOWED_GENDERS = {"male", "female", "unknown"}


def _normalize_alias(alias: str) -> str:
    return alias.strip().lower()


def _validate_entry(canonical: str, info: dict) -> None:
    if not isinstance(canonical, str) or not canonical.strip():
        raise ValueError(f"Invalid canonical key: {canonical!r}")

    if not isinstance(info, dict):
        raise ValueError(f"Entry for {canonical!r} must be an object")

    if "gender" not in info:
        raise ValueError(f"Missing gender for {canonical!r}")
    gender = info["gender"]
    if gender not in ALLOWED_GENDERS:
        raise ValueError(
            f"Invalid gender for {canonical!r}: {gender!r} (allowed: {sorted(ALLOWED_GENDERS)})"
        )

    if "aliases" not in info:
        raise ValueError(f"Missing aliases for {canonical!r}")
    aliases = info["aliases"]
    if not isinstance(aliases, list) or len(aliases) == 0:
        raise ValueError(f"Aliases must be a non-empty list for {canonical!r}")

    for alias in aliases:
        if not isinstance(alias, str):
            raise ValueError(f"Alias for {canonical!r} must be a string: {alias!r}")
        if not _normalize_alias(alias):
            raise ValueError(f"Alias for {canonical!r} is empty after normalization: {alias!r}")

    if "speaker" in info and not isinstance(info["speaker"], bool):
        raise ValueError(f"Speaker flag for {canonical!r} must be boolean if present")


def _build_outputs(name_map: dict) -> tuple[dict, dict, dict, dict, str, dict]:
    alias_to_canonical_set: dict[str, set[str]] = defaultdict(set)
    alias_to_originals: dict[str, list[str]] = {}

    total_alias_entries = 0
    for canonical, info in name_map.items():
        _validate_entry(canonical, info)
        for alias in info["aliases"]:
            total_alias_entries += 1
            norm = _normalize_alias(alias)
            alias_to_canonical_set[norm].add(canonical)

            originals = alias_to_originals.setdefault(norm, [])
            if alias not in originals:
                originals.append(alias)

    alias_to_canonical = {
        alias: sorted(canonicals) for alias, canonicals in alias_to_canonical_set.items()
    }

    alias_to_gender = {}
    for alias, canonicals in alias_to_canonical.items():
        genders = {name_map[canonical]["gender"] for canonical in canonicals}
        alias_to_gender[alias] = genders.pop() if len(genders) == 1 else "unknown"

    alias_to_speaker = {}
    for alias, canonicals in alias_to_canonical.items():
        speakers = {bool(name_map[canonical].get("speaker", False)) for canonical in canonicals}
        alias_to_speaker[alias] = True if speakers == {True} else False

    aliases_sorted = sorted(alias_to_canonical.keys(), key=lambda a: (-len(a), a))
    regex_body = "|".join(re.escape(alias) for alias in aliases_sorted)
    aliases_regex = rf"(?i)\b(?:{regex_body})\b"

    stats = {
        "canonicals": len(name_map),
        "alias_entries": total_alias_entries,
        "unique_aliases": len(alias_to_canonical),
        "collisions": sum(1 for canonicals in alias_to_canonical.values() if len(canonicals) > 1),
    }

    return (
        alias_to_canonical,
        alias_to_gender,
        alias_to_speaker,
        alias_to_originals,
        aliases_regex,
        stats,
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    name_map_path = repo_root / "data" / "name_map" / "name_map.json"
    derived_dir = repo_root / "data" / "name_map" / "derived"

    try:
        with name_map_path.open("r", encoding="utf-8") as handle:
            name_map = json.load(handle)
    except FileNotFoundError:
        print(f"[ERROR] Missing input file: {name_map_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Invalid JSON in {name_map_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(name_map, dict):
        print("[ERROR] name_map.json must be a JSON object at the top level", file=sys.stderr)
        return 1

    try:
        (
            alias_to_canonical,
            alias_to_gender,
            alias_to_speaker,
            alias_to_originals,
            aliases_regex,
            stats,
        ) = _build_outputs(name_map)
    except ValueError as exc:
        print(f"[ERROR] Schema validation failed: {exc}", file=sys.stderr)
        return 1

    derived_dir.mkdir(parents=True, exist_ok=True)

    (derived_dir / "alias_to_canonical.json").write_text(
        json.dumps(alias_to_canonical, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (derived_dir / "alias_to_gender.json").write_text(
        json.dumps(alias_to_gender, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (derived_dir / "alias_to_speaker.json").write_text(
        json.dumps(alias_to_speaker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (derived_dir / "alias_to_originals.json").write_text(
        json.dumps(alias_to_originals, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (derived_dir / "aliases_regex.txt").write_text(aliases_regex + "\n", encoding="utf-8")

    for alias, canonicals in sorted(alias_to_canonical.items()):
        if len(canonicals) > 1:
            print(f'[WARN] Alias collision: "{alias}" -> {len(canonicals)} canonicals', file=sys.stderr)

    print("Name map prepared successfully.")
    print(f"Canonicals: {stats['canonicals']}")
    print(f"Alias entries: {stats['alias_entries']}")
    print(f"Unique normalized aliases: {stats['unique_aliases']}")
    print(f"Collisions: {stats['collisions']}")
    print(f"Derived directory: {derived_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
