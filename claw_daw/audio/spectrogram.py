from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpectrogramOptions:
    size: str = "1200x600"
    legend: bool = True
    color: str = "fiery"
    scale: str = "log"  # log|lin
    gain: float = 5.0


def render_spectrogram_png(in_audio: str, out_png: str, *, sample_rate: int = 44100, opts: SpectrogramOptions | None = None) -> str:
    opts = opts or SpectrogramOptions()
    legend = 1 if opts.legend else 0

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(in_audio),
        "-lavfi",
        (
            "showspectrumpic="
            f"s={opts.size}:legend={legend}:color={opts.color}:scale={opts.scale}:gain={opts.gain}"
        ),
        "-frames:v",
        "1",
        str(out_png),
    ]

    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
    return str(out_png)


def band_energy_report(in_audio: str) -> dict[str, dict[str, float]]:
    """Very small 'reference analysis' helper.

    Uses ffmpeg volumedetect across full-band and crude band splits.

    Keys are stable and additive (new bands may be added over time).
    """

    def _vol(filtergraph: str) -> dict[str, float]:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(in_audio),
            "-af",
            filtergraph + ",volumedetect",
            "-f",
            "null",
            "-",
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        mean_db = None
        max_db = None
        for ln in p.stderr.splitlines():
            ln = ln.strip()
            if "mean_volume:" in ln:
                mean_db = float(ln.split("mean_volume:", 1)[1].split(" dB", 1)[0].strip())
            if "max_volume:" in ln:
                max_db = float(ln.split("max_volume:", 1)[1].split(" dB", 1)[0].strip())
        return {"mean_volume": float(mean_db or 0.0), "max_volume": float(max_db or 0.0)}

    return {
        "full": _vol("anull"),
        "sub_lt90": _vol("lowpass=f=90"),
        "rest_ge90": _vol("highpass=f=90"),
        # Extra splits for simple spectral balance heuristics
        "low_90_200": _vol("highpass=f=90,lowpass=f=200"),
        "mid_200_4k": _vol("highpass=f=200,lowpass=f=4000"),
        "high_ge4k": _vol("highpass=f=4000"),
    }
