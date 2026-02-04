from __future__ import annotations

from typing import Any

from claw_daw.model.types import Project
from claw_daw.util.drumkit import get_drum_kit, normalize_role
from claw_daw.util.limits import (
    MAX_CLIPS_PER_TRACK,
    MAX_NOTES_PER_PATTERN,
    MAX_NOTES_PER_TRACK,
    MAX_PATTERNS_PER_TRACK,
    MAX_TICK,
    MAX_TRACKS,
)


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


CURRENT_SCHEMA_VERSION = 9


def migrate_project_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Migrate a project JSON dict to the latest schema.

    Migration is intentionally simple/defensive: we add missing fields and
    normalize types, but we don't try to perfectly repair corrupted structures.
    """

    schema = int(d.get("schema_version", 1) or 1)

    # v1 -> v2: add swing/loop fields
    if schema < 2:
        d.setdefault("swing_percent", 0)
        d.setdefault("loop_start", None)
        d.setdefault("loop_end", None)
        schema = 2

    # v2 -> v3: add render region
    if schema < 3:
        d.setdefault("render_start", None)
        d.setdefault("render_end", None)
        schema = 3

    # v3/v4 -> v5: arrangement + track humanize/glide fields
    if schema < 5:
        d.setdefault("arrangement", {"sections": [], "variations": []})
        for t in d.get("tracks", []) or []:
            t.setdefault("glide_ticks", 0)
            # new preferred shape
            t.setdefault("humanize", {"timing": 0, "velocity": 0, "seed": 0})
        schema = 5

    # v5 -> v6: sampler preset
    if schema < 6:
        for t in d.get("tracks", []) or []:
            t.setdefault("sampler_preset", "default")
        schema = 6

    # v6 -> v7: drum kit (for role-based drum notes)
    if schema < 7:
        for t in d.get("tracks", []) or []:
            t.setdefault("drum_kit", "trap_hard")
        schema = 7

    # v7 -> v8: optional mix spec (sound engineering FX)
    if schema < 8:
        d.setdefault("mix", {})
        schema = 8

    # v8 -> v9: track bus assignment
    if schema < 9:
        for t in d.get("tracks", []) or []:
            t.setdefault("bus", "music")
        schema = 9

    d["schema_version"] = CURRENT_SCHEMA_VERSION
    return d


def validate_and_migrate_project(project: Project) -> Project:
    """Best-effort validation/migration for loaded projects.

    Keeps the app from crashing on old/bad files and prevents footguns.
    """

    project.tempo_bpm = clamp(project.tempo_bpm, 20, 400)
    project.ppq = clamp(project.ppq, 24, 1920)
    project.swing_percent = clamp(getattr(project, "swing_percent", 0), 0, 75)

    # arrangement metadata (safe defaults)
    project.sections = list(getattr(project, "sections", []) or [])
    project.variations = list(getattr(project, "variations", []) or [])

    # mix spec (optional)
    project.mix = dict(getattr(project, "mix", {}) or {})

    # hard limits
    if len(project.tracks) > MAX_TRACKS:
        project.tracks = project.tracks[:MAX_TRACKS]

    # loop
    ls = getattr(project, "loop_start", None)
    le = getattr(project, "loop_end", None)
    if ls is not None and le is not None:
        try:
            ls_i = int(ls)
            le_i = int(le)
        except Exception:
            ls_i, le_i = None, None
        if ls_i is None or le_i is None or le_i <= ls_i or ls_i < 0 or le_i > MAX_TICK:
            project.loop_start = None
            project.loop_end = None
        else:
            project.loop_start = ls_i
            project.loop_end = le_i

    # render region
    rs = getattr(project, "render_start", None)
    re = getattr(project, "render_end", None)
    if rs is not None and re is not None:
        try:
            rs_i = int(rs)
            re_i = int(re)
        except Exception:
            rs_i, re_i = None, None
        if rs_i is None or re_i is None or re_i <= rs_i or rs_i < 0 or re_i > MAX_TICK:
            project.render_start = None
            project.render_end = None
        else:
            project.render_start = rs_i
            project.render_end = re_i

    for t in project.tracks:
        t.channel = clamp(t.channel, 0, 15)
        t.program = clamp(t.program, 0, 127)
        t.volume = clamp(getattr(t, "volume", 100), 0, 127)
        t.pan = clamp(getattr(t, "pan", 64), 0, 127)
        t.reverb = clamp(getattr(t, "reverb", 0), 0, 127)
        t.chorus = clamp(getattr(t, "chorus", 0), 0, 127)

        # sampler mode (optional)
        sm = getattr(t, "sampler", None)
        if sm is None:
            t.sampler = None
        else:
            s = str(sm).strip().lower()
            t.sampler = s if s in {"drums", "808"} else None

        # sampler preset (optional; validated at render time)
        t.sampler_preset = str(getattr(t, "sampler_preset", "default") or "default")

        # bus assignment
        t.bus = str(getattr(t, "bus", "music") or "music").strip().lower() or "music"

        # drum kit (role-based drums)
        try:
            t.drum_kit = get_drum_kit(getattr(t, "drum_kit", "trap_hard")).name
        except Exception:
            t.drum_kit = "trap_hard"

        t.glide_ticks = clamp(int(getattr(t, "glide_ticks", 0) or 0), 0, project.ppq * 2)
        t.humanize_timing = clamp(int(getattr(t, "humanize_timing", 0) or 0), 0, project.ppq // 8)
        t.humanize_velocity = clamp(int(getattr(t, "humanize_velocity", 0) or 0), 0, 30)
        t.humanize_seed = int(getattr(t, "humanize_seed", 0) or 0)

        # ensure patterns dictionary is sane
        t.patterns = dict(getattr(t, "patterns", {}) or {})
        t.clips = list(getattr(t, "clips", []) or [])

        # cap counts
        if len(t.notes) > MAX_NOTES_PER_TRACK:
            t.notes = sorted(t.notes)[:MAX_NOTES_PER_TRACK]
        if len(t.patterns) > MAX_PATTERNS_PER_TRACK:
            # deterministic truncation: keep lexicographically-first keys
            keys = sorted(t.patterns.keys())[:MAX_PATTERNS_PER_TRACK]
            t.patterns = {k: t.patterns[k] for k in keys}
        if len(t.clips) > MAX_CLIPS_PER_TRACK:
            t.clips = t.clips[:MAX_CLIPS_PER_TRACK]

        # sanity for notes
        for n in t.notes:
            n.pitch = clamp(n.pitch, 0, 127)
            n.velocity = clamp(n.velocity, 1, 127)
            n.role = normalize_role(getattr(n, "role", None))
            if n.start < 0:
                n.start = 0
            if n.start > MAX_TICK:
                n.start = MAX_TICK
            if n.duration <= 0:
                n.duration = 1
            if n.duration > MAX_TICK:
                n.duration = MAX_TICK

        # sanity for pattern notes
        for pat in t.patterns.values():
            if pat.length <= 0:
                pat.length = project.ppq * 4
            pat.length = clamp(pat.length, 1, MAX_TICK)
            if len(pat.notes) > MAX_NOTES_PER_PATTERN:
                pat.notes = sorted(pat.notes)[:MAX_NOTES_PER_PATTERN]
            for n in pat.notes:
                n.pitch = clamp(n.pitch, 0, 127)
                n.velocity = clamp(n.velocity, 1, 127)
                n.role = normalize_role(getattr(n, "role", None))
                if n.start < 0:
                    n.start = 0
                if n.start > MAX_TICK:
                    n.start = MAX_TICK
                if n.duration <= 0:
                    n.duration = 1
                if n.duration > MAX_TICK:
                    n.duration = MAX_TICK

    return project
