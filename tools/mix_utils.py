#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TrackRole:
    role: str
    bus: str
    is_drums: bool
    is_bass: bool
    is_kick: bool
    is_music: bool
    is_fx: bool
    is_vocal: bool


def _has_any(name: str, tokens: Iterable[str]) -> bool:
    return any(t in name for t in tokens)


def classify_track(name: str) -> TrackRole:
    n = (name or "").strip().lower()

    drum_tokens = ["drum", "perc", "kick", "snare", "clap", "hat", "hh", "ride", "cym", "tom", "shaker", "rim"]
    bass_tokens = ["bass", "sub", "808"]
    vocal_tokens = ["vocal", "vox", "voice", "choir"]
    lead_tokens = ["lead", "hook"]
    pluck_tokens = ["pluck", "arp", "seq"]
    pad_tokens = ["pad", "string", "strings", "wash", "atmo", "atmos"]
    keys_tokens = ["key", "keys", "chord", "piano", "organ", "synth", "stab"]
    fx_tokens = ["fx", "rise", "riser", "impact", "sweep", "noise", "down", "uplifter", "drop"]

    is_drums = _has_any(n, drum_tokens)
    is_bass = _has_any(n, bass_tokens)
    is_vocal = _has_any(n, vocal_tokens)
    is_fx = _has_any(n, fx_tokens)
    is_kick = "kick" in n

    if is_drums:
        return TrackRole(role="drums", bus="drums", is_drums=True, is_bass=False, is_kick=is_kick, is_music=False, is_fx=False, is_vocal=False)
    if is_bass:
        return TrackRole(role="bass", bus="bass", is_drums=False, is_bass=True, is_kick=False, is_music=False, is_fx=False, is_vocal=False)
    if is_vocal:
        return TrackRole(role="vox", bus="vox", is_drums=False, is_bass=False, is_kick=False, is_music=False, is_fx=False, is_vocal=True)
    if _has_any(n, lead_tokens):
        return TrackRole(role="lead", bus="music", is_drums=False, is_bass=False, is_kick=False, is_music=True, is_fx=False, is_vocal=False)
    if _has_any(n, pluck_tokens):
        return TrackRole(role="pluck", bus="music", is_drums=False, is_bass=False, is_kick=False, is_music=True, is_fx=False, is_vocal=False)
    if _has_any(n, pad_tokens):
        return TrackRole(role="pad", bus="music", is_drums=False, is_bass=False, is_kick=False, is_music=True, is_fx=False, is_vocal=False)
    if _has_any(n, keys_tokens):
        return TrackRole(role="keys", bus="music", is_drums=False, is_bass=False, is_kick=False, is_music=True, is_fx=False, is_vocal=False)
    if is_fx:
        return TrackRole(role="fx", bus="music", is_drums=False, is_bass=False, is_kick=False, is_music=True, is_fx=True, is_vocal=False)

    return TrackRole(role="music", bus="music", is_drums=False, is_bass=False, is_kick=False, is_music=True, is_fx=False, is_vocal=False)


def pick_kick_source_index(tracks) -> int | None:
    # Prefer a dedicated kick track, else a drums track.
    kick_idx = None
    drum_idx = None
    for i, t in enumerate(tracks):
        role = classify_track(getattr(t, "name", ""))
        if role.is_kick:
            kick_idx = i
            break
        if role.is_drums and drum_idx is None:
            drum_idx = i
    return kick_idx if kick_idx is not None else drum_idx


def track_is_drum_role_capable(track) -> bool:
    # Heuristic: drum channel (10 -> index 9), sampler drums, sample pack, or drum_kit set.
    try:
        if getattr(track, "channel", None) == 9:
            return True
    except Exception:
        pass
    try:
        if getattr(track, "sampler", None) == "drums":
            return True
    except Exception:
        pass
    try:
        if getattr(track, "sample_pack", None) is not None:
            return True
    except Exception:
        pass
    try:
        if getattr(track, "drum_kit", None):
            return True
    except Exception:
        pass
    return False


def guess_section_scale(pattern_name: str) -> float | None:
    name = (pattern_name or "").lower()
    # Ordered by priority.
    rules = [
        (r"breakdown|break", 0.75),
        (r"intro|outro", 0.85),
        (r"build|rise", 0.90),
        (r"verse", 0.90),
        (r"drop|chorus|hook", 1.0),
    ]
    for pat, scale in rules:
        if re.search(pat, name):
            return scale
    return None
