DEFAULT_VOICE_CONFIG = {
    "narrator_voice": "narrator_default",
    "male_default_voice": "male_default",
    "female_default_voice": "female_default",
    "neutral_default_voice": "neutral_default",
    "unknown_default_voice": "unknown_default",
}

INTERNAL_THOUGHT_VOICE_POLICIES = ("character", "narrator", "thought_voice")


def _normalize_internal_thought_voice_policy(raw_policy: object | None) -> str:
    policy = str(raw_policy).strip().lower() if raw_policy is not None else "character"
    if policy in INTERNAL_THOUGHT_VOICE_POLICIES:
        return policy
    return "character"


def _resolve_dialogue_like_voice(
    speaker: str,
    character_lookup: dict[str, dict[str, str | None]],
    merged_config: dict[str, str],
) -> tuple[str, str]:
    if not speaker or speaker.lower() == "unknown":
        return merged_config["unknown_default_voice"], "unknown"

    entry = character_lookup.get(speaker.lower())
    if entry is None:
        return merged_config["unknown_default_voice"], "unknown"

    if entry.get("voice_id"):
        return str(entry["voice_id"]), str(entry.get("gender", "unknown"))

    gender = str(entry.get("gender", "unknown")).lower()
    if gender == "male":
        return merged_config["male_default_voice"], gender
    if gender == "female":
        return merged_config["female_default_voice"], gender
    if gender == "neutral":
        return merged_config["neutral_default_voice"], gender
    if gender == "unknown":
        return merged_config["unknown_default_voice"], gender
    return merged_config["unknown_default_voice"], gender


def build_effective_voice_config(
    voice_config: dict[str, str] | None,
    *,
    default_narrator_voice: str | None = None,
    default_male_voice: str | None = None,
    default_female_voice: str | None = None,
    default_neutral_voice: str | None = None,
    default_unknown_voice: str | None = None,
) -> dict[str, str]:
    merged = DEFAULT_VOICE_CONFIG | (voice_config or {})
    if default_narrator_voice:
        merged["narrator_voice"] = default_narrator_voice
    if default_male_voice:
        merged["male_default_voice"] = default_male_voice
    if default_female_voice:
        merged["female_default_voice"] = default_female_voice
    if default_neutral_voice:
        merged["neutral_default_voice"] = default_neutral_voice
    if default_unknown_voice:
        merged["unknown_default_voice"] = default_unknown_voice
    return merged


def resolve_voice(
    segment_type: str,
    speaker: str,
    character_lookup: dict[str, dict[str, str | None]],
    voice_config: dict[str, str],
) -> tuple[str, str]:
    merged_config = DEFAULT_VOICE_CONFIG | (voice_config or {})
    narrator_voice = merged_config["narrator_voice"]
    normalized_speaker = speaker.strip().lower()
    internal_thought_policy = _normalize_internal_thought_voice_policy(
        merged_config.get("internal_thought_voice_policy")
    )

    if segment_type == "dialogue":
        return _resolve_dialogue_like_voice(
            speaker=normalized_speaker,
            character_lookup=character_lookup,
            merged_config=merged_config,
        )

    if segment_type == "internal thought":
        if internal_thought_policy == "character":
            return _resolve_dialogue_like_voice(
                speaker=normalized_speaker,
                character_lookup=character_lookup,
                merged_config=merged_config,
            )
        if internal_thought_policy == "narrator":
            return narrator_voice, "unknown"
        if internal_thought_policy == "thought_voice":
            thought_voice = str(merged_config.get("thought_voice", narrator_voice)).strip()
            return (thought_voice or narrator_voice), "unknown"

        return narrator_voice, "unknown"

    return narrator_voice, "unknown"
