from app.services.pipeline import _should_escalate_to_llm


def _build_confident_tag_payload() -> dict[str, object]:
    return {
        "type_state": "certain",
        "speaker_state": "certain",
        "emotion_state": "certain",
        "summary_tag": {"state": "certain"},
        "tension_contribution": {"state": "certain"},
        "dominance_contribution": {"state": "certain"},
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
