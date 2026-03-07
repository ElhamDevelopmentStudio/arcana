from app.services.gender_inference import infer_character_genders


def test_unit_gender_inference_prefers_honorific_titles() -> None:
    results = infer_character_genders(
        character_names=["Milo", "Nina", "Kael"],
        chapter_texts=[
            "Mr. Milo strode into the hall. The evening was dark.",
            "Miss Nina watched from the stairs. She said nothing.",
            "Kael wandered in with the crowd.",
        ],
    )

    by_name = {entry["name"]: entry for entry in results}
    assert by_name["Milo"]["inferred_gender"] == "male"
    assert by_name["Milo"]["confidence"] >= 0.75
    assert by_name["Nina"]["inferred_gender"] == "female"
    assert by_name["Nina"]["confidence"] >= 0.75
    assert by_name["Kael"]["inferred_gender"] == "unknown"


def test_unit_gender_inference_from_pronoun_context() -> None:
    results = infer_character_genders(
        character_names=["Lena", "Orin"],
        chapter_texts=[
            "Lena, she smiled before the crowd.",
            "Orin, he muttered under his breath.",
        ],
    )

    by_name = {entry["name"]: entry for entry in results}
    assert by_name["Lena"]["inferred_gender"] == "female"
    assert by_name["Lena"]["confidence"] >= 0.7
    assert by_name["Orin"]["inferred_gender"] == "male"
    assert by_name["Orin"]["confidence"] >= 0.7


def test_unit_gender_inference_returns_unknown_for_conflicting_evidence() -> None:
    results = infer_character_genders(
        character_names=["Rin"],
        chapter_texts=["Rin, she admitted it. Later, Rin, he claimed it was over."],
    )

    assert len(results) == 1
    assert results[0]["name"] == "Rin"
    assert results[0]["inferred_gender"] == "unknown"
    assert results[0]["confidence"] == 0.0


def test_unit_gender_inference_empty_input() -> None:
    assert infer_character_genders(character_names=[], chapter_texts=[]) == []
