from __future__ import annotations

ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _number_from_tokens(tokens: list[str]) -> str | None:
    whole: int | None = None
    fraction: list[str] = []
    in_fraction = False
    for token in tokens:
        if token in {".", "point"}:
            in_fraction = True
            continue
        if token.replace(".", "", 1).isdigit():
            if in_fraction:
                fraction.append(token.replace(".", ""))
            else:
                whole = int(token) if whole is None else int(f"{whole}{token}")
            continue
        if token in TENS:
            value = TENS[token]
            whole = value if whole is None else whole + value
            continue
        if token in ONES:
            value = ONES[token]
            if in_fraction:
                fraction.append(str(value))
            elif whole is not None and whole >= 20 and whole % 10 == 0:
                whole += value
            elif whole is None:
                whole = value
            else:
                whole = int(f"{whole}{value}")
    if whole is None and not fraction:
        return None
    if fraction:
        return f"{whole or 0}.{''.join(fraction)}"
    return str(whole)


def parse_voice_proposal(transcript: str) -> dict[str, str] | None:
    """Turn a transcript into an untrusted draft. Never mutates Brew-Day state."""
    if not transcript or not transcript.strip():
        return None
    lowered = transcript.lower().strip()
    tokens = lowered.replace("-", " ").split()
    value = _number_from_tokens(tokens)
    field = "MASH_PH"
    unit = "pH"
    if "gravity" in lowered:
        field = "MASH_GRAVITY"
        unit = "SG"
    if value is None:
        return None
    return {
        "transcript": transcript,
        "field": field,
        "value": value,
        "unit": unit,
        "action": "record_measurement",
        "committed": "false",
    }
