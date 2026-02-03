"""Drum render sanity + automatic fallback.

Problem this targets:
- In some environments/SoundFonts, sampler-based drums can render with crackle/noise.
- Plain GM drums via FluidSynth (MIDI channel 10) can be more reliable.

We implement an *auto* mode that renders a short preview in both modes and picks the
one that looks more like a sane drum mix (more low-end punch, less harsh HF dominance).

This is intentionally simple and deterministic.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from claw_daw.audio.spectrogram import band_energy_report
from claw_daw.model.types import Note, Project, Track
from claw_daw.util.drumkit import expand_role_note


def _ticks_per_bar(project: Project) -> int:
    # 4/4 assumption consistent with the rest of the project.
    return int(project.ppq) * 4


def project_preview(project: Project, *, bars: int) -> Project:
    """Return a copy of the project with render_start/end set to the first N bars."""
    p = Project.from_dict(project.to_dict())
    p.render_start = 0
    p.render_end = int(_ticks_per_bar(p) * max(1, int(bars)))
    return p


def convert_sampler_drums_to_gm(project: Project) -> Project:
    """Convert sampler-based drum tracks to plain GM drums on MIDI channel 10.

    - Expands role notes into explicit MIDI drum pitches (GM-ish)
    - Disables sampler mode
    - Forces channel 10 (index 9)

    This avoids depending on the sampler render path.
    """

    p = Project.from_dict(project.to_dict())

    # Make channel 10 (index 9) available.
    used = {t.channel for t in p.tracks}
    if 9 in used:
        for t in p.tracks:
            if t.channel == 9 and getattr(t, "sampler", None) != "drums":
                for ch in range(16):
                    if ch != 9 and ch not in used:
                        used.remove(9)
                        t.channel = ch
                        used.add(ch)
                        break

    for i, t in enumerate(p.tracks):
        if getattr(t, "sampler", None) != "drums":
            continue

        gm_track = Track.from_dict(t.to_dict())
        gm_track.drum_kit = "gm_basic"

        def _expand(notes: list[Note]) -> list[Note]:
            expanded: list[Note] = []
            for n in notes:
                for nn in expand_role_note(n, track=gm_track):
                    expanded.append(replace(nn, role=None))

            best: dict[tuple[int, int], Note] = {}
            for n2 in expanded:
                k = (int(n2.start), int(n2.pitch))
                cur = best.get(k)
                if cur is None or int(n2.velocity) > int(cur.velocity):
                    best[k] = n2

            out = list(best.values())
            out.sort(key=lambda x: (x.start, x.pitch, -x.velocity))
            return out

        new_patterns = {name: replace(pat, notes=_expand(pat.notes)) for name, pat in t.patterns.items()}
        new_notes = _expand(t.notes)

        p.tracks[i] = replace(
            t,
            sampler=None,
            sampler_preset="default",
            drum_kit="gm_basic",
            program=0,
            channel=9,
            reverb=0,
            chorus=0,
            patterns=new_patterns,
            notes=new_notes,
        )

    return p


def _score_bands(rep: dict[str, dict[str, float]]) -> float:
    """Heuristic score: higher is better (more punch, less harsh dominance)."""
    sub = float(rep.get("sub_lt90", {}).get("mean_volume", 0.0))
    high = float(rep.get("high_ge4k", {}).get("mean_volume", 0.0))
    full_max = float(rep.get("full", {}).get("max_volume", 0.0))

    rel = sub - high

    clip_pen = 0.0
    if full_max > -1.0:
        clip_pen = (full_max + 1.0) * 3.0

    return float(rel - clip_pen)


def choose_drum_render_mode(
    *,
    project: Project,
    render_preview_wav,  # callable(Project) -> wav_path
    preview_bars: int = 8,
    threshold_db: float = 6.0,
) -> tuple[str, dict[str, Any]]:
    """Return ("sampler"|"gm", debug).

    We render a short preview in both modes and choose GM if it scores better by
    `threshold_db` (or if sampler render fails).
    """

    debug: dict[str, Any] = {"preview_bars": int(preview_bars), "threshold_db": float(threshold_db)}

    has_sampler_drums = any(getattr(t, "sampler", None) == "drums" for t in project.tracks)
    if not has_sampler_drums:
        debug["reason"] = "no sampler drums"
        return "sampler", debug

    p_prev = project_preview(project, bars=preview_bars)

    try:
        wav_s = render_preview_wav(p_prev)
        rep_s = band_energy_report(wav_s)
        score_s = _score_bands(rep_s)
    except Exception as e:
        debug["sampler_error"] = repr(e)
        return "gm", debug

    try:
        gm_prev = convert_sampler_drums_to_gm(p_prev)
        wav_g = render_preview_wav(gm_prev)
        rep_g = band_energy_report(wav_g)
        score_g = _score_bands(rep_g)
    except Exception as e:
        debug["gm_error"] = repr(e)
        return "sampler", debug

    debug["sampler_score"] = score_s
    debug["gm_score"] = score_g

    if score_g > score_s + float(threshold_db):
        debug["reason"] = "gm better by threshold"
        return "gm", debug

    debug["reason"] = "sampler ok"
    return "sampler", debug
