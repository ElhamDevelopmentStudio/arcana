from enum import Enum
try:
    from enum import StrEnum
except ImportError:  # pragma: no cover
    class StrEnum(str, Enum):
        """Fallback for Python versions without enum.StrEnum."""

        def __str__(self) -> str:
            return self.value

        def __format__(self, format_spec: str) -> str:
            return str.__format__(self.value, format_spec)

from fastapi import HTTPException


class IngestionErrorType(StrEnum):
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNSUPPORTED_ENCODING = "unsupported_encoding"
    MISSING_CHAPTERS = "missing_chapters"


def make_ingestion_http_error(
    *,
    status_code: int,
    error_type: IngestionErrorType,
    detail: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers={"X-NIPE-Error-Type": str(error_type)},
    )
