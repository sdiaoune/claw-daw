from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random
from typing import Any, Protocol

from claw_daw.model.types import Note, Project


class InstrumentPlugin(Protocol):
    id: str

    def presets(self) -> dict[str, dict[str, Any]]:
        ...

    def render(self, project: Project, track_index: int, notes: list[Note], out_wav: str, sr: int) -> None:
        ...


@dataclass
class InstrumentSpecView:
    preset: str
    params: dict[str, Any]
    seed: int


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def param_float(params: dict[str, Any], key: str, default: float, lo: float | None = None, hi: float | None = None) -> float:
    raw = params.get(key, default)
    try:
        v = float(raw)
    except Exception:
        v = float(default)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def param_int(params: dict[str, Any], key: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    raw = params.get(key, default)
    try:
        v = int(raw)
    except Exception:
        v = int(default)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def param_str(params: dict[str, Any], key: str, default: str) -> str:
    raw = params.get(key, default)
    return str(raw).strip() or default


def midi_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


def softclip(x: float, drive: float = 1.0) -> float:
    return math.tanh(x * drive)


def limit_polyphony(notes: list[Note], max_polyphony: int) -> list[Note]:
    if max_polyphony <= 0:
        return []
    out: list[Note] = []
    active_ends: list[int] = []
    for n in sorted(notes, key=lambda nn: (nn.start, nn.pitch)):
        active_ends = [e for e in active_ends if e > n.start]
        if len(active_ends) >= max_polyphony:
            continue
        active_ends.append(n.end)
        out.append(n)
    return out


def apply_limiter(left: list[float], right: list[float], limit: float = 0.98) -> None:
    peak = 0.0
    for i in range(len(left)):
        peak = max(peak, abs(left[i]))
    for i in range(len(right)):
        peak = max(peak, abs(right[i]))
    if peak <= 0 or peak <= limit:
        return
    gain = limit / peak
    for i in range(len(left)):
        left[i] *= gain
    for i in range(len(right)):
        right[i] *= gain


class InstrumentBase:
    id: str = ""

    def presets(self) -> dict[str, dict[str, Any]]:
        return {}

    def _spec(self, project: Project, track_index: int) -> InstrumentSpecView:
        spec = getattr(project.tracks[track_index], "instrument", None)
        preset = "default"
        params: dict[str, Any] = {}
        seed = 0
        if spec is not None:
            preset = str(getattr(spec, "preset", "default") or "default")
            params = dict(getattr(spec, "params", {}) or {})
            seed = int(getattr(spec, "seed", 0) or 0)
        return InstrumentSpecView(preset=preset, params=params, seed=seed)

    def _resolve_params(self, preset: str, overrides: dict[str, Any] | None) -> dict[str, Any]:
        base = dict(self.presets().get(preset, self.presets().get("default", {}) or {}))
        for k, v in (overrides or {}).items():
            base[str(k)] = v
        return base

    def _note_rng(self, base_seed: int, n: Note) -> Random:
        r = (int(base_seed) * 1000003 + int(n.start) * 31 + int(n.pitch) * 131) & 0x7FFFFFFF
        return Random(r)
