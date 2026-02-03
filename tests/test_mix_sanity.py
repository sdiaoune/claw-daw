from __future__ import annotations

import subprocess
from pathlib import Path

from claw_daw.audio.sanity import analyze_mix_sanity


def _ffmpeg_make(src_filter: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        src_filter,
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def test_mix_sanity_detects_mostly_silent(tmp_path: Path) -> None:
    wav = tmp_path / "silence.wav"
    _ffmpeg_make("anullsrc=r=44100:cl=mono:d=1.5", wav)

    s = analyze_mix_sanity(str(wav))
    assert s.metrics["silence_fraction"] >= 0.80
    assert s.score < 0.60
    assert any("silent" in r for r in s.reasons)


def test_mix_sanity_detects_hot_peaks(tmp_path: Path) -> None:
    wav = tmp_path / "clip.wav"
    # Generate a sine and amplify to force max_volume close to 0 dBFS.
    _ffmpeg_make("sine=frequency=1000:sample_rate=44100:duration=1,volume=25dB", wav)

    s = analyze_mix_sanity(str(wav))
    assert s.metrics["max_dbfs"] >= -1.0
    assert any("peaks" in r for r in s.reasons)
