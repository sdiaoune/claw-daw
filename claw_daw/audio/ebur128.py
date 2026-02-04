from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Ebur128Stats:
    # last-observed short-term loudness (LUFS)
    shortterm_lufs: float | None


_RE_ST = re.compile(r"\bS:\s*([-0-9.]+)\s*LUFS\b")


def measure_shortterm_lufs(in_audio: str) -> Ebur128Stats:
    """Measure short-term LUFS using ffmpeg ebur128.

    We parse the last S: ... LUFS reading from the framelog output.
    """

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(in_audio),
        "-filter_complex",
        "ebur128=peak=true:framelog=verbose",
        "-f",
        "null",
        "-",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    st: float | None = None
    for ln in (p.stderr or "").splitlines():
        m = _RE_ST.search(ln)
        if not m:
            continue
        try:
            st = float(m.group(1))
        except Exception:
            continue
    return Ebur128Stats(shortterm_lufs=st)
