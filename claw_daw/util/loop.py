from __future__ import annotations

from claw_daw.model.types import Note, Project, Track


def slice_project_loop(project: Project, start: int, end: int) -> Project:
    """Return a new Project containing only events within [start,end), shifted to 0."""
    out = Project(
        name=project.name + "_loop",
        tempo_bpm=project.tempo_bpm,
        ppq=project.ppq,
        swing_percent=project.swing_percent,
    )

    for t in project.tracks:
        nt = Track(
            name=t.name,
            channel=t.channel,
            program=t.program,
            volume=t.volume,
            pan=t.pan,
            reverb=getattr(t, "reverb", 0),
            chorus=getattr(t, "chorus", 0),
            sampler=getattr(t, "sampler", None),
            mute=t.mute,
            solo=t.solo,
        )
        for n in t.notes:
            if n.start >= end or n.end <= start:
                continue
            new_start = max(n.start, start) - start
            new_end = min(n.end, end) - start
            nt.notes.append(Note(start=new_start, duration=max(1, new_end - new_start), pitch=n.pitch, velocity=n.velocity))
        out.tracks.append(nt)

    out.dirty = False
    return out
