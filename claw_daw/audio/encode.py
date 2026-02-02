from __future__ import annotations

import subprocess
from pathlib import Path


def encode_audio(
    in_wav: str,
    out_path: str,
    *,
    trim_seconds: float | None = None,
    sample_rate: int = 44100,
    codec: str = "mp3",
    bitrate: str = "192k",
) -> str:
    """Encode a WAV file to a compressed audio format via ffmpeg.

    Supported codecs: mp3, m4a (aac).
    """

    inp = str(Path(in_wav))
    outp = str(Path(out_path))

    if codec not in {"mp3", "m4a"}:
        raise ValueError("codec must be mp3 or m4a")

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

    if codec == "mp3":
        cmd += ["-codec:a", "libmp3lame", "-b:a", bitrate, outp]
    else:
        # m4a container w/ AAC
        cmd += ["-codec:a", "aac", "-b:a", bitrate, outp]

    subprocess.run(cmd, check=True)
    return outp
