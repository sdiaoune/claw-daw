from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MasterPreset:
    name: str
    # ffmpeg filtergraph (audio)
    afilter: str


# Deterministic macro-style mastering presets.
MASTER_PRESETS: dict[str, MasterPreset] = {
    # Safe default: light highpass + gentle compression + limiter.
    "clean": MasterPreset(
        name="clean",
        # Streaming-safe: target -14 LUFS with true-peak <= -1.0 dBTP.
        afilter="highpass=f=30,loudnorm=I=-14:TP=-2.0:LRA=11",
    ),
    # "demo" is intentionally a bit louder/brighter.
    "demo": MasterPreset(
        name="demo",
        # Use equalizer (3-band style) for broad high-shelf-ish lift (more compatible than eq=t=h).
        afilter="highpass=f=30,acompressor=threshold=-20dB:ratio=3:attack=3:release=40,equalizer=f=9000:t=h:width_type=o:width=2:g=2,alimiter=limit=0.98",
    ),
    # Lofi macro: bandlimit + saturation-ish + noise gate.
    "lofi": MasterPreset(
        name="lofi",
        afilter="highpass=f=120,lowpass=f=6000,acompressor=threshold=-22dB:ratio=3,alimiter=limit=0.96",
    ),
    # Punchy macro: a bit more compression + gentle saturation + limiter.
    "punchy": MasterPreset(
        name="punchy",
        afilter="highpass=f=30,acompressor=threshold=-24dB:ratio=4:attack=3:release=80,asoftclip=type=tanh,alimiter=limit=0.97",
    ),
}


def _load_custom_preset(preset: str) -> MasterPreset | None:
    """Load a custom mastering preset from file.

    Supported forms:
      - preset="file:/path/to/afilter.txt"  (file contains an ffmpeg audio filtergraph)
      - preset="@/path/to/afilter.txt"      (same)

    Returns None if preset is not a file reference.
    """

    p = preset.strip()
    path = None
    if p.startswith("file:"):
        path = p.split(":", 1)[1]
    elif p.startswith("@"):
        path = p[1:]
    if not path:
        return None

    fp = Path(path).expanduser()
    af = fp.read_text(encoding="utf-8").strip()
    if not af:
        raise ValueError(f"empty mastering chain file: {fp}")
    return MasterPreset(name=str(fp.name), afilter=af)


def _fade_filter(*, fade_in_seconds: float, fade_out_seconds: float, dur_seconds: float | None) -> str:
    parts: list[str] = []
    if fade_in_seconds > 0:
        parts.append(f"afade=t=in:st=0:d={float(fade_in_seconds)}")
    if fade_out_seconds > 0 and dur_seconds is not None:
        st = max(0.0, float(dur_seconds) - float(fade_out_seconds))
        parts.append(f"afade=t=out:st={st}:d={float(fade_out_seconds)}")
    return ",".join(parts)


def master_wav(
    in_wav: str,
    out_wav: str,
    *,
    sample_rate: int = 44100,
    trim_seconds: float | None = None,
    preset: str = "demo",
    fade_in_seconds: float = 0.0,
    fade_out_seconds: float = 0.0,
) -> str:
    """Apply deterministic mastering via ffmpeg.

    Returns path to the mastered wav.
    """

    custom = _load_custom_preset(preset)
    if custom is None and preset not in MASTER_PRESETS:
        raise ValueError(f"unknown preset: {preset}")

    inp = str(Path(in_wav))
    stream_to_stdout = str(out_wav).strip() == "-"
    outp = "pipe:1" if stream_to_stdout else str(Path(out_wav))

    # Build a deterministic filtergraph.
    base = custom.afilter if custom is not None else MASTER_PRESETS[preset].afilter
    filters = [base]
    fade = _fade_filter(fade_in_seconds=fade_in_seconds, fade_out_seconds=fade_out_seconds, dur_seconds=trim_seconds)
    if fade:
        filters.append(fade)
    af = ",".join([f for f in filters if f])

    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        inp,
        "-ar",
        str(int(sample_rate)),
    ]

    if trim_seconds is not None:
        cmd += ["-t", str(float(trim_seconds))]

    cmd += ["-af", af]

    if stream_to_stdout:
        # Force container when writing to pipe.
        cmd += ["-f", "wav", outp]
        subprocess.run(cmd, check=True, stdout=sys.stdout.buffer)
        return "-"

    cmd += [outp]
    Path(outp).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
    return outp
