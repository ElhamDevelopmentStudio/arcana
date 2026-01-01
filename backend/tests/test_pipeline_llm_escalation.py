from app.services.pipeline import _should_escalate_to_llm


def _build_confident_tag_payload() -> dict[str, object]:
    return {
        "type_state": "certain",
        "speaker_state": "certain",
        "emotion_state": "certain",
        "type_confidence": 0.99,
        "speaker_confidence": 0.95,
        "emotion_confidence": 0.92,
        "summary_tag": {"state": "certain", "confidence": 0.94},
        "tension_contribution": {"state": "certain", "confidence": 0.95},
        "dominance_contribution": {"state": "certain", "confidence": 0.97},
    }


def test_should_not_escalate_to_llm_when_rule_outputs_are_certain() -> None:
    tags = _build_confident_tag_payload()
    assert _should_escalate_to_llm(tags) is False


def test_should_escalate_to_llm_when_any_rule_output_is_uncertain() -> None:
    uncertain_payload = _build_confident_tag_payload()
    uncertain_payload["speaker_state"] = "uncertain"
    assert _should_escalate_to_llm(uncertain_payload) is True


def test_should_escalate_to_llm_when_rule_state_is_missing() -> None:
    incomplete_payload = {
        "type_state": "certain",
    }
    assert _should_escalate_to_llm(incomplete_payload) is True


def test_should_escalate_to_llm_when_confidence_below_threshold() -> None:
    weak_confidence_payload = _build_confident_tag_payload()
    weak_confidence_payload["speaker_confidence"] = 0.42
    assert _should_escalate_to_llm(weak_confidence_payload, confidence_threshold=0.6) is True


def test_should_not_escalate_to_llm_when_confidence_meets_threshold() -> None:
    payload = _build_confident_tag_payload()
    assert _should_escalate_to_llm(payload, confidence_threshold=0.9) is False


def test_should_escalate_to_llm_when_ambiguity_flag_is_raised() -> None:
    ambiguous_payload = _build_confident_tag_payload()
    ambiguous_payload["ambiguity_flags"] = ["ambiguous_speaker_attribution"]
    assert _should_escalate_to_llm(ambiguous_payload) is True


def test_should_not_escalate_to_llm_with_empty_ambiguity_flags() -> None:
    payload = _build_confident_tag_payload()
    payload["ambiguity_flags"] = []
    assert _should_escalate_to_llm(payload) is False
