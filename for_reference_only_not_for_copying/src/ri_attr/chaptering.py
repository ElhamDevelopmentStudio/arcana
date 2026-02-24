#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


CHAPTER_HEADER_RE = re.compile(r"^chapter\s+(\d+)\s*:\s*(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class ChapterChunk:
    number: int
    header: str
    lines: list[str]


def normalize_text(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    collapsed = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 2:
                collapsed.append("")
        else:
            blank_run = 0
            collapsed.append(line)
    return "\n".join(collapsed)


def _canonical_header(number: int, title: str) -> str:
    return f"Chapter {number}: {title.strip()}".strip()


def split_chapters(text: str) -> list[ChapterChunk]:
    lines = text.split("\n")
    chapters: list[ChapterChunk] = []
    current_num = None
    current_header = None
    current_lines: list[str] = []
    preface: list[str] = []

    def flush() -> None:
        nonlocal current_num, current_header, current_lines
        if current_num is None or current_header is None:
            return
        chapters.append(
            ChapterChunk(number=current_num, header=current_header, lines=list(current_lines))
        )
        current_num = None
        current_header = None
        current_lines = []

    found_header = False
    for line in lines:
        match = CHAPTER_HEADER_RE.match(line.strip())
        if match:
            found_header = True
            number = int(match.group(1))
            title = match.group(2).strip()
            header = _canonical_header(number, title)

            if current_num is None:
                current_num = number
                current_header = header
                current_lines = [header]
                if preface:
                    current_lines.extend(preface)
                    preface = []
                continue

            if number == current_num:
                has_content = len(current_lines) > 1
                if not has_content:
                    current_header = header
                    current_lines[0] = header
                    continue

                if line.lower().startswith(current_header.lower()):
                    remainder = line[len(current_header) :].lstrip()
                    if remainder:
                        current_lines.append(remainder)
                continue

            flush()
            current_num = number
            current_header = header
            current_lines = [header]
            continue

        if current_num is None:
            if line.strip():
                preface.append(line)
            continue
        current_lines.append(line)

    flush()

    if not found_header:
        return []

    return chapters


def write_chapters(chapters: list[ChapterChunk], out_dir: Path) -> list[Path]:
    out_paths = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for chapter in chapters:
        filename = f"chapter_{chapter.number}.txt"
        out_path = out_dir / filename
        out_path.write_text("\n".join(chapter.lines).rstrip() + "\n", encoding="utf-8")
        out_paths.append(out_path)
    return out_paths
