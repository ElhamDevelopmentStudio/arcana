DEFAULT_VOICE_CONFIG = {
    "narrator_voice": "narrator_default",
    "male_default_voice": "male_default",
    "female_default_voice": "female_default",
    "neutral_default_voice": "neutral_default",
    "unknown_default_voice": "unknown_default",
}


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

    if segment_type != "dialogue":
        return narrator_voice, "unknown"

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
