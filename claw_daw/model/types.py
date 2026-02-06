from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from claw_daw.arrange.sections import Section, Variation
from claw_daw.arrange.types import Clip, Pattern


@dataclass(order=True)
class Note:
    """A single MIDI note event in a track.

    Times are in ticks (PPQ), relative to start of the song.

    Optional expression fields are designed to be:
    - deterministic (chance uses a seed)
    - backwards-compatible (omitted when default)
    """

    start: int
    duration: int
    pitch: int
    velocity: int = 100

    # Optional: role-based drum note (expanded via track.drum_kit at render/export).
    # When role is set, pitch is still kept as an int for backwards compatibility,
    # but is treated as a fallback.
    role: str | None = None

    # Optional note-level expressions (all deterministic):
    # - chance: probability [0..1] the note plays
    # - mute: if true, the note never plays
    # - accent: velocity multiplier (e.g. 1.15)
    # - glide_ticks: per-note 808 glide override (sampler-only)
    chance: float = 1.0
    mute: bool = False
    accent: float = 1.0
    glide_ticks: int = 0

    def __post_init__(self) -> None:
        if not (0 <= self.pitch <= 127):
            raise ValueError(f"pitch out of range: {self.pitch}")
        if self.role is not None:
            # Keep role as a normalized-ish string. Full validation happens elsewhere.
            r = str(self.role).strip()
            self.role = r if r else None
        if not (1 <= self.velocity <= 127):
            raise ValueError(f"velocity out of range: {self.velocity}")
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")
        try:
            self.chance = float(self.chance)
        except Exception:
            self.chance = 1.0
        self.chance = max(0.0, min(1.0, self.chance))
        self.mute = bool(self.mute)
        try:
            self.accent = float(self.accent)
        except Exception:
            self.accent = 1.0
        if self.accent <= 0:
            self.accent = 1.0
        try:
            self.glide_ticks = int(self.glide_ticks)
        except Exception:
            self.glide_ticks = 0
        if self.glide_ticks < 0:
            self.glide_ticks = 0

    @property
    def end(self) -> int:
        return self.start + self.duration

    def effective_velocity(self) -> int:
        v = int(round(self.velocity * float(self.accent)))
        return max(1, min(127, v))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "start": self.start,
            "duration": self.duration,
            "pitch": self.pitch,
            "velocity": self.velocity,
        }
        if self.role:
            d["role"] = str(self.role)
        if self.mute:
            d["mute"] = True
        if self.chance != 1.0:
            d["chance"] = float(self.chance)
        if self.accent != 1.0:
            d["accent"] = float(self.accent)
        if self.glide_ticks:
            d["glide_ticks"] = int(self.glide_ticks)
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Note":
        return Note(
            start=int(d["start"]),
            duration=int(d["duration"]),
            pitch=int(d.get("pitch", 0)),
            velocity=int(d.get("velocity", 100)),
            role=(str(d.get("role")).strip() if d.get("role", None) is not None else None),
            chance=float(d.get("chance", 1.0) or 1.0),
            mute=bool(d.get("mute", False)),
            accent=float(d.get("accent", 1.0) or 1.0),
            glide_ticks=int(d.get("glide_ticks", 0) or 0),
        )


@dataclass
class InstrumentSpec:
    id: str
    preset: str = "default"
    params: dict[str, Any] = field(default_factory=dict)
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "preset": str(self.preset),
            "params": dict(self.params or {}),
            "seed": int(self.seed),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "InstrumentSpec":
        return InstrumentSpec(
            id=str(d.get("id", "")).strip(),
            preset=str(d.get("preset", "default") or "default"),
            params=dict(d.get("params", {}) or {}),
            seed=int(d.get("seed", 0) or 0),
        )


