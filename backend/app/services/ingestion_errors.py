from enum import StrEnum

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
