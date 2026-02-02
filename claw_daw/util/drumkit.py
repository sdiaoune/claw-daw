from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from claw_daw.model.types import Note, Track


# Drum Kit abstraction v1
# -----------------------
# This is intentionally small and deterministic:
# - Notes may specify a canonical drum *role* instead of a MIDI pitch.
# - Each role maps to 1..N MIDI pitches (layers) with fixed velocity multipliers.
# - Expansion happens at render/export time based on the track's selected kit.


# Canonical drum roles (v1)
# Keep these stable; aliases can be added in ROLE_ALIASES.
CANONICAL_ROLES: tuple[str, ...] = (
    "kick",
    "snare",
    "clap",
    "rim",
    "hat_closed",
    "hat_open",
    "hat_pedal",
    "tom_low",
    "tom_mid",
    "tom_high",
    "crash",
    "ride",
    "perc",
    "shaker",
)


ROLE_ALIASES: dict[str, str] = {
    # common short names
    "bd": "kick",
    "k": "kick",
    "sd": "snare",
    "s": "snare",
    "hh": "hat_closed",
    "ch": "hat_closed",
    "oh": "hat_open",
    "ph": "hat_pedal",
    "rc": "ride",
    "cr": "crash",
    "tomlo": "tom_low",
    "tomm": "tom_mid",
    "tomhi": "tom_high",
    # stylistic naming
    "hat": "hat_closed",
    "hihat": "hat_closed",
}


@dataclass(frozen=True)
class DrumLayer:
    pitch: int
    vel_mul: float = 1.0


@dataclass(frozen=True)
class DrumKit:
    name: str
    roles: dict[str, tuple[DrumLayer, ...]]


def _layers(*xs: tuple[int, float] | int) -> tuple[DrumLayer, ...]:
    out: list[DrumLayer] = []
    for x in xs:
        if isinstance(x, tuple):
            p, m = x
            out.append(DrumLayer(int(p), float(m)))
        else:
            out.append(DrumLayer(int(x), 1.0))
    return tuple(out)


# Built-in kits
# Notes:
# - We use GM-ish percussion numbers so exported MIDI works out of the box.
# - Layering is conservative: it should translate even on plain GM kits.
BUILTIN_KITS: dict[str, DrumKit] = {
    "trap_hard": DrumKit(
        name="trap_hard",
        roles={
            "kick": _layers((36, 1.0), (35, 0.55)),
            "snare": _layers((38, 1.0), (40, 0.65)),
            "clap": _layers((39, 1.0), (38, 0.35)),
            "rim": _layers(37),
            "hat_closed": _layers(42),
            "hat_open": _layers(46),
            "hat_pedal": _layers(44),
            "tom_low": _layers(45),
            "tom_mid": _layers(47),
            "tom_high": _layers(50),
            "crash": _layers(49),
            "ride": _layers(51),
            "perc": _layers(56),
            "shaker": _layers(82),
        },
    ),
    "house_clean": DrumKit(
        name="house_clean",
        roles={
            "kick": _layers((36, 1.0), (35, 0.35)),
            "snare": _layers((39, 0.85), (38, 0.55)),
            "clap": _layers((39, 1.0)),
            "rim": _layers(37),
            "hat_closed": _layers(42),
            "hat_open": _layers(46),
            "hat_pedal": _layers(44),
            "tom_low": _layers(45),
            "tom_mid": _layers(47),
            "tom_high": _layers(50),
            "crash": _layers(57),
            "ride": _layers(51),
            "perc": _layers(75),
            "shaker": _layers(70),
        },
    ),
    "boombap_dusty": DrumKit(
        name="boombap_dusty",
        roles={
            "kick": _layers((36, 1.0), (35, 0.70)),
            "snare": _layers((38, 1.0), (54, 0.40)),
            "clap": _layers((39, 0.75), (38, 0.30)),
            "rim": _layers(37),
            "hat_closed": _layers((42, 1.0)),
            "hat_open": _layers(46),
            "hat_pedal": _layers(44),
            "tom_low": _layers(45),
            "tom_mid": _layers(47),
            "tom_high": _layers(50),
            "crash": _layers(49),
            "ride": _layers(51),
            "perc": _layers(58),
            "shaker": _layers(82),
        },
    ),
    # Back-compat / explicit GM default.
    "gm_basic": DrumKit(
        name="gm_basic",
        roles={
            "kick": _layers(36),
            "snare": _layers(38),
            "clap": _layers(39),
            "rim": _layers(37),
            "hat_closed": _layers(42),
            "hat_open": _layers(46),
            "hat_pedal": _layers(44),
            "tom_low": _layers(45),
            "tom_mid": _layers(47),
            "tom_high": _layers(50),
            "crash": _layers(49),
            "ride": _layers(51),
            "perc": _layers(56),
            "shaker": _layers(82),
        },
    ),
}


KIT_ALIASES: dict[str, str] = {
    "default": "trap_hard",
    "gm": "gm_basic",
    "basic": "gm_basic",
}


def normalize_role(role: str | None) -> str | None:
    if not role:
        return None
    r = str(role).strip().lower()
    r = r.replace("-", "_").replace(" ", "_")
    r = ROLE_ALIASES.get(r, r)
    return r


def normalize_kit_name(name: str | None) -> str | None:
    if name is None:
        return None
    k = str(name).strip().lower()
    k = k.replace("-", "_").replace(" ", "_")
    k = KIT_ALIASES.get(k, k)
    return k


def get_drum_kit(name: str | None) -> DrumKit:
    k = normalize_kit_name(name) or "default"
    k = KIT_ALIASES.get(k, k)
    if k not in BUILTIN_KITS:
        # safest fallback: still deterministic
        k = "trap_hard"
    return BUILTIN_KITS[k]


def list_drum_kits(*, include_internal: bool = False) -> list[str]:
    names = sorted(BUILTIN_KITS.keys())
    if not include_internal:
        names = [n for n in names if n in {"trap_hard", "house_clean", "boombap_dusty"}]
    return names


def expand_role_note(note: Note, *, track: Track) -> list[Note]:
    role = normalize_role(getattr(note, "role", None))
    if not role:
        return [note]

    kit = get_drum_kit(getattr(track, "drum_kit", None))
    layers = kit.roles.get(role)
    if not layers:
        # Unknown role: fall back to existing pitch (or closed hat if pitch is 0).
        if 0 <= int(note.pitch) <= 127 and int(note.pitch) != 0:
            return [note]
        fallback = kit.roles.get("hat_closed", _layers(42))
        layers = fallback

    out: list[Note] = []
    for lay in layers:
        v = int(round(int(note.velocity) * float(lay.vel_mul)))
        v = max(1, min(127, v))
        out.append(
            Note(
                start=int(note.start),
                duration=int(note.duration),
                pitch=int(lay.pitch),
                velocity=v,
                chance=float(getattr(note, "chance", 1.0) or 1.0),
                mute=bool(getattr(note, "mute", False)),
                accent=float(getattr(note, "accent", 1.0) or 1.0),
                glide_ticks=int(getattr(note, "glide_ticks", 0) or 0),
            )
        )
    return out


def expand_role_notes(notes: Iterable[Note], *, track: Track) -> list[Note]:
    out: list[Note] = []
    for n in notes:
        out.extend(expand_role_note(n, track=track))
    return out
