from __future__ import annotations

from typing import Protocol


class EpubParser(Protocol):
    def parse(self, payload: bytes) -> list[tuple[str, str]]:
        ...


class StubEpubParser:
    def parse(self, payload: bytes) -> list[tuple[str, str]]:
        raise NotImplementedError("EPUB parser is not implemented yet. Add a concrete parser adapter to enable this path.")


def extract_epub_chapters(payload: bytes, parser: EpubParser | None = None) -> list[tuple[str, str]]:
    active_parser = parser or StubEpubParser()
    return active_parser.parse(payload)
