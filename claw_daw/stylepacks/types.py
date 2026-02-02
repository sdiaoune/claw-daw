from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


StylepackName = Literal["trap_2020s", "boom_bap", "house"]


@dataclass
class BeatSpec:
    """A small, reproducible spec that can be compiled into a headless script."""

    name: str
    stylepack: StylepackName

    # Determinism
    seed: int = 0
    max_attempts: int = 6

    # Length target (we keep it simple: bars)
    length_bars: int = 32

    # Tempo/feel overrides (optional)
    bpm: int | None = None
    swing_percent: int | None = None

    # Knobs (3–6 per stylepack)
    knobs: dict[str, Any] = field(default_factory=dict)

    # Scoring / iteration
    score_threshold: float = 0.60
    max_similarity: float = 0.92


@dataclass(frozen=True)
class AttemptReport:
    attempt: int
    seed: int
    knobs: dict[str, Any]
    acceptance_ok: bool
    acceptance_errors: list[str]
    similarity_to_prev: float | None
    spectral: dict[str, Any] | None
    score: float | None
    chosen: bool = False
