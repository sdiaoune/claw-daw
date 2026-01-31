from __future__ import annotations

import tempfile
from pathlib import Path

from claw_daw.io.midi import export_midi
from claw_daw.model.types import Project
from claw_daw.util.loop import slice_project_loop


def export_loop_midi(project: Project, midi_path: str, start: int, end: int) -> None:
    loop_proj = slice_project_loop(project, start, end)
    export_midi(loop_proj, midi_path)


def temp_mid_path(prefix: str = "claw-daw-") -> str:
    tmp = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".mid", delete=False)
    tmp.close()
    return tmp.name


def safe_unlink(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass
