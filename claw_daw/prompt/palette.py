from __future__ import annotations

from dataclasses import dataclass

from claw_daw.prompt.types import StyleName
from claw_daw.util.gm import parse_program


@dataclass(frozen=True)
class TrackSound:
    """How a role should be realized in claw-daw."""

    # Either set sampler to drums/808, or use a GM program.
    sampler: str | None = None
    sampler_preset: str | None = None
    program: int | None = None


@dataclass(frozen=True)
class TrackMix:
    """Per-track mixer defaults (GM-ish CCs)."""

    volume: int | None = None
    pan: int | None = None
    reverb: int | None = None
    chorus: int | None = None


@dataclass(frozen=True)
class TrackPreset:
    sound: TrackSound
    mix: TrackMix


# Default mappings. These are intentionally simple and GM-compatible.
DEFAULT_ROLE_SOUNDS: dict[str, TrackSound] = {
    "drums": TrackSound(sampler="drums", sampler_preset="tight"),
    "bass": TrackSound(sampler="808", sampler_preset="round"),
    "keys": TrackSound(program=parse_program("electric_piano_1")),
    "pad": TrackSound(program=parse_program("warm_pad")),
    "lead": TrackSound(program=parse_program("square_lead")),
}

DEFAULT_ROLE_MIX: dict[str, TrackMix] = {
    "drums": TrackMix(volume=112, pan=64, reverb=10, chorus=0),
    "bass": TrackMix(volume=104, pan=64, reverb=0, chorus=0),
    "keys": TrackMix(volume=92, pan=62, reverb=30, chorus=10),
    "pad": TrackMix(volume=86, pan=66, reverb=48, chorus=18),
    "lead": TrackMix(volume=94, pan=70, reverb=22, chorus=6),
}

# Style-aware role presets. Keep these small + deterministic.
STYLE_ROLE_SOUNDS: dict[StyleName, dict[str, TrackSound]] = {
    "trap": {
        "bass": TrackSound(sampler="808", sampler_preset="round"),
        "keys": TrackSound(program=parse_program("piano")),
        "lead": TrackSound(program=parse_program("saw_lead")),
    },
    "boom_bap": {
        "bass": TrackSound(program=parse_program("acoustic_bass")),
        "keys": TrackSound(program=parse_program("electric_piano_2")),
    },
    "lofi": {
        "bass": TrackSound(program=parse_program("acoustic_bass")),
        "keys": TrackSound(program=parse_program("electric_piano_1")),
        "pad": TrackSound(program=parse_program("synth_strings")),
    },
    "house": {
        "bass": TrackSound(program=parse_program("synth_bass_1")),
        "keys": TrackSound(program=parse_program("drawbar_organ")),
        "lead": TrackSound(program=parse_program("saw_lead")),
    },
    "techno": {
        "bass": TrackSound(program=parse_program("synth_bass_2")),
        "keys": TrackSound(program=parse_program("organ")),
        "lead": TrackSound(program=parse_program("saw_lead")),
    },
    "ambient": {
        "bass": TrackSound(program=parse_program("synth_bass_1")),
        "pad": TrackSound(program=parse_program("warm_pad")),
        "keys": TrackSound(program=parse_program("electric_piano_2")),
    },
    "hiphop": {
        "bass": TrackSound(program=parse_program("synth_bass_1")),
        "keys": TrackSound(program=parse_program("electric_piano_2")),
    },
}

STYLE_ROLE_MIX: dict[StyleName, dict[str, TrackMix]] = {
    "trap": {
        "drums": TrackMix(volume=114, pan=64, reverb=6, chorus=0),
        "bass": TrackMix(volume=108, pan=64, reverb=0, chorus=0),
        "keys": TrackMix(volume=88, pan=60, reverb=20, chorus=6),
        "lead": TrackMix(volume=92, pan=70, reverb=18, chorus=6),
    },
    "house": {
        "drums": TrackMix(volume=112, pan=64, reverb=10, chorus=0),
        "bass": TrackMix(volume=102, pan=64, reverb=0, chorus=0),
        "keys": TrackMix(volume=92, pan=60, reverb=34, chorus=12),
    },
    "boom_bap": {
        "drums": TrackMix(volume=110, pan=64, reverb=14, chorus=0),
        "bass": TrackMix(volume=100, pan=64, reverb=4, chorus=0),
        "keys": TrackMix(volume=90, pan=62, reverb=26, chorus=10),
    },
}


def select_track_sound(
    role: str,
    *,
    style: StyleName,
    mood: str | None = None,
    overrides: dict[str, TrackSound] | None = None,
) -> TrackSound:
    """Select only the sound (sampler/program) for a role."""

    role_key = role.strip().lower()
    if overrides and role_key in overrides:
        return overrides[role_key]

    # Base default, then style override, then mood tweaks.
    base = DEFAULT_ROLE_SOUNDS.get(role_key, TrackSound(program=parse_program("piano")))
    style_over = STYLE_ROLE_SOUNDS.get(style, {}).get(role_key)
    out = style_over or base

    if role_key == "keys" and mood and "dark" in mood.lower():
        return TrackSound(program=parse_program("piano"))

    return out


def select_track_mix(
    role: str,
    *,
    style: StyleName,
    overrides: dict[str, TrackMix] | None = None,
) -> TrackMix:
    role_key = role.strip().lower()
    if overrides and role_key in overrides:
        return overrides[role_key]

    base = DEFAULT_ROLE_MIX.get(role_key, TrackMix())
    style_over = STYLE_ROLE_MIX.get(style, {}).get(role_key)
    return style_over or base


def select_track_preset(
    role: str,
    *,
    style: StyleName,
    mood: str | None = None,
    sound_overrides: dict[str, TrackSound] | None = None,
    mix_overrides: dict[str, TrackMix] | None = None,
) -> TrackPreset:
    return TrackPreset(
        sound=select_track_sound(role, style=style, mood=mood, overrides=sound_overrides),
        mix=select_track_mix(role, style=style, overrides=mix_overrides),
    )
