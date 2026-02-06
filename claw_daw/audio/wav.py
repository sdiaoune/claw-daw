from __future__ import annotations

import wave
from pathlib import Path


def write_wav_stereo(path: Path, left: list[float], right: list[float], *, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(len(left), len(right))
    if len(left) < n:
        left = left + [0.0] * (n - len(left))
    if len(right) < n:
        right = right + [0.0] * (n - len(right))

    def _i16(x: float) -> int:
        v = max(-1.0, min(1.0, float(x)))
        return int(v * 32767.0)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        frames = bytearray()
        for i in range(n):
            frames += int.to_bytes(_i16(left[i]), 2, "little", signed=True)
            frames += int.to_bytes(_i16(right[i]), 2, "little", signed=True)
        wf.writeframes(bytes(frames))
