from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from claw_daw.genre_packs.v1 import PackName


@dataclass(frozen=True)
class Stylepack:
    name: str
    title: str
    pack: PackName
    bpm_default: int
    bpm_min: int
    bpm_max: int
    swing_percent: int
    # default generation knobs
    default_knobs: dict[str, Any]
    # knobs docs (for humans/agents)
    knobs: dict[str, str]


def list_stylepacks_v1() -> list[Stylepack]:
    return [
        Stylepack(
            name="trap_2020s",
            title="2020s Trap (bouncy)",
            pack="trap",
            bpm_default=150,
            bpm_min=140,
            bpm_max=165,
            swing_percent=18,
            default_knobs={
                "drum_density": 0.80,
                "drum_kit": "trap_hard",
                "humanize_timing": 6,
                "humanize_velocity": 8,
                "lead_density": 0.55,
            },
            knobs={
                "drum_density": "0..1 hat/percussion density",
                "drum_kit": "trap_hard|house_clean|boombap_dusty|gm_basic",
                "humanize_timing": "ticks of timing humanize (0..20)",
                "humanize_velocity": "velocity randomization amount (0..25)",
                "lead_density": "0..1 (lower => sparser top melody)",
            },
        ),
        Stylepack(
            name="boom_bap",
            title="Boom Bap (classic)",
            pack="boom_bap",
            bpm_default=92,
            bpm_min=80,
            bpm_max=105,
            swing_percent=25,
            default_knobs={
                "drum_density": 0.60,
                "drum_kit": "boombap_dusty",
                "humanize_timing": 10,
                "humanize_velocity": 10,
                "lead_density": 0.30,
            },
            knobs={
                "drum_density": "0..1 hat/percussion density",
                "drum_kit": "trap_hard|house_clean|boombap_dusty|gm_basic",
                "humanize_timing": "ticks of timing humanize (0..25)",
                "humanize_velocity": "velocity randomization amount (0..25)",
                "lead_density": "0..1 (lower => sparser top melody)",
            },
        ),
        Stylepack(
            name="house",
            title="House (clean 4x4)",
            pack="house",
            bpm_default=124,
            bpm_min=120,
            bpm_max=130,
            swing_percent=0,
            default_knobs={
                "drum_density": 0.82,
                "drum_kit": "house_clean",
                "humanize_timing": 2,
                "humanize_velocity": 6,
                "lead_density": 0.35,
            },
            knobs={
                "drum_density": "0..1 hat/percussion density",
                "drum_kit": "trap_hard|house_clean|boombap_dusty|gm_basic",
                "humanize_timing": "ticks of timing humanize (0..15)",
                "humanize_velocity": "velocity randomization amount (0..20)",
                "lead_density": "0..1 (lower => sparser top melody)",
            },
        ),
    ]


StylepackName = Literal["trap_2020s", "boom_bap", "house"]


def get_stylepack(name: str) -> Stylepack:
    for sp in list_stylepacks_v1():
        if sp.name == name:
            return sp
    raise KeyError(f"unknown stylepack: {name}")
