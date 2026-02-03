from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from claw_daw.audio.spectrogram import band_energy_report


@dataclass(frozen=True)
class MixSanity:
    """Lightweight audio sanity gate.

    This is intentionally cheap + deterministic.

    Metrics are in dBFS (negative values), derived from ffmpeg volumedetect.
    """

    score: float
    reasons: list[str]
    metrics: dict[str, float]
    bands: dict[str, dict[str, float]]

    @property
    def ok(self) -> bool:
        return self.score >= 0.60

    def to_dict(self) -> dict:
        return {"score": self.score, "ok": self.ok, "reasons": list(self.reasons), "metrics": dict(self.metrics), "bands": self.bands}


def _ffprobe_duration_seconds(in_audio: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(in_audio),
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    data = json.loads(p.stdout or "{}")
    dur = float(((data.get("format") or {}).get("duration")) or 0.0)
    return max(0.0, dur)


def _silence_fraction(in_audio: str, *, noise_db: float = -45.0, min_silence_dur: float = 0.10) -> float:
    """Estimate fraction of time considered "silent".

    Uses ffmpeg silencedetect. We parse silence_start/silence_end markers.
    """

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(in_audio),
        "-af",
        f"silencedetect=noise={noise_db}dB:d={float(min_silence_dur)}",
        "-f",
        "null",
        "-",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

    dur = _ffprobe_duration_seconds(in_audio)
    if dur <= 0:
        return 0.0

    silent_total = 0.0
    cur_start: float | None = None
    for ln in p.stderr.splitlines():
        s = ln.strip()
        # Example:
        # [silencedetect @ ...] silence_start: 0
        # [silencedetect @ ...] silence_end: 0.723 | silence_duration: 0.723
        if "silence_start:" in s:
            try:
                cur_start = float(s.split("silence_start:", 1)[1].strip().split()[0])
            except Exception:
                cur_start = None
        if "silence_end:" in s:
            try:
                end = float(s.split("silence_end:", 1)[1].strip().split("|", 1)[0].strip())
            except Exception:
                end = None
            if end is not None and cur_start is not None:
                silent_total += max(0.0, end - cur_start)
            cur_start = None

    # If the file ends in silence, silencedetect may emit silence_start but no silence_end.
    # In that case count until duration.
    if cur_start is not None:
        silent_total += max(0.0, dur - cur_start)

    return max(0.0, min(1.0, silent_total / dur))


def analyze_mix_sanity(in_audio: str) -> MixSanity:
    """Run the mix sanity gate.

    Checks:
    - clipping risk (max_volume close to 0 dBFS)
    - too much silence (e.g., empty render or missing notes)
    - crude loudness proxy (mean_volume)
    - coarse low/mid/high balance warnings

    Returns a 0..1 score where higher is "more sane".
    """

    rep = band_energy_report(in_audio)
    full = rep.get("full", {})
    mean_db = float(full.get("mean_volume", 0.0))
    max_db = float(full.get("max_volume", 0.0))

    silence_frac = _silence_fraction(in_audio)

    low = float(rep.get("low_90_200", {}).get("mean_volume", 0.0))
    mid = float(rep.get("mid_200_4k", {}).get("mean_volume", 0.0))
    high = float(rep.get("high_ge4k", {}).get("mean_volume", 0.0))

    penalties: list[tuple[float, str]] = []

    # Peak/clipping safety (approx; MP3 can hide inter-sample peaks).
    if max_db >= -0.2:
        penalties.append((0.35, f"peaks too hot (max={max_db:.1f}dBFS)") )
    elif max_db >= -1.0:
        penalties.append((0.20, f"peaks near 0dBFS (max={max_db:.1f}dBFS)") )

    # Silence detection.
    if silence_frac >= 0.85:
        penalties.append((0.60, f"mostly silent (silence~{silence_frac*100:.0f}%)"))
    elif silence_frac >= 0.50:
        penalties.append((0.30, f"too much silence (silence~{silence_frac*100:.0f}%)"))

    # Mean loudness proxy.
    if mean_db < -40.0:
        penalties.append((0.30, f"very quiet (mean={mean_db:.1f}dBFS)"))
    elif mean_db < -32.0:
        penalties.append((0.15, f"quiet (mean={mean_db:.1f}dBFS)"))
    if mean_db > -10.0:
        penalties.append((0.20, f"very loud (mean={mean_db:.1f}dBFS)"))

    # Coarse balance warnings (volumes are negative; closer to 0 is louder).
    if mid != 0.0 and high != 0.0:
        high_minus_mid = high - mid
        if high_minus_mid > 6.0:
            penalties.append((0.15, f"highs dominate mids (high-mid={high_minus_mid:.1f}dB)"))
    if mid != 0.0 and low != 0.0:
        low_minus_mid = low - mid
        if low_minus_mid > 7.0:
            penalties.append((0.15, f"lows dominate mids (low-mid={low_minus_mid:.1f}dB)"))
        if low_minus_mid < -10.0:
            penalties.append((0.10, f"thin low end (low-mid={low_minus_mid:.1f}dB)"))

    penalty = sum(p for p, _ in penalties)
    score = max(0.0, min(1.0, 1.0 - penalty))

    metrics = {
        "mean_dbfs": mean_db,
        "max_dbfs": max_db,
        "silence_fraction": float(silence_frac),
        "low_mean_dbfs": low,
        "mid_mean_dbfs": mid,
        "high_mean_dbfs": high,
    }

    return MixSanity(score=score, reasons=[r for _, r in penalties], metrics=metrics, bands=rep)
