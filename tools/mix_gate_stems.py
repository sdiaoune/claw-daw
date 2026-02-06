#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from claw_daw.audio.metering import analyze_metering

from mix_utils import classify_track


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _load_audio_list(stem_dir: Path, bus_dir: Path | None):
    files = []
    if not stem_dir.exists():
        raise FileNotFoundError(f"missing stems dir: {stem_dir}")
    files += sorted(stem_dir.glob("*.wav"))
    if bus_dir is not None:
        if not bus_dir.exists():
            raise FileNotFoundError(f"missing busses dir: {bus_dir}")
        files += sorted(bus_dir.glob("*.wav"))
    return files


def _load_presets(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(name, ok, detail):
    status = "PASS" if ok else "FAIL"
    return (name, ok, f"{status} {detail}")


def _role_from_filename(name: str) -> str:
    # Use track role classifier on filename tokens.
    base = name.lower().replace(".wav", "")
    # strip numeric prefix: "00_"
    base = base.split("_", 1)[1] if "_" in base and base.split("_", 1)[0].isdigit() else base
    return classify_track(base).role


def main():
    ap = argparse.ArgumentParser(description="Stem/bus QA gate for claw-daw renders.")
    ap.add_argument("stem_dir", help="Directory with stems (e.g. out/<name>_stems)")
    ap.add_argument("--bus-dir", default=None, help="Optional busses dir (e.g. out/<name>_busses)")
    ap.add_argument("--preset", default="edm_streaming", help="Preset name in tools/mix_presets.json")
    ap.add_argument("--presets", default="tools/mix_presets.json", help="Preset file path")
    ap.add_argument("--lufs-guidance", action="store_true", help="Enable per-stem LUFS guidance")
    ap.add_argument("--true-peak-max", type=float, default=None)
    ap.add_argument("--peak-max", type=float, default=None)
    ap.add_argument("--crest-min", type=float, default=None)
    ap.add_argument("--stereo-corr-min", type=float, default=None)
    ap.add_argument("--stereo-balance-max", type=float, default=None)
    ap.add_argument("--dc-offset-max", type=float, default=None)
    args = ap.parse_args()

    presets = _load_presets(Path(args.presets))
    if args.preset not in presets:
        raise SystemExit(f"Unknown preset: {args.preset}")

    gates = (presets.get(args.preset) or {}).get("gates") or {}
    stems_gate = gates.get("stems") or {}

    true_peak_max = args.true_peak_max if args.true_peak_max is not None else stems_gate.get("true_peak_max", -3.0)
    peak_max = args.peak_max if args.peak_max is not None else stems_gate.get("peak_max", -3.0)
    crest_min = args.crest_min if args.crest_min is not None else stems_gate.get("crest_min", 3.0)
    stereo_corr_min = args.stereo_corr_min if args.stereo_corr_min is not None else stems_gate.get("stereo_corr_min", -0.5)
    stereo_balance_max = args.stereo_balance_max if args.stereo_balance_max is not None else stems_gate.get("stereo_balance_max", 4.0)
    dc_offset_max = args.dc_offset_max if args.dc_offset_max is not None else stems_gate.get("dc_offset_max", 0.02)
    lufs_guidance = stems_gate.get("lufs_guidance") or {}

    stem_dir = Path(args.stem_dir)
    bus_dir = Path(args.bus_dir) if args.bus_dir else None

    try:
        files = _load_audio_list(stem_dir, bus_dir)
    except FileNotFoundError as e:
        print(f"mix_gate_stems: FAIL {e}")
        return 1

    if not files:
        print("mix_gate_stems: FAIL no stems/busses found")
        return 1

    any_fail = False
    print(f"mix_gate_stems: stems={stem_dir} busses={bus_dir if bus_dir else '-'} preset={args.preset}")

    for wav in files:
        rep = analyze_metering(str(wav), include_spectral=False)
        metrics = {
            "integrated_lufs": _f(rep.integrated_lufs),
            "true_peak_dbtp": _f(rep.true_peak_dbtp),
            "peak_dbfs": _f(rep.peak_dbfs),
            "crest_factor_db": _f(rep.crest_factor_db),
            "stereo_correlation": _f(rep.stereo_correlation),
            "stereo_balance_db": _f(rep.stereo_balance_db),
            "dc_offset": _f(rep.dc_offset),
        }

        checks = []
        tp = metrics["true_peak_dbtp"]
        if tp is None:
            checks.append(_check("true_peak_dbtp", False, "missing"))
        else:
            checks.append(_check("true_peak_dbtp", tp <= true_peak_max, f"{tp:.2f} dBTP (<= {true_peak_max})"))

        pk = metrics["peak_dbfs"]
        if pk is None:
            checks.append(_check("peak_dbfs", False, "missing"))
        else:
            checks.append(_check("peak_dbfs", pk <= peak_max, f"{pk:.2f} dBFS (<= {peak_max})"))

        cf = metrics["crest_factor_db"]
        if cf is None:
            checks.append(_check("crest_factor_db", False, "missing"))
        else:
            checks.append(_check("crest_factor_db", cf >= crest_min, f"{cf:.2f} dB (>= {crest_min})"))

        corr = metrics["stereo_correlation"]
        if corr is None:
            checks.append(_check("stereo_correlation", False, "missing"))
        else:
            checks.append(_check("stereo_correlation", corr >= stereo_corr_min, f"{corr:.2f} (>= {stereo_corr_min})"))

        bal = metrics["stereo_balance_db"]
        if bal is None:
            checks.append(_check("stereo_balance_db", False, "missing"))
        else:
            checks.append(_check("stereo_balance_db", abs(bal) <= stereo_balance_max, f"{bal:.2f} dB (<= {stereo_balance_max})"))

        dc = metrics["dc_offset"]
        if dc is None:
            checks.append(_check("dc_offset", False, "missing"))
        else:
            checks.append(_check("dc_offset", abs(dc) <= dc_offset_max, f"{dc:.4f} (<= {dc_offset_max})"))

        # Optional LUFS guidance by role (wide, but hard-fail when enabled).
        if args.lufs_guidance and lufs_guidance:
            role = _role_from_filename(wav.name)
            guide = lufs_guidance.get(role) or lufs_guidance.get("music")
            if guide:
                lufs = metrics["integrated_lufs"]
                if lufs is None:
                    checks.append(_check("integrated_lufs", False, "missing"))
                else:
                    ok = guide["min"] <= lufs <= guide["max"]
                    checks.append(_check("integrated_lufs", ok, f"{lufs:.2f} (target {guide['min']}..{guide['max']})"))

        file_fail = any(not ok for _, ok, _ in checks)
        any_fail = any_fail or file_fail

        print(f"- {wav.name}")
        for _, _, detail in checks:
            print(f"  {detail}")

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
