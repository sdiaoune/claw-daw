from __future__ import annotations

import wave
from pathlib import Path


def sanitize_stereo(
    left: list[float],
    right: list[float],
    *,
    zero_threshold: float = 1.0e-9,
) -> tuple[list[float], list[float]]:
    n = max(len(left), len(right))
    if len(left) < n:
        left = left + [0.0] * (n - len(left))
    else:
        left = list(left)
    if len(right) < n:
        right = right + [0.0] * (n - len(right))
    else:
        right = list(right)

    if n <= 0:
        return left, right

    dc_l = sum(left) / float(n)
    dc_r = sum(right) / float(n)

    for i in range(n):
        lv = left[i] - dc_l
        rv = right[i] - dc_r
        left[i] = 0.0 if abs(lv) < zero_threshold else lv
        right[i] = 0.0 if abs(rv) < zero_threshold else rv

    return left, right


def write_wav_stereo(path: Path, left: list[float], right: list[float], *, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    left, right = sanitize_stereo(left, right)
    n = max(len(left), len(right))

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
