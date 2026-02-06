from __future__ import annotations

import tempfile
from pathlib import Path

import subprocess

from claw_daw.audio.render import render_project_wav
from claw_daw.model.types import Project


def _infer_bus_from_name(name: str) -> str:
    n = str(name or "").strip().lower()
    if "drum" in n or "perc" in n:
        return "drums"
    if "bass" in n or "808" in n:
        return "bass"
    return "music"


def _group_tracks_by_bus(project: Project) -> dict[str, list[int]]:
    """Group tracks by bus assignment, with heuristic fallback for default bus."""

    groups: dict[str, list[int]] = {}
    for i, t in enumerate(project.tracks):
        bus = str(getattr(t, "bus", "") or "").strip().lower()
        # "music" is the model default; use heuristic grouping unless explicitly set otherwise.
        if not bus or bus == "music":
            bus = _infer_bus_from_name(getattr(t, "name", ""))
        groups.setdefault(bus or "music", []).append(i)
    return groups


def export_stems(
    project: Project,
    *,
    soundfont: str,
    out_dir: str,
    sample_rate: int = 44100,
    mix: dict | None = None,
) -> list[str]:
    """Export per-track stems.

    Notes:
    - For sampler and native instrument tracks, stems include the synthesized audio.
    - For SoundFont tracks, we re-render the project with only that track allowed.
    - If a mix spec is provided, we apply **track-level** processing (not master)
      to each stem (e.g. gain_db / eq / hp/lp / comp / sat / stereo).
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

            # Render dry stem first.
            render_project_wav(p2, soundfont=soundfont, out_wav=str(out), sample_rate=sample_rate)

            # Optionally apply *track-level* mix processing to the stem.
            if mix and isinstance(mix, dict):
                tr_spec = (mix.get("tracks") or {}).get(str(idx))
                if isinstance(tr_spec, dict) and tr_spec:
                    # Lazy import to avoid circular import with mix_engine.
                    from claw_daw.audio.mix_engine import _track_fx_chain

                    chain = _track_fx_chain(tr_spec)
                    if chain:
                        tmp = out.with_suffix(out.suffix + ".tmp.wav")
                        tmp.write_bytes(out.read_bytes())
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-hide_banner",
                                "-loglevel",
                                "error",
                                "-i",
                                str(tmp),
                                "-af",
                                chain,
                                str(out),
                            ],
                            check=True,
                        )
                        tmp.unlink(missing_ok=True)

            stems.append(str(out))

    return stems


def export_busses(project: Project, *, soundfont: str, out_dir: str, sample_rate: int = 44100) -> list[str]:
    """Export bus stems as WAV files.

    This is a convenience feature for agents.

    Bus assignment rules:
    - explicit: `track.bus` from `set_bus`
    - fallback: name heuristic for default/empty bus values
    """

    od = Path(out_dir).expanduser()
    od.mkdir(parents=True, exist_ok=True)

    groups = _group_tracks_by_bus(project)

    outs: list[str] = []
    for bus in sorted(groups.keys()):
        idxs = groups[bus]
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
