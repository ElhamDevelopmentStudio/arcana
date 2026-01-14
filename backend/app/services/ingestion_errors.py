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

from fastapi import HTTPException, status


class IngestionErrorType(StrEnum):
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNSUPPORTED_ENCODING = "unsupported_encoding"
    MISSING_CHAPTERS = "missing_chapters"


class IngestionError(HTTPException):
    """Base exception for ingestion failures with machine-readable error type metadata."""

    def __init__(self, *, status_code: int, error_type: IngestionErrorType, detail: str):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"X-NIPE-Error-Type": str(error_type)},
        )


class UnsupportedFormatIngestionError(IngestionError):
    """Raised when uploaded ingestion data uses an unsupported file format."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(
            status_code=status_code,
            error_type=IngestionErrorType.UNSUPPORTED_FORMAT,
            detail=detail,
        )


class UnsupportedEncodingIngestionError(IngestionError):
    """Raised when text content cannot be decoded with supported encodings."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(
            status_code=status_code,
            error_type=IngestionErrorType.UNSUPPORTED_ENCODING,
            detail=detail,
        )


def make_ingestion_http_error(
    *,
    status_code: int,
    error_type: IngestionErrorType,
    detail: str,
) -> HTTPException:
    return IngestionError(
        status_code=status_code,
        error_type=error_type,
        detail=detail,
    )
