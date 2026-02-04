from __future__ import annotations

import math
import subprocess
from pathlib import Path

from claw_daw.audio.metering import analyze_metering, measure_stereo_correlation


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


def test_metering_reports_lufs_truepeak_and_crest(tmp_path: Path) -> None:
    wav = tmp_path / "tone.wav"
    # -12 dBFS sine (roughly); stereo.
    _ffmpeg_make("sine=frequency=1000:sample_rate=44100:duration=1,volume=-12dB,pan=stereo|c0=c0|c1=c0", wav)

    m = analyze_metering(str(wav), include_spectral=False)
    assert m.integrated_lufs is not None
    assert -40.0 < m.integrated_lufs < 0.0

    assert m.true_peak_dbtp is not None
    assert -20.0 < m.true_peak_dbtp < 0.0

    assert m.peak_dbfs is not None
    assert -20.0 < m.peak_dbfs < 0.0

    assert m.rms_dbfs is not None
    assert -40.0 < m.rms_dbfs < 0.0

    assert m.crest_factor_db is not None
    # Sine crest ~ 3.01 dB
    assert math.isfinite(m.crest_factor_db)
    assert 2.5 <= m.crest_factor_db <= 3.7


def test_metering_detects_dc_offset(tmp_path: Path) -> None:
    wav = tmp_path / "dc.wav"
    # Add DC offset of 0.1 to both channels.
    _ffmpeg_make("aevalsrc=0.1+0.2*sin(2*PI*440*t)|0.1+0.2*sin(2*PI*440*t):s=44100:d=1", wav)

    m = analyze_metering(str(wav), include_spectral=False)
    assert m.dc_offset is not None
    assert 0.08 <= m.dc_offset <= 0.12


def test_stereo_correlation_in_phase_vs_antiphase(tmp_path: Path) -> None:
    a = tmp_path / "inphase.wav"
    b = tmp_path / "antiphase.wav"

    _ffmpeg_make("aevalsrc=sin(2*PI*220*t)|sin(2*PI*220*t):s=44100:d=1", a)
    _ffmpeg_make("aevalsrc=sin(2*PI*220*t)|-sin(2*PI*220*t):s=44100:d=1", b)

    ca = measure_stereo_correlation(str(a))
    cb = measure_stereo_correlation(str(b))

    assert ca is not None and ca > 0.95
    assert cb is not None and cb < -0.95
