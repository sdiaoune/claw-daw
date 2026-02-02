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


# Default mappings. These are intentionally simple and GM-compatible.
DEFAULT_ROLE_SOUNDS: dict[str, TrackSound] = {
    "drums": TrackSound(sampler="drums", sampler_preset="tight"),
    "bass": TrackSound(sampler="808", sampler_preset="round"),
    "keys": TrackSound(program=parse_program("electric_piano")),
    "pad": TrackSound(program=parse_program("pad")),
    "lead": TrackSound(program=parse_program("lead")),
}


def select_track_sound(
    role: str,
    *,
    style: StyleName,
    mood: str | None = None,
    overrides: dict[str, TrackSound] | None = None,
) -> TrackSound:
    """Default sound selection hook.

    You can override per role by passing overrides.
    """

    role_key = role.strip().lower()
    if overrides and role_key in overrides:
        return overrides[role_key]

    # Lightweight style-aware tweaks.
    base = DEFAULT_ROLE_SOUNDS.get(role_key, TrackSound(program=parse_program("piano")))

    if role_key == "bass" and style in {"house", "techno"}:
        # Prefer an electric bass over 808 in faster dance styles.
        return TrackSound(program=parse_program("electric_bass"))

    if role_key == "pad" and style == "lofi":
        # Softer pad choice.
        return TrackSound(program=parse_program("synth_strings"))

    if role_key == "keys" and mood and "dark" in mood.lower():
        return TrackSound(program=parse_program("piano"))

    return base
