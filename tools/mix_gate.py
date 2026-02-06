#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_presets(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Mix QA gate for claw-daw meter_audio JSON.")
    ap.add_argument("meter_json", help="Path to meter JSON (from meter_audio)")
    ap.add_argument("--preset", default="edm_streaming", help="Preset name in tools/mix_presets.json")
    ap.add_argument("--presets", default="tools/mix_presets.json", help="Preset file path")
    ap.add_argument("--target", choices=["club", "streaming"], default=None, help="Legacy alias for preset loudness")
    ap.add_argument("--lufs-min", type=float, default=None)
    ap.add_argument("--lufs-max", type=float, default=None)
    ap.add_argument("--true-peak-max", type=float, default=None)
    ap.add_argument("--crest-min", type=float, default=6.0)
    ap.add_argument("--stereo-corr-min", type=float, default=None)
    ap.add_argument("--stereo-balance-max", type=float, default=None)
    ap.add_argument("--dc-offset-max", type=float, default=None)
    ap.add_argument("--spectral-tilt-min", type=float, default=None)
    ap.add_argument("--spectral-tilt-max", type=float, default=None)
    args = ap.parse_args()

    data = _load_json(args.meter_json)

    # Load preset defaults.
    presets = _load_presets(args.presets)
    if args.target:
        args.preset = f"edm_{args.target}"
    if args.preset not in presets:
        raise SystemExit(f"Unknown preset: {args.preset}")

    gates = (presets.get(args.preset) or {}).get("gates") or {}
    master = gates.get("master") or {}

    lufs_min = args.lufs_min if args.lufs_min is not None else master.get("lufs_min", -15.5)
    lufs_max = args.lufs_max if args.lufs_max is not None else master.get("lufs_max", -12.5)
    true_peak_max = args.true_peak_max if args.true_peak_max is not None else master.get("true_peak_max", -1.0)
    stereo_corr_min = args.stereo_corr_min if args.stereo_corr_min is not None else master.get("stereo_corr_min", -0.2)
    stereo_balance_max = args.stereo_balance_max if args.stereo_balance_max is not None else master.get("stereo_balance_max", 1.5)
    dc_offset_max = args.dc_offset_max if args.dc_offset_max is not None else master.get("dc_offset_max", 0.02)
    spectral_tilt_min = args.spectral_tilt_min if args.spectral_tilt_min is not None else master.get("spectral_tilt_min", None)
    spectral_tilt_max = args.spectral_tilt_max if args.spectral_tilt_max is not None else master.get("spectral_tilt_max", None)

    metrics = {
        "integrated_lufs": _f(data.get("integrated_lufs")),
        "true_peak_dbtp": _f(data.get("true_peak_dbtp")),
        "crest_factor_db": _f(data.get("crest_factor_db")),
        "stereo_correlation": _f(data.get("stereo_correlation")),
        "stereo_balance_db": _f(data.get("stereo_balance_db")),
        "dc_offset": _f(data.get("dc_offset")),
        "spectral_tilt_db": _f(data.get("spectral_tilt_db")),
    }

    checks = []

    # Integrated LUFS
    lufs = metrics["integrated_lufs"]
    if lufs is None:
        checks.append(("integrated_lufs", False, "missing"))
    else:
        ok = lufs_min <= lufs <= lufs_max
        checks.append(("integrated_lufs", ok, f"{lufs:.2f} (target {lufs_min}..{lufs_max})"))

    # True peak
    tp = metrics["true_peak_dbtp"]
    if tp is None:
        checks.append(("true_peak_dbtp", False, "missing"))
    else:
        ok = tp <= true_peak_max
        checks.append(("true_peak_dbtp", ok, f"{tp:.2f} dBTP (<= {true_peak_max})"))

    # Crest factor
    cf = metrics["crest_factor_db"]
    if cf is None:
        checks.append(("crest_factor_db", False, "missing"))
    else:
        ok = cf >= args.crest_min
        checks.append(("crest_factor_db", ok, f"{cf:.2f} dB (>= {args.crest_min})"))

    # Stereo correlation
    corr = metrics["stereo_correlation"]
    if corr is None:
        checks.append(("stereo_correlation", False, "missing"))
    else:
        ok = corr >= stereo_corr_min
        checks.append(("stereo_correlation", ok, f"{corr:.2f} (>= {stereo_corr_min})"))

    # Stereo balance
    bal = metrics["stereo_balance_db"]
    if bal is None:
        checks.append(("stereo_balance_db", False, "missing"))
    else:
        ok = abs(bal) <= stereo_balance_max
        checks.append(("stereo_balance_db", ok, f"{bal:.2f} dB (<= {stereo_balance_max})"))

    # DC offset
    dc = metrics["dc_offset"]
    if dc is None:
        checks.append(("dc_offset", False, "missing"))
    else:
        ok = abs(dc) <= dc_offset_max
        checks.append(("dc_offset", ok, f"{dc:.4f} (<= {dc_offset_max})"))

    # Spectral tilt
    tilt = metrics["spectral_tilt_db"]
    if spectral_tilt_min is not None or spectral_tilt_max is not None:
        if tilt is None:
            checks.append(("spectral_tilt_db", False, "missing"))
        else:
            ok = True
            if spectral_tilt_min is not None and tilt < spectral_tilt_min:
                ok = False
            if spectral_tilt_max is not None and tilt > spectral_tilt_max:
                ok = False
            checks.append(("spectral_tilt_db", ok, f"{tilt:.2f} dB (target {spectral_tilt_min}..{spectral_tilt_max})"))

    any_fail = any(not ok for _, ok, _ in checks)

    print(f"mix_gate: {args.meter_json} preset={args.preset}")
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"- {name}: {status} {detail}")

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
