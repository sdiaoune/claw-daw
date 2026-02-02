from __future__ import annotations

import math
from dataclasses import dataclass

from claw_daw.model.types import Project


@dataclass(frozen=True)
class ProjectFingerprint:
    # 12-dim pitch class histogram across all notes.
    pitch_class_hist: tuple[float, ...]
    # 16-dim rhythmic histogram (mod 16th) across all notes.
    step_hist: tuple[float, ...]
    # Interval histogram bucketed into 25 bins (-12..+12, clamp).
    interval_hist: tuple[float, ...]
    # 8-dim velocity histogram (bucketed).
    velocity_hist: tuple[float, ...]
    # 64-dim hashed event bigrams (order-sensitive, coarse).
    event_hash_hist: tuple[float, ...]
    # 64-dim hashed (track,step,pitchclass) events to reduce false positives
    # when different role structure yields similar global histograms.
    track_event_hash_hist: tuple[float, ...]


def _normalize(v: list[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in v))
    if norm <= 1e-12:
        return tuple([0.0 for _ in v])
    return tuple([x / norm for x in v])


def fingerprint_project(proj: Project) -> ProjectFingerprint:
    pc = [0.0] * 12
    step = [0.0] * 16
    intervals = [0.0] * 25  # -12..+12
    vel_hist = [0.0] * 8
    ev_hash = [0.0] * 64
    track_ev_hash = [0.0] * 64

    all_notes: list[tuple[int, int]] = []  # (start, pitch)
    ppq = int(proj.ppq)
    sixteenth = max(1, ppq // 4)

    for ti, t in enumerate(proj.tracks):
        # Use arranged patterns if present, else linear notes.
        if t.patterns and t.clips:
            # Expand clips quickly (best-effort): only use pattern starts.
            for c in t.clips:
                pat = t.patterns.get(c.pattern)
                if not pat:
                    continue
                for rep in range(max(1, int(c.repeats))):
                    base = int(c.start) + rep * int(pat.length)
                    for n in pat.notes:
                        if getattr(n, "mute", False):
                            continue
                        if float(getattr(n, "chance", 1.0)) <= 0.0:
                            continue
                        start = base + int(n.start)
                        pitch = int(n.pitch)
                        pc[pitch % 12] += 1.0
                        step[(start // sixteenth) % 16] += 1.0
                        v = int(getattr(n, "velocity", 100) or 100)
                        v = max(1, min(127, v))
                        vel_hist[min(7, (v - 1) // 16)] += 1.0
                        te = (ti * 1315423911 + ((start // sixteenth) % 16) * 12 + (pitch % 12)) & 63
                        track_ev_hash[te] += 1.0
                        all_notes.append((start, pitch))
        else:
            for n in t.notes:
                if getattr(n, "mute", False):
                    continue
                if float(getattr(n, "chance", 1.0)) <= 0.0:
                    continue
                start = int(n.start)
                pitch = int(n.pitch)
                pc[pitch % 12] += 1.0
                step[(start // sixteenth) % 16] += 1.0
                v = int(getattr(n, "velocity", 100) or 100)
                v = max(1, min(127, v))
                vel_hist[min(7, (v - 1) // 16)] += 1.0
                te = (ti * 1315423911 + ((start // sixteenth) % 16) * 12 + (pitch % 12)) & 63
                track_ev_hash[te] += 1.0
                all_notes.append((start, pitch))

    all_notes.sort(key=lambda x: x[0])
    for (s1, p1), (s2, p2) in zip(all_notes, all_notes[1:]):
        iv = int(p2) - int(p1)
        iv = max(-12, min(12, iv))
        intervals[iv + 12] += 1.0

        # order-sensitive hashed bigram of (step,pitchclass)->(step,pitchclass)
        a = ((s1 // sixteenth) % 16) * 12 + (p1 % 12)
        b = ((s2 // sixteenth) % 16) * 12 + (p2 % 12)
        h = (a * 1315423911 + b * 2654435761) & 63
        ev_hash[h] += 1.0

    return ProjectFingerprint(
        pitch_class_hist=_normalize(pc),
        step_hist=_normalize(step),
        interval_hist=_normalize(intervals),
        velocity_hist=_normalize(vel_hist),
        event_hash_hist=_normalize(ev_hash),
        track_event_hash_hist=_normalize(track_ev_hash),
    )


def _cos(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def project_similarity(a: Project, b: Project) -> float:
    """Return similarity in [0,1] based on simple musical fingerprints."""

    fa = fingerprint_project(a)
    fb = fingerprint_project(b)

    # Average of cosine similarities.
    sims = [
        _cos(fa.pitch_class_hist, fb.pitch_class_hist),
        _cos(fa.step_hist, fb.step_hist),
        _cos(fa.interval_hist, fb.interval_hist),
        _cos(fa.velocity_hist, fb.velocity_hist),
        _cos(fa.event_hash_hist, fb.event_hash_hist),
        _cos(fa.track_event_hash_hist, fb.track_event_hash_hist),
    ]
    # clamp numeric noise
    s = sum(sims) / len(sims)
    return max(0.0, min(1.0, s))
