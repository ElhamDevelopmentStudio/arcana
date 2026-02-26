from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

_STANDARD_GENDERS = frozenset({"male", "female", "neutral"})
_CUSTOM_GENDER = "custom"
_UNKNOWN_GENDER = "unknown"
_MIN_SEVERITY = 0.0
_MAX_SEVERITY = 1.0
_INSUFFICIENT_INFERENCE_CONFIDENCE_THRESHOLD = 0.1


def _normalize_gender(value: Any) -> str:
    text = str(value or _UNKNOWN_GENDER).strip().lower()
    return text or _UNKNOWN_GENDER


def _coerce_confidence(value: Any, default: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return round(confidence, 4)


def _coerce_review_threshold(value: Any, default: float) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return default
    if threshold < 0.0:
        return 0.0
    if threshold > 1.0:
        return 1.0
    return round(threshold, 4)


def _extract_field(row: Mapping[str, Any] | object, key: str, default: Any) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _is_standard_gender(value: str) -> bool:
    return value in _STANDARD_GENDERS


def _build_comparison_state(manual_gender: str, inferred_gender: str) -> tuple[str, bool]:
    if _is_standard_gender(manual_gender) and _is_standard_gender(inferred_gender):
        if manual_gender == inferred_gender:
            return "match", False
        return "conflict", True
    if manual_gender == _CUSTOM_GENDER:
        return "manual_custom", False
    if manual_gender == _UNKNOWN_GENDER:
        return "manual_unknown", False
    if inferred_gender == _UNKNOWN_GENDER:
        return "inferred_unknown", False
    return "incomparable", False


def _build_contradiction_severity(
    comparison: str,
    manual_gender: str,
    inferred_gender: str,
    manual_confidence: float,
    inferred_confidence: float,
) -> float:
    if comparison != "conflict":
        return _MIN_SEVERITY

    if not _is_standard_gender(manual_gender) or not _is_standard_gender(inferred_gender):
        return _MIN_SEVERITY

    return round(
        max(_MIN_SEVERITY, min(_MAX_SEVERITY, (manual_confidence + inferred_confidence) / 2)),
        4,
    )


@dataclass(frozen=True)
class GenderComparisonResult:
    name: str
    manual_gender: str
    inferred_gender: str
    manual_confidence: float
    inferred_confidence: float
    comparison: str
    contradiction_severity: float
    is_contradiction: bool
    requires_review: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "manual_gender": self.manual_gender,
            "inferred_gender": self.inferred_gender,
            "manual_confidence": self.manual_confidence,
            "inferred_confidence": self.inferred_confidence,
            "comparison": self.comparison,
            "contradiction_severity": self.contradiction_severity,
            "is_contradiction": self.is_contradiction,
            "requires_review": self.requires_review,
        }


def compare_manual_and_inferred_gender_fields(
    character_rows: Iterable[Mapping[str, Any] | object],
    *,
    include_only_conflicts: bool = False,
    contradiction_review_required: bool = True,
    contradiction_review_threshold: float = 0.75,
) -> list[dict[str, Any]]:
    review_threshold = _coerce_review_threshold(contradiction_review_threshold, default=0.75)
    should_require_review = bool(contradiction_review_required)
    payloads: list[dict[str, Any]] = []

    for row in character_rows:
        name = str(_extract_field(row, "name", "")).strip()
        if not name:
            continue

        manual_gender = _normalize_gender(_extract_field(row, "gender", _UNKNOWN_GENDER))
        inferred_gender = _normalize_gender(_extract_field(row, "inferred_gender", _UNKNOWN_GENDER))
        manual_confidence = _coerce_confidence(_extract_field(row, "confidence", 1.0), default=1.0)
        inferred_confidence = _coerce_confidence(
            _extract_field(row, "inferred_confidence", 0.0),
            default=0.0,
        )
        comparison, is_contradiction = _build_comparison_state(manual_gender, inferred_gender)
        contradiction_severity = _build_contradiction_severity(
            comparison=comparison,
            manual_gender=manual_gender,
            inferred_gender=inferred_gender,
            manual_confidence=manual_confidence,
            inferred_confidence=inferred_confidence,
        )
        result = GenderComparisonResult(
            name=name,
            manual_gender=manual_gender,
            inferred_gender=inferred_gender,
            manual_confidence=manual_confidence,
            inferred_confidence=inferred_confidence,
            comparison=comparison,
            contradiction_severity=contradiction_severity,
            is_contradiction=is_contradiction,
            requires_review=(
                should_require_review and is_contradiction and contradiction_severity >= review_threshold
            ),
        )
        payload = result.to_payload()
        if include_only_conflicts and not is_contradiction:
            continue
        payloads.append(payload)

    payloads.sort(key=lambda value: value["name"].casefold())
    return payloads


def build_manual_inferred_gender_contradiction_warnings(
    character_rows: Iterable[Mapping[str, Any] | object],
    *,
    source: str = "character-gender-comparison",
    contradiction_review_required: bool = True,
    contradiction_review_threshold: float = 0.75,
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []

    for payload in compare_manual_and_inferred_gender_fields(
        character_rows,
        include_only_conflicts=True,
        contradiction_review_required=contradiction_review_required,
        contradiction_review_threshold=contradiction_review_threshold,
    ):
        severity = round(float(payload["contradiction_severity"]), 4)
        warnings.append(
            {
                "type": "manual_inferred_gender_contradiction",
                "level": "warning",
                "source": source,
                "character_name": payload["name"],
                "manual_gender": payload["manual_gender"],
                "inferred_gender": payload["inferred_gender"],
                "manual_confidence": payload["manual_confidence"],
                "inferred_confidence": payload["inferred_confidence"],
                "contradiction_severity": severity,
                "requires_review": payload["requires_review"],
                "message": (
                    f"Manual gender '{payload['manual_gender']}' for '{payload['name']}' "
                    f"contradicts inferred gender '{payload['inferred_gender']}' "
                    f"(severity {severity})."
                ),
            }
        )

    return warnings


def build_insufficient_inference_evidence_warnings(
    character_rows: Iterable[Mapping[str, Any] | object],
    *,
    source: str = "character-gender-comparison",
    inferred_confidence_threshold: float = _INSUFFICIENT_INFERENCE_CONFIDENCE_THRESHOLD,
) -> list[dict[str, object]]:
    threshold = _coerce_review_threshold(inferred_confidence_threshold, default=_INSUFFICIENT_INFERENCE_CONFIDENCE_THRESHOLD)

    warnings: list[dict[str, object]] = []
    for payload in compare_manual_and_inferred_gender_fields(character_rows):
        if payload["inferred_gender"] != _UNKNOWN_GENDER:
            continue

        if payload["inferred_confidence"] > threshold:
            continue

        warnings.append(
            {
                "type": "inferred_gender_insufficient_evidence",
                "level": "warning",
                "source": source,
                "character_name": payload["name"],
                "manual_gender": payload["manual_gender"],
                "inferred_gender": payload["inferred_gender"],
                "manual_confidence": payload["manual_confidence"],
                "inferred_confidence": payload["inferred_confidence"],
                "contradiction_severity": 0.0,
                "requires_review": False,
                "message": (
                    f"Insufficient evidence to confidently infer gender for '{payload['name']}'. "
                    f"Inferred gender remains '{payload['inferred_gender']}' "
                    f"(confidence {round(payload['inferred_confidence'], 4)})."
                ),
            }
        )

    return warnings
