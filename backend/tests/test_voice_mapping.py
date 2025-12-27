from app.services.voice import (
    DEFAULT_VOICE_CONFIG,
    _normalize_internal_thought_voice_policy,
    resolve_voice,
)


def test_unit_resolve_voice_maps_gender_defaults_to_neutral_and_unknown_buckets() -> None:
    character_lookup = {
        "neo": {"gender": "neutral", "voice_id": None},
        "ava": {"gender": "unknown", "voice_id": None},
    }
    config = {
        "narrator_voice": "narrator",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral_bucket",
        "unknown_default_voice": "unknown_bucket",
    }

    neutral_voice, neutral_gender = resolve_voice(
        segment_type="dialogue",
        speaker="Neo",
        character_lookup=character_lookup,
        voice_config=config,
    )
    unknown_voice, unknown_gender = resolve_voice(
        segment_type="dialogue",
        speaker="Ava",
        character_lookup=character_lookup,
        voice_config=config,
    )

    assert neutral_voice == "neutral_bucket"
    assert neutral_gender == "neutral"
    assert unknown_voice == "unknown_bucket"
    assert unknown_gender == "unknown"


def test_unit_resolve_voice_falls_back_to_default_mapping_when_extended_defaults_are_missing() -> None:
    character_lookup = {
        "sam": {"gender": "neutral", "voice_id": None},
        "nina": {"gender": "unknown", "voice_id": None},
    }
    config = {
        "narrator_voice": "narr",
        "male_default_voice": "m",
        "female_default_voice": "f",
    }

    neutral_voice, _ = resolve_voice(
        segment_type="dialogue",
        speaker="Sam",
        character_lookup=character_lookup,
        voice_config=config,
    )
    unknown_voice, _ = resolve_voice(
        segment_type="dialogue",
        speaker="Nina",
        character_lookup=character_lookup,
        voice_config=config,
    )

    assert neutral_voice == DEFAULT_VOICE_CONFIG["neutral_default_voice"]
    assert unknown_voice == DEFAULT_VOICE_CONFIG["unknown_default_voice"]


def test_unit_resolve_voice_defaults_unknown_speaker_to_unknown_bucket() -> None:
    neutral_voice, gender = resolve_voice(
        segment_type="dialogue",
        speaker="",
        character_lookup={},
        voice_config={},
    )

    assert neutral_voice == DEFAULT_VOICE_CONFIG["unknown_default_voice"]
    assert gender == "unknown"


def test_unit_resolve_voice_internal_thought_uses_character_policy() -> None:
    character_lookup = {
        "kai": {"gender": "male", "voice_id": None},
    }
    config = {
        "narrator_voice": "narrator",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral",
        "unknown_default_voice": "unknown_default",
        "internal_thought_voice_policy": "character",
    }

    internal_voice, gender = resolve_voice(
        segment_type="internal thought",
        speaker="Kai",
        character_lookup=character_lookup,
        voice_config=config,
    )

    assert internal_voice == "male"
    assert gender == "male"


def test_unit_resolve_voice_internal_thought_uses_narrator_policy() -> None:
    config = {
        "narrator_voice": "narrator",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral",
        "unknown_default_voice": "unknown_default",
        "internal_thought_voice_policy": "narrator",
    }

    internal_voice, gender = resolve_voice(
        segment_type="internal thought",
        speaker="Kai",
        character_lookup={},
        voice_config=config,
    )

    assert internal_voice == "narrator"
    assert gender == "unknown"


def test_unit_resolve_voice_internal_thought_uses_thought_voice_policy() -> None:
    config = {
        "narrator_voice": "narrator",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral",
        "unknown_default_voice": "unknown_default",
        "internal_thought_voice_policy": "thought_voice",
        "thought_voice": "thought_default",
    }

    internal_voice, gender = resolve_voice(
        segment_type="internal thought",
        speaker="",
        character_lookup={},
        voice_config=config,
    )

    assert internal_voice == "thought_default"
    assert gender == "unknown"


def test_unit_normalize_internal_thought_voice_policy_defaults_to_character_for_bad_values() -> None:
    assert _normalize_internal_thought_voice_policy("thought_voice") == "thought_voice"
    assert _normalize_internal_thought_voice_policy("CHARACTER") == "character"
    assert _normalize_internal_thought_voice_policy("mystery") == "character"
    assert _normalize_internal_thought_voice_policy("") == "character"
    assert _normalize_internal_thought_voice_policy(None) == "character"


def test_unit_resolve_voice_internal_thought_defaults_to_narrator_when_policy_thought_voice_and_no_voice() -> None:
    config = {
        "narrator_voice": "narrator_voice",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral",
        "unknown_default_voice": "unknown_default",
        "internal_thought_voice_policy": "thought_voice",
    }

    internal_voice, gender = resolve_voice(
        segment_type="internal thought",
        speaker="Kai",
        character_lookup={},
        voice_config=config,
    )

    assert internal_voice == "narrator_voice"
    assert gender == "unknown"


def test_unit_resolve_voice_unknown_segment_type_uses_narrator_fallback() -> None:
    config = {
        "narrator_voice": "narrator_voice",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral",
        "unknown_default_voice": "unknown_default",
    }

    fallback_voice, fallback_gender = resolve_voice(
        segment_type="flashback",
        speaker="Kai",
        character_lookup={"kai": {"gender": "male", "voice_id": "explicit"}},
        voice_config=config,
    )

    assert fallback_voice == "narrator_voice"
    assert fallback_gender == "unknown"


def test_unit_resolve_voice_unknown_lookup_falls_back_for_custom_gender_values() -> None:
    config = {
        "narrator_voice": "narrator",
        "male_default_voice": "male",
        "female_default_voice": "female",
        "neutral_default_voice": "neutral",
        "unknown_default_voice": "unknown_default",
    }
    character_lookup = {"kai": {"gender": "custom", "voice_id": None}}

    fallback_voice, fallback_gender = resolve_voice(
        segment_type="dialogue",
        speaker="Kai",
        character_lookup=character_lookup,
        voice_config=config,
    )

    assert fallback_voice == "unknown_default"
    assert fallback_gender == "custom"