@dataclass
class SamplePackSpec:
    id: str | None = None
    path: str | None = None
    seed: int = 0
    gain_db: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "seed": int(self.seed),
            "gain_db": float(self.gain_db),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SamplePackSpec":
        return SamplePackSpec(
            id=(str(d.get("id")).strip() if d.get("id", None) is not None else None),
            path=(str(d.get("path")).strip() if d.get("path", None) is not None else None),
            seed=int(d.get("seed", 0) or 0),
            gain_db=float(d.get("gain_db", 0.0) or 0.0),
        )


@dataclass
class Track:
    name: str
    channel: int  # 0-15
    program: int = 0  # GM patch 0-127
    volume: int = 100  # CC7 0-127
    pan: int = 64  # CC10 0-127 (64 center)
    reverb: int = 0  # CC91 0-127
    chorus: int = 0  # CC93 0-127

    # Optional sampler mode (rendered with claw_daw.audio.sampler, bypassing FluidSynth)
    # Supported: None, "drums", "808".
    sampler: str | None = None

    # Optional native instrument plugin (offline render-only).
    instrument: InstrumentSpec | None = None

    # Optional sample-pack drums (role-based, offline render-only).
    sample_pack: SamplePackSpec | None = None

    # Drum kit name for role-based drum notes (sampler and MIDI export).
    # Built-ins include: trap_hard, house_clean, boombap_dusty.
    drum_kit: str = "trap_hard"

    # Sampler preset (built-in, deterministic). Examples: "tight", "hard", "air", "clean", "dist".
    sampler_preset: str = "default"

    # Sampler-only: 808 glide/portamento time expressed in ticks.
    glide_ticks: int = 0

    # Optional deterministic humanize (applied on export/render).
    humanize_timing: int = 0
    humanize_velocity: int = 0
    humanize_seed: int = 0

    # Optional bus assignment for mix routing.
    # Common conventions: drums|bass|music|vox.
    bus: str = "music"

    # legacy linear notes (still supported)
    notes: list[Note] = field(default_factory=list)

    # arrangement
    patterns: dict[str, Pattern] = field(default_factory=dict)
    clips: list[Clip] = field(default_factory=list)

    mute: bool = False
    solo: bool = False

    def __post_init__(self) -> None:
        if not (0 <= self.channel <= 15):
            raise ValueError(f"channel out of range: {self.channel}")
        if not (0 <= self.program <= 127):
            raise ValueError(f"program out of range: {self.program}")
        if not (0 <= self.volume <= 127):
            raise ValueError(f"volume out of range: {self.volume}")
        if not (0 <= self.pan <= 127):
            raise ValueError(f"pan out of range: {self.pan}")
        if not (0 <= self.reverb <= 127):
            raise ValueError(f"reverb out of range: {self.reverb}")
        if not (0 <= self.chorus <= 127):
            raise ValueError(f"chorus out of range: {self.chorus}")

    def to_dict(self) -> dict[str, Any]:
        d = {
            "name": self.name,
            "channel": self.channel,
            "program": self.program,
            "volume": self.volume,
            "pan": self.pan,
            "reverb": self.reverb,
            "chorus": self.chorus,
            "sampler": self.sampler,
            "sampler_preset": self.sampler_preset,
            "drum_kit": getattr(self, "drum_kit", "trap_hard"),
            "glide_ticks": self.glide_ticks,
            "humanize": {
                "timing": self.humanize_timing,
                "velocity": self.humanize_velocity,
                "seed": self.humanize_seed,
            },
            "bus": getattr(self, "bus", "music"),
            "mute": self.mute,
            "solo": self.solo,
            "notes": [n.to_dict() for n in sorted(self.notes)],
            "patterns": {k: v.to_dict() for k, v in self.patterns.items()},
            "clips": [c.to_dict() for c in self.clips],
        }
        if self.instrument is not None:
            d["instrument"] = self.instrument.to_dict()
        if self.sample_pack is not None:
            d["sample_pack"] = self.sample_pack.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Track":
        human = d.get("humanize", {}) or {}
        t = Track(
            name=str(d["name"]),
            channel=int(d["channel"]),
            program=int(d.get("program", 0)),
            volume=int(d.get("volume", 100)),
            pan=int(d.get("pan", 64)),
            reverb=int(d.get("reverb", 0)),
            chorus=int(d.get("chorus", 0)),
            sampler=(str(d.get("sampler")).lower() if d.get("sampler", None) is not None else None),
            sampler_preset=str(d.get("sampler_preset", d.get("preset", "default")) or "default"),
            drum_kit=str(d.get("drum_kit", "trap_hard") or "trap_hard"),
            glide_ticks=int(d.get("glide_ticks", 0) or 0),
            humanize_timing=int(human.get("timing", d.get("humanize_timing", 0) or 0)),
            humanize_velocity=int(human.get("velocity", d.get("humanize_velocity", 0) or 0)),
            humanize_seed=int(human.get("seed", d.get("humanize_seed", 0) or 0)),
            bus=str(d.get("bus", "music") or "music"),
            mute=bool(d.get("mute", False)),
            solo=bool(d.get("solo", False)),
        )
        instr = d.get("instrument", None)
        if isinstance(instr, dict):
            t.instrument = InstrumentSpec.from_dict(instr)
        sp = d.get("sample_pack", None)
        if isinstance(sp, dict):
            t.sample_pack = SamplePackSpec.from_dict(sp)
        t.notes = [Note.from_dict(x) for x in d.get("notes", [])]
        # patterns/clips optional
        pats = d.get("patterns", {}) or {}
        t.patterns = {str(k): Pattern.from_dict(v) for k, v in pats.items()}
        t.clips = [Clip.from_dict(x) for x in d.get("clips", [])]
        return t


