from __future__ import annotations

import json
import math
import re
import subprocess
from array import array
from dataclasses import dataclass

from claw_daw.audio.spectrogram import band_energy_report


@dataclass(frozen=True)
class AudioMetering:
    """Audio metering / diagnostics for quick offline checks.

    All metrics are deterministic and derived from ffmpeg/ffprobe or simple math.

    Notes:
    - LUFS/true-peak are sourced via ffmpeg loudnorm analysis (EBU R128).
    - RMS/peak/DC offset/crest factor are sourced via ffmpeg astats.
    - Stereo correlation is computed in Python from decoded PCM (no numpy required).
    """

    integrated_lufs: float | None
    loudness_range_lu: float | None
    true_peak_dbtp: float | None

    peak_dbfs: float | None
    rms_dbfs: float | None
    crest_factor_linear: float | None
    crest_factor_db: float | None

    dc_offset: float | None
    stereo_correlation: float | None

    spectral_bands: dict[str, dict[str, float]] | None

    raw: dict


_LOUDNORM_JSON_RE = re.compile(r"\{\s*\"input_i\".*?\}\s*", re.DOTALL)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)


def _parse_loudnorm_json(stderr: str) -> dict | None:
    # loudnorm prints a JSON blob to stderr. We grab the first JSON object that includes input_i.
    m = _LOUDNORM_JSON_RE.search(stderr or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def measure_lufs_truepeak(in_audio: str) -> dict[str, float] | None:
    """Return LUFS / true-peak metrics (input_* fields) using ffmpeg loudnorm.

    Returns keys:
      - integrated_lufs
      - loudness_range_lu
      - true_peak_dbtp

    If parsing fails, returns None.
    """

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(in_audio),
        "-af",
        # Targets are irrelevant; we only read input_* stats. (Still deterministic.)
        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f",
        "null",
        "-",
    ]
    p = _run(cmd)
    data = _parse_loudnorm_json(p.stderr)
    if not data:
        return None

    def _f(k: str) -> float | None:
        v = data.get(k)
        try:
            return float(v)
        except Exception:
            return None

    out = {
        "integrated_lufs": _f("input_i"),
        "loudness_range_lu": _f("input_lra"),
        "true_peak_dbtp": _f("input_tp"),
    }
    # Drop Nones
    out2 = {k: v for k, v in out.items() if v is not None}
    return out2 or None


def measure_astats(in_audio: str) -> dict[str, float] | None:
    """Return peak/RMS/DC offset/crest factor (from ffmpeg astats 'Overall' section)."""

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(in_audio),
        "-af",
        "astats=metadata=0:reset=0",
        "-f",
        "null",
        "-",
    ]
    p = _run(cmd)

    overall = False
    metrics: dict[str, float] = {}

    # Example lines:
    # [Parsed_astats_0 ...] Overall
    # [Parsed_astats_0 ...] DC offset: 0.000000
    # [Parsed_astats_0 ...] Peak level dB: -0.000002
    # [Parsed_astats_0 ...] RMS level dB: -3.010300
    # [Parsed_astats_0 ...] Crest factor: 1.414213
    for ln in (p.stderr or "").splitlines():
        s = ln.strip()
        if s.endswith("] Overall") or s.endswith("] Overall:") or s.endswith("] Overall"):
            overall = True
            continue
        if overall and "] Channel:" in s:
            # In some builds, Overall is followed by channels again; stop once we exit overall block.
            overall = False
        if not overall:
            continue

        def _grab(prefix: str) -> float | None:
            if prefix not in s:
                return None
            try:
                return float(s.split(prefix, 1)[1].strip().split()[0])
            except Exception:
                return None

        v = _grab("DC offset:")
        if v is not None:
            metrics["dc_offset"] = v
        v = _grab("Peak level dB:")
        if v is not None:
            metrics["peak_dbfs"] = v
        v = _grab("RMS level dB:")
        if v is not None:
            metrics["rms_dbfs"] = v
        v = _grab("Crest factor:")
        if v is not None:
            metrics["crest_factor_linear"] = v

    if not metrics:
        return None
    # Derived crest factor in dB if possible.
    if "peak_dbfs" in metrics and "rms_dbfs" in metrics:
        metrics["crest_factor_db"] = float(metrics["peak_dbfs"] - metrics["rms_dbfs"])
    elif "crest_factor_linear" in metrics:
        try:
            metrics["crest_factor_db"] = float(20.0 * math.log10(max(1e-12, metrics["crest_factor_linear"])))
        except Exception:
            pass

    return metrics


