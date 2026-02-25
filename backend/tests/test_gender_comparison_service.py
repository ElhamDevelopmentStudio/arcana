from app.services.gender_comparison import compare_manual_and_inferred_gender_fields


def test_unit_gender_comparison_flags_conflict_and_matches() -> None:
    payload = compare_manual_and_inferred_gender_fields(
        [
            {
                "name": "Nia",
                "gender": "male",
                "inferred_gender": "female",
                "confidence": 1.0,
                "inferred_confidence": 0.91,
            },
            {
                "name": "Kai",
                "gender": "female",
                "inferred_gender": "female",
                "confidence": 0.9,
                "inferred_confidence": 0.88,
            },
        ]
    )

    assert len(payload) == 2
    nia = next(item for item in payload if item["name"] == "Nia")
    kai = next(item for item in payload if item["name"] == "Kai")

    assert nia["comparison"] == "conflict"
    assert nia["contradiction_severity"] == 0.955
    assert nia["is_contradiction"] is True
    assert nia["requires_review"] is True
    assert kai["comparison"] == "match"
    assert kai["contradiction_severity"] == 0.0
    assert kai["is_contradiction"] is False
    assert kai["requires_review"] is False


def test_unit_gender_comparison_marks_unknown_and_custom_as_not_actionable() -> None:
    payload = compare_manual_and_inferred_gender_fields(
        [
            {
                "name": "Tess",
                "gender": "unknown",
                "inferred_gender": "female",
                "confidence": 1.0,
                "inferred_confidence": 0.82,
            },
            {
                "name": "Ray",
                "gender": "custom",
                "inferred_gender": "male",
                "confidence": 1.0,
                "inferred_confidence": 0.77,
            },
        ]
    )

    tessa = next(item for item in payload if item["name"] == "Tess")
    ray = next(item for item in payload if item["name"] == "Ray")

    assert tessa["comparison"] == "manual_unknown"
    assert tessa["contradiction_severity"] == 0.0
    assert tessa["requires_review"] is False
    assert tessa["is_contradiction"] is False
    assert ray["comparison"] == "manual_custom"
    assert ray["contradiction_severity"] == 0.0
    assert ray["requires_review"] is False
    assert ray["is_contradiction"] is False


def test_unit_gender_comparison_include_only_conflicts() -> None:
    payload = compare_manual_and_inferred_gender_fields(
        [
            {"name": "Tess", "gender": "female", "inferred_gender": "female"},
            {"name": "Nia", "gender": "male", "inferred_gender": "female"},
            {"name": "Kai", "gender": "male", "inferred_gender": "female"},
        ],
        include_only_conflicts=True,
    )

    assert len(payload) == 2
    names = [item["name"] for item in payload]
    assert names == ["Kai", "Nia"]
