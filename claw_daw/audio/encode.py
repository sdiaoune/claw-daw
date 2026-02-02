from __future__ import annotations

import subprocess
import sys
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
    if codec not in {"mp3", "m4a"}:
        raise ValueError("codec must be mp3 or m4a")

    # Support streaming to stdout for agent pipelines.
    stream_to_stdout = out_path.strip() == "-"
    outp = "pipe:1" if stream_to_stdout else str(Path(out_path))

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
        # When writing to a pipe, force the container/format.
        if stream_to_stdout:
            cmd += ["-f", "mp3"]
        cmd += ["-codec:a", "libmp3lame", "-b:a", bitrate, outp]
    else:
        # m4a container w/ AAC
        if stream_to_stdout:
            cmd += ["-f", "ipod"]
        cmd += ["-codec:a", "aac", "-b:a", bitrate, outp]

    if stream_to_stdout:
        subprocess.run(cmd, check=True, stdout=sys.stdout.buffer)
        return "-"

    subprocess.run(cmd, check=True)
    return outp
