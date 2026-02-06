from __future__ import annotations

from dataclasses import replace

from claw_daw.model.types import Note, Project, Track
from claw_daw.util.notes import apply_swing_tick


def slice_project_range(project: Project, start: int, end: int) -> Project:
    """Return a new Project containing only events within [start,end), shifted to 0.

    This works for both legacy linear notes and arrangement clips/patterns by
    flattening arrangement into linear notes.

    The output contains *only* linear notes (patterns/clips are not preserved).
    """

    start = int(start)
    end = int(end)
    if start < 0:
        start = 0
    if end <= start:
        end = start

    out = Project(
        name=project.name,
        tempo_bpm=project.tempo_bpm,
        ppq=project.ppq,
        swing_percent=project.swing_percent,
        loop_start=None,
        loop_end=None,
        render_start=0,
        render_end=end - start,
    )

    for t in project.tracks:
        # Preserve all track metadata by default (including new fields added later),
        # but reset notes/arrangement to avoid leaking patterns/clips into the slice.
        nt = replace(t, notes=[], patterns={}, clips=[])

        # Prefer arrangement if present.
        if t.clips and t.patterns:
            for c in t.clips:
                pat = t.patterns.get(c.pattern)
                if not pat:
                    continue
                for rep in range(c.repeats):
                    base = c.start + rep * pat.length
                    for n in pat.notes:
                        st = apply_swing_tick(base + n.start, project.ppq, project.swing_percent)
                        en = st + n.duration
                        if st >= end or en <= start:
                            continue
                        new_start = max(st, start) - start
                        new_end = min(en, end) - start
                        nt.notes.append(
                            Note(
                                start=new_start,
                                duration=max(1, new_end - new_start),
                                pitch=n.pitch,
                                velocity=n.velocity,
                                role=getattr(n, "role", None),
                                chance=getattr(n, "chance", 1.0),
                                mute=getattr(n, "mute", False),
                                accent=getattr(n, "accent", 1.0),
                                glide_ticks=getattr(n, "glide_ticks", 0),
                            )
                        )
        else:
            for n in t.notes:
                st = apply_swing_tick(n.start, project.ppq, project.swing_percent)
                en = st + n.duration
                if st >= end or en <= start:
                    continue
                new_start = max(st, start) - start
                new_end = min(en, end) - start
                nt.notes.append(
                    Note(
                        start=new_start,
                        duration=max(1, new_end - new_start),
                        pitch=n.pitch,
                        velocity=n.velocity,
                        role=getattr(n, "role", None),
                        chance=getattr(n, "chance", 1.0),
                        mute=getattr(n, "mute", False),
                        accent=getattr(n, "accent", 1.0),
                        glide_ticks=getattr(n, "glide_ticks", 0),
                    )
                )

        out.tracks.append(nt)

    out.dirty = False
    return out
