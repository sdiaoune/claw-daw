from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


CueType = Literal["dropout", "fill"]
CueAt = Literal["start", "end"]


@dataclass(frozen=True)
class CueSpec:
    """A minimal arrangement cue.

    - dropout: remove clips for target tracks in a window at a section boundary
    - fill: swap to a fill pattern for target tracks in a window at a section boundary

    Track selection is by indices.
    """

    type: CueType
    at: CueAt = "end"
    bars: int = 1
    tracks: list[int] = field(default_factory=list)

    # fill-only
    pattern: str | None = None


@dataclass(frozen=True)
class SectionSpec:
    name: str
    bars: int
    cues: list[CueSpec] = field(default_factory=list)


@dataclass(frozen=True)
class ArrangeSpec:
    """Structure/arrangement specification.

    Minimal v1 format:

    version: 1
    sections:
      - name: intro
        bars: 4
        cues:
          - type: dropout
            at: end
            bars: 1
            tracks: [1,2]
          - type: fill
            at: end
            bars: 1
            tracks: [0]
            pattern: drums_fill

    Optional:
    - seed: int (reserved for future; currently unused)
    - base_patterns: {"0": "drums_main", "1": "bass_main"}  (track_index -> pattern name)
    """

    version: int = 1
    seed: int = 0
    sections: list[SectionSpec] = field(default_factory=list)
    base_patterns: dict[int, str] = field(default_factory=dict)


def _as_int(x: Any, *, default: int | None = None) -> int:
    if x is None:
        if default is None:
            raise ValueError("expected int")
        return default
    try:
        return int(x)
    except Exception as e:
        raise ValueError(f"expected int, got: {x!r}") from e


def _as_str(x: Any, *, default: str | None = None) -> str:
    if x is None:
        if default is None:
            raise ValueError("expected str")
        return default
    s = str(x)
    if not s:
        if default is None:
            raise ValueError("expected non-empty str")
        return default
    return s


def _as_int_list(x: Any) -> list[int]:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return [int(v) for v in x]
    # allow single int
    return [int(x)]


def load_arrange_spec(path: str | Path) -> ArrangeSpec:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")

    if p.suffix.lower() in {".json"}:
        data = json.loads(raw)
    else:
        data = yaml.safe_load(raw)

    if not isinstance(data, dict):
        raise ValueError("arrange spec must be a mapping at top-level")

    version = _as_int(data.get("version", 1), default=1)
    if version != 1:
        raise ValueError(f"unsupported arrange spec version: {version}")

    seed = _as_int(data.get("seed", 0), default=0)

    # base_patterns: allow either int keys or string keys
    base_patterns_raw = data.get("base_patterns", {}) or {}
    if not isinstance(base_patterns_raw, dict):
        raise ValueError("base_patterns must be a mapping")
    base_patterns: dict[int, str] = {}
    for k, v in base_patterns_raw.items():
        try:
            ki = int(k)
        except Exception as e:
            raise ValueError(f"base_patterns key must be track index int, got: {k!r}") from e
        base_patterns[ki] = _as_str(v)

    sections_raw = data.get("sections", [])
    if not isinstance(sections_raw, list) or not sections_raw:
        raise ValueError("sections must be a non-empty list")

    sections: list[SectionSpec] = []
    for s in sections_raw:
        if not isinstance(s, dict):
            raise ValueError("each section must be a mapping")
        name = _as_str(s.get("name"))
        bars = _as_int(s.get("bars"))
        if bars <= 0:
            raise ValueError("section bars must be > 0")

        cues_raw = s.get("cues", []) or []
        if not isinstance(cues_raw, list):
            raise ValueError("section.cues must be a list")
        cues: list[CueSpec] = []
        for c in cues_raw:
            if not isinstance(c, dict):
                raise ValueError("each cue must be a mapping")
            ctype = _as_str(c.get("type")).lower()
            if ctype not in {"dropout", "fill"}:
                raise ValueError(f"unknown cue type: {ctype}")
            at = _as_str(c.get("at", "end"), default="end").lower()
            if at not in {"start", "end"}:
                raise ValueError(f"cue.at must be 'start' or 'end', got: {at}")
            cbars = _as_int(c.get("bars", 1), default=1)
            if cbars <= 0:
                raise ValueError("cue.bars must be > 0")
            tracks = _as_int_list(c.get("tracks"))
            if not tracks:
                raise ValueError("cue.tracks must be a non-empty list of track indices")
            pattern = c.get("pattern", None)
            if ctype == "fill":
                pat = _as_str(pattern)
            else:
                pat = None
            cues.append(CueSpec(type=ctype, at=at, bars=cbars, tracks=tracks, pattern=pat))

        sections.append(SectionSpec(name=name, bars=bars, cues=cues))

    return ArrangeSpec(version=version, seed=seed, sections=sections, base_patterns=base_patterns)
