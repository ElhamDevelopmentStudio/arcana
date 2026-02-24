DEFAULT_VOICE_CONFIG = {
    "narrator_voice": "narrator_default",
    "male_default_voice": "male_default",
    "female_default_voice": "female_default",
}


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
        return narrator_voice, "unknown"

    entry = character_lookup.get(speaker.lower())
    if entry is None:
        return narrator_voice, "unknown"

    if entry.get("voice_id"):
        return str(entry["voice_id"]), str(entry.get("gender", "unknown"))

    gender = str(entry.get("gender", "unknown")).lower()
    if gender == "male":
        return merged_config["male_default_voice"], gender
    if gender == "female":
        return merged_config["female_default_voice"], gender
    return narrator_voice, gender
