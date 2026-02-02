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
    with tempfile.TemporaryDirectory(prefix="claw_daw_stems_") as td:
        tdir = Path(td)
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
