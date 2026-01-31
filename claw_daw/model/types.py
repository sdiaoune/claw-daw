from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from claw_daw.arrange.types import Clip, Pattern


@dataclass(order=True)
class Note:
    """A single MIDI note event in a track.

    Times are in ticks (PPQ), relative to start of the song.
    """

    start: int
    duration: int
    pitch: int
    velocity: int = 100

    def __post_init__(self) -> None:
        if not (0 <= self.pitch <= 127):
            raise ValueError(f"pitch out of range: {self.pitch}")
        if not (1 <= self.velocity <= 127):
            raise ValueError(f"velocity out of range: {self.velocity}")
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")

    @property
    def end(self) -> int:
        return self.start + self.duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "duration": self.duration,
            "pitch": self.pitch,
            "velocity": self.velocity,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Note":
        return Note(
            start=int(d["start"]),
            duration=int(d["duration"]),
            pitch=int(d["pitch"]),
            velocity=int(d.get("velocity", 100)),
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
        return {
            "name": self.name,
            "channel": self.channel,
            "program": self.program,
            "volume": self.volume,
            "pan": self.pan,
            "reverb": self.reverb,
            "chorus": self.chorus,
            "sampler": self.sampler,
            "mute": self.mute,
            "solo": self.solo,
            "notes": [n.to_dict() for n in sorted(self.notes)],
            "patterns": {k: v.to_dict() for k, v in self.patterns.items()},
            "clips": [c.to_dict() for c in self.clips],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Track":
        t = Track(
            name=str(d["name"]),
            channel=int(d["channel"]),
            program=int(d.get("program", 0)),
            volume=int(d.get("volume", 100)),
            pan=int(d.get("pan", 64)),
            reverb=int(d.get("reverb", 0)),
            chorus=int(d.get("chorus", 0)),
            sampler=(str(d.get("sampler")).lower() if d.get("sampler", None) is not None else None),
            mute=bool(d.get("mute", False)),
            solo=bool(d.get("solo", False)),
        )
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

    # recommended "bang for buck" extras
    swing_percent: int = 0  # 0-75; applied to offbeat 16ths on export/play
    loop_start: int | None = None  # ticks
    loop_end: int | None = None  # ticks (exclusive)

    # explicit render region (ticks). If set, exports should use this region.
    render_start: int | None = None
    render_end: int | None = None  # exclusive

    # runtime-only fields
    path: str | None = None
    dirty: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 4,
            "name": self.name,
            "tempo_bpm": self.tempo_bpm,
            "ppq": self.ppq,
            "swing_percent": self.swing_percent,
            "loop_start": self.loop_start,
            "loop_end": self.loop_end,
            "render_start": self.render_start,
            "render_end": self.render_end,
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
        )
        p.tracks = [Track.from_dict(x) for x in d.get("tracks", [])]
        return p

    def next_free_channel(self) -> int:
        used = {t.channel for t in self.tracks}
        for ch in range(16):
            if ch not in used:
                return ch
        raise RuntimeError("no free MIDI channels left")