@dataclass
class Project:
    name: str
    tempo_bpm: int = 120
    ppq: int = 480
    tracks: list[Track] = field(default_factory=list)

    # High-level arrangement helpers (labels + pattern substitutions).
    sections: list[Section] = field(default_factory=list)
    variations: list[Variation] = field(default_factory=list)

    # recommended "bang for buck" extras
    swing_percent: int = 0  # 0-75; applied to offbeat 16ths on export/play
    loop_start: int | None = None  # ticks
    loop_end: int | None = None  # ticks (exclusive)

    # explicit render region (ticks). If set, exports should use this region.
    render_start: int | None = None
    render_end: int | None = None  # exclusive

    # Optional mix spec (sound engineering FX) used by the mix engine.
    # Stored as a JSON/YAML-friendly dict for forward compatibility.
    mix: dict[str, Any] = field(default_factory=dict)


    # runtime-only fields
    path: str | None = None
    dirty: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 11,
            "name": self.name,
            "tempo_bpm": self.tempo_bpm,
            "ppq": self.ppq,
            "swing_percent": self.swing_percent,
            "loop_start": self.loop_start,
            "loop_end": self.loop_end,
            "render_start": self.render_start,
            "render_end": self.render_end,
            "mix": getattr(self, "mix", {}) or {},
            "arrangement": {
                "sections": [s.to_dict() for s in getattr(self, "sections", [])],
                "variations": [v.to_dict() for v in getattr(self, "variations", [])],
            },
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Project":
        p = Project(
            name=str(d.get("name", "Untitled")),
            tempo_bpm=int(d.get("tempo_bpm", 120)),
            ppq=int(d.get("ppq", 480)),
            swing_percent=int(d.get("swing_percent", 0)),
            loop_start=d.get("loop_start", None),
            loop_end=d.get("loop_end", None),
            render_start=d.get("render_start", None),
            render_end=d.get("render_end", None),
            mix=dict(d.get("mix", {}) or {}),
        )
        arr = d.get("arrangement", {}) or {}
        p.sections = [Section.from_dict(x) for x in (arr.get("sections", []) or [])]
        p.variations = [Variation.from_dict(x) for x in (arr.get("variations", []) or [])]
        p.tracks = [Track.from_dict(x) for x in d.get("tracks", [])]
        return p

    def next_free_channel(self) -> int:
        used = {t.channel for t in self.tracks}
        for ch in range(16):
            if ch not in used:
                return ch
        raise RuntimeError("no free MIDI channels left")
