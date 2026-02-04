from __future__ import annotations

import tempfile
from pathlib import Path

from claw_daw.audio.render import render_project_wav
from claw_daw.model.types import Project


def export_stems(project: Project, *, soundfont: str, out_dir: str, sample_rate: int = 44100) -> list[str]:
    """Export per-track stems (rough).

    For sampler tracks, stems include the synthesized audio.
    For SoundFont tracks, we re-render the project with only that track allowed.
    """

    od = Path(out_dir).expanduser()
    od.mkdir(parents=True, exist_ok=True)

    stems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="claw_daw_stems_"):
        for idx, t in enumerate(project.tracks):
            # render only this track by temporarily muting others
            p2 = Project.from_dict(project.to_dict())
            for j, tj in enumerate(p2.tracks):
                tj.mute = j != idx
                tj.solo = False

            out = od / f"{idx:02d}_{t.name}.wav"
            out = Path(str(out).replace(" ", "_"))
            render_project_wav(p2, soundfont=soundfont, out_wav=str(out), sample_rate=sample_rate)
            stems.append(str(out))

    return stems


def export_busses(project: Project, *, soundfont: str, out_dir: str, sample_rate: int = 44100) -> list[str]:
    """Export simple busses (Drums, Bass, Music) as WAV stems.

    This is a convenience feature for agents.

    Bus assignment rules (heuristic):
    - drums: track name contains 'drum' or 'perc'
    - bass: track name contains 'bass' or '808'
    - music: everything else

    For deterministic grouping, rename tracks accordingly.
    """

    od = Path(out_dir).expanduser()
    od.mkdir(parents=True, exist_ok=True)

    groups: dict[str, list[int]] = {"drums": [], "bass": [], "music": []}
    for i, t in enumerate(project.tracks):
        n = t.name.lower()
        if "drum" in n or "perc" in n:
            groups["drums"].append(i)
        elif "bass" in n or "808" in n:
            groups["bass"].append(i)
        else:
            groups["music"].append(i)

    outs: list[str] = []
    for bus, idxs in groups.items():
        if not idxs:
            continue
        p2 = Project.from_dict(project.to_dict())
        for j, tj in enumerate(p2.tracks):
            tj.mute = j not in idxs
            tj.solo = False
        out = od / f"bus_{bus}.wav"
        render_project_wav(p2, soundfont=soundfont, out_wav=str(out), sample_rate=sample_rate)
        outs.append(str(out))

    return outs
