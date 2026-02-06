#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from mix_utils import classify_track, pick_kick_source_index, track_is_drum_role_capable


def load_presets(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_mix_spec(proj, preset: dict) -> dict:
    mix_def = preset.get("mix") or {}
    role_defs = (mix_def.get("roles") or {})

    mix = {
        "tracks": {},
        "returns": mix_def.get("returns") or {},
        "busses": mix_def.get("busses") or {},
        "master": mix_def.get("master") or {},
        "sidechain": [],
    }

    for i, t in enumerate(proj.tracks):
        role = classify_track(t.name)
        spec = dict(role_defs.get(role.role) or role_defs.get("music") or {})
        mix["tracks"][str(i)] = spec

    sc_def = mix_def.get("sidechain") or {}
    targets = sc_def.get("targets") or ["bass"]
    params = sc_def.get("params") or {"threshold_db": -24, "ratio": 6, "attack_ms": 5, "release_ms": 120}

    kick_idx = pick_kick_source_index(proj.tracks)
    if kick_idx is not None:
        src_track = proj.tracks[kick_idx]
        use_src_role = track_is_drum_role_capable(src_track)
        for i, t in enumerate(proj.tracks):
            role = classify_track(t.name)
            if role.role in targets:
                sc = {"src": kick_idx, "dst": i}
                if use_src_role:
                    sc["src_role"] = "kick"
                sc.update(params)
                mix["sidechain"].append(sc)

    return mix
