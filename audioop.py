"""Minimal audioop compatibility shim (lin2lin only).

This is a small fallback for Python builds where stdlib audioop is missing.
It implements the subset used by claw-daw's sample pack loader.
"""

from __future__ import annotations

from typing import Final


def _bytes_to_int(sample: bytes, width: int) -> int:
    if width == 1:
        # 8-bit is unsigned in WAV: 0..255 with 128 as zero.
        return sample[0] - 128
    return int.from_bytes(sample, "little", signed=True)


def _int_to_bytes(value: int, width: int) -> bytes:
    if width == 1:
        return bytes([(value + 128) & 0xFF])
    return int(value).to_bytes(width, "little", signed=True)


def lin2lin(data: bytes, width: int, newwidth: int) -> bytes:
    """Convert linear PCM samples between widths (1-4 bytes)."""
    if width == newwidth:
        return data
    if width < 1 or newwidth < 1 or width > 4 or newwidth > 4:
        raise ValueError("lin2lin only supports widths 1..4")

    src_max: Final[int] = (1 << (8 * width - 1)) - 1
    dst_max: Final[int] = (1 << (8 * newwidth - 1)) - 1

    out = bytearray()
    step = width
    for i in range(0, len(data) - (len(data) % step), step):
        v = _bytes_to_int(data[i : i + step], width)
        # Scale to target width while preserving relative amplitude.
        ratio = v / float(src_max) if src_max else 0.0
        if ratio > 1.0:
            ratio = 1.0
        elif ratio < -1.0:
            ratio = -1.0
        nv = int(round(ratio * dst_max))
        if nv > dst_max:
            nv = dst_max
        elif nv < -dst_max - 1:
            nv = -dst_max - 1
        out.extend(_int_to_bytes(nv, newwidth))
    return bytes(out)
