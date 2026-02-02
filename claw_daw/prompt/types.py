from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


StyleName = Literal["hiphop", "lofi", "house", "techno", "ambient", "unknown"]


@dataclass(frozen=True)
class NoveltyConstraints:
    """Constraints applied when iterating prompt→song variants."""

    # If provided, we try to ensure similarity to the previous iteration is <= this.
    max_similarity: float = 0.92


@dataclass
class Brief:
    """A structured producer brief derived from a natural-language prompt."""

    prompt: str
    title: str = "untitled"
    style: StyleName = "unknown"
    bpm: int | None = None
    key: str | None = None
    mood: str | None = None
    length_bars: int = 24

    # High-level palette roles; used by the script generator.
    roles: list[str] = field(default_factory=lambda: ["drums", "bass", "keys", "pad", "lead"])

    novelty: NoveltyConstraints = field(default_factory=NoveltyConstraints)


@dataclass(frozen=True)
class StylePreset:
    style: StyleName
    bpm_default: int
    swing_percent: int
    drum_density: float
    mastering_preset: str
    prefer_sampler_808: bool = True
