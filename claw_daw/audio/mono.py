from __future__ import annotations


def mono_below_filter(*, hz: float, low_label: str = "lo", high_label: str = "hi") -> str:
    """Return a labeled ffmpeg filtergraph snippet that mono-sums below hz.

    Usage pattern:
      [in]{snippet}[out]

    We split into low/high, mono the low band, then mix back.

    Note: This returns a *filtergraph* (with labels), not a comma-chain.
    """

    hz = max(20.0, float(hz))
    # pan=mono collapses to 1ch; we re-upmix to stereo via pan=stereo
    return (
        f"asplit=2[{low_label}][{high_label}];"
        f"[{low_label}]lowpass=f={hz},pan=mono|c0=0.5*c0+0.5*c1,pan=stereo|c0=c0|c1=c0[{low_label}m];"
        f"[{high_label}]highpass=f={hz}[{high_label}f];"
        f"[{low_label}m][{high_label}f]amix=inputs=2:normalize=0"
    )
