from __future__ import annotations

# Minimal General MIDI program map (0-127). This is not exhaustive, but covers common instruments.
# Program numbers here are **0-based** to match MIDI program_change.
GM_PROGRAMS: dict[str, int] = {
    "piano": 0,
    "acoustic_grand_piano": 0,
    "bright_piano": 1,
    "electric_piano": 4,
    "harpsichord": 6,
    "clav": 7,
    "celesta": 8,
    "glockenspiel": 9,
    "music_box": 10,
    "vibraphone": 11,
    "marimba": 12,
    "xylophone": 13,
    "organ": 16,
    "church_organ": 19,
    "accordion": 21,
    "guitar": 24,
    "acoustic_guitar": 24,
    "electric_guitar": 27,
    "bass": 32,
    "acoustic_bass": 32,
    "electric_bass": 33,
    "violin": 40,
    "strings": 48,
    "string_ensemble": 48,
    "synth_strings": 50,
    "choir": 52,
    "trumpet": 56,
    "trombone": 57,
    "tuba": 58,
    "sax": 64,
    "alto_sax": 65,
    "tenor_sax": 66,
    "oboe": 68,
    "clarinet": 71,
    "flute": 73,
    "lead": 80,
    "synth_lead": 80,
    "pad": 88,
    "synth_pad": 88,
    "fx": 96,
    "drums": 0,  # NOTE: GM drums are typically on channel 10, not a program.
}


def parse_program(token: str) -> int:
    """Parse a MIDI program token.

    Accepts:
      - integer 0-127 (0-based)
      - integer 1-128 (1-based; will be converted)
      - GM name key from GM_PROGRAMS (case-insensitive)
    """

    t = token.strip().lower().replace(" ", "_")
    if t in GM_PROGRAMS:
        return GM_PROGRAMS[t]

    n = int(t)
    if 0 <= n <= 127:
        return n
    if 1 <= n <= 128:
        return n - 1
    raise ValueError("program must be 0-127 (or 1-128), or a GM name")
