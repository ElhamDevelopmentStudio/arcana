from app.services.voice import DEFAULT_VOICE_CONFIG, resolve_voice


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