def measure_stereo_correlation(in_audio: str, *, max_seconds: float = 10.0) -> float | None:
    """Compute Pearson correlation between L/R channels.

    Returns -1..+1 for stereo inputs. If the audio decodes to mono, returns None.

    We decode to float32 PCM using ffmpeg and compute correlation in Python.
    """

    # Force stereo decode (ac=2). For mono sources, ffmpeg will duplicate channel and corr ~ 1.
    # So we detect mono via channel_layout from ffprobe.
    try:
        pr = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=channels",
                "-of",
                "json",
                str(in_audio),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        info = json.loads(pr.stdout or "{}")
        streams = info.get("streams") or []
        ch = int((streams[0] or {}).get("channels") or 0) if streams else 0
        if ch < 2:
            return None
    except Exception:
        # Best-effort: if ffprobe fails, still attempt correlation.
        pass

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(in_audio),
        "-t",
        str(float(max_seconds)),
        "-ac",
        "2",
        "-f",
        "f32le",
        "-",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        return None

    buf = p.stdout or b""
    if len(buf) < 8:
        return None

    a = array("f")
    a.frombytes(buf[: len(buf) - (len(buf) % 4)])
    if len(a) < 4:
        return None

    # interleaved stereo: L,R,L,R...
    n_frames = len(a) // 2
    if n_frames <= 1:
        return None

    # Compute means
    sum_l = 0.0
    sum_r = 0.0
    for i in range(n_frames):
        sum_l += float(a[2 * i])
        sum_r += float(a[2 * i + 1])
    mean_l = sum_l / n_frames
    mean_r = sum_r / n_frames

    cov = 0.0
    var_l = 0.0
    var_r = 0.0
    for i in range(n_frames):
        dl = float(a[2 * i]) - mean_l
        dr = float(a[2 * i + 1]) - mean_r
        cov += dl * dr
        var_l += dl * dl
        var_r += dr * dr

    denom = math.sqrt(max(1e-24, var_l * var_r))
    if denom <= 0:
        return None
    corr = cov / denom
    # Clamp for numerical stability.
    return max(-1.0, min(1.0, float(corr)))


def analyze_metering(in_audio: str, *, include_spectral: bool = True) -> AudioMetering:
    loud = measure_lufs_truepeak(in_audio) or {}
    ast = measure_astats(in_audio) or {}
    corr = measure_stereo_correlation(in_audio)

    bands = band_energy_report(in_audio) if include_spectral else None

    # Prefer astats' peak_dbfs for sample peak; loudnorm provides true peak.
    integrated_lufs = float(loud["integrated_lufs"]) if "integrated_lufs" in loud else None
    lra = float(loud["loudness_range_lu"]) if "loudness_range_lu" in loud else None
    tp = float(loud["true_peak_dbtp"]) if "true_peak_dbtp" in loud else None

    peak = float(ast["peak_dbfs"]) if "peak_dbfs" in ast else None
    rms = float(ast["rms_dbfs"]) if "rms_dbfs" in ast else None
    cfl = float(ast["crest_factor_linear"]) if "crest_factor_linear" in ast else None
    cfd = float(ast["crest_factor_db"]) if "crest_factor_db" in ast else None
    dc = float(ast["dc_offset"]) if "dc_offset" in ast else None

    raw = {"loudnorm": loud, "astats": ast, "stereo_correlation": corr}

    return AudioMetering(
        integrated_lufs=integrated_lufs,
        loudness_range_lu=lra,
        true_peak_dbtp=tp,
        peak_dbfs=peak,
        rms_dbfs=rms,
        crest_factor_linear=cfl,
        crest_factor_db=cfd,
        dc_offset=dc,
        stereo_correlation=corr,
        spectral_bands=bands,
        raw=raw,
    )
