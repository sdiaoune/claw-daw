from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claw_daw.audio.stems import export_stems
from claw_daw.model.types import Project


@dataclass(frozen=True)
class MixSpec:
    """Loose, forwards-compatible mix spec.

    This is intentionally JSON/YAML-friendly and only lightly validated.

    Expected structure (all optional):

    {
      "tracks": {
        "0": {
          "gain_db": -2.0,
          "eq": [{"f": 300, "q": 1.0, "g": -3.0}],
          "comp": {"threshold_db": -18, "ratio": 2, "attack_ms": 5, "release_ms": 50},
          "gate": {"threshold_db": -45},
          "sat": {"type": "tanh", "drive": 1.0},
          "stereo": {"width": 1.2, "low_mono_hz": 120},
          "sends": {"reverb": 0.15, "delay": 0.08}
        }
      },
      "sidechain": [{"src": 0, "dst": 1, "threshold_db": -24, "ratio": 6, "attack_ms": 5, "release_ms": 120}],
      "returns": {
        "reverb": {"predelay_ms": 0, "decay": 0.35},
        "delay": {"ms": 240, "decay": 0.25}
      },
      "master": {
        "eq": [{"f": 9000, "q": 0.7, "g": 1.5}],
        "comp": {"threshold_db": -20, "ratio": 2.5, "attack_ms": 3, "release_ms": 60},
        "limiter": {"limit": 0.98}
      }
    }
    """

    raw: dict[str, Any]

    @staticmethod
    def from_dict(d: dict[str, Any] | None) -> "MixSpec":
        return MixSpec(raw=dict(d or {}))


def _flt(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return int(default)


def _track_fx_chain(spec: dict[str, Any]) -> str:
    """Return an ffmpeg audio filter chain for a single track."""

    chain: list[str] = []

    gain_db = spec.get("gain_db", None)
    if gain_db is not None:
        chain.append(f"volume={_flt(gain_db, 0.0)}dB")

    # Parametric EQ (ffmpeg equalizer supports a peaking filter)
    for b in (spec.get("eq") or []):
        try:
            f = _flt(b.get("f"), 1000.0)
            q = _flt(b.get("q", 1.0), 1.0)
            g = _flt(b.get("g", 0.0), 0.0)
        except Exception:
            continue
        chain.append(f"equalizer=f={f}:t=q:width_type=q:width={q}:g={g}")

    gate = spec.get("gate") or None
    if gate:
        thr = _flt(gate.get("threshold_db", -45.0), -45.0)
        chain.append(f"agate=threshold={thr}dB")

    comp = spec.get("comp") or None
    if comp:
        thr = _flt(comp.get("threshold_db", -18.0), -18.0)
        ratio = _flt(comp.get("ratio", 2.0), 2.0)
        atk = _flt(comp.get("attack_ms", 5.0), 5.0)
        rel = _flt(comp.get("release_ms", 50.0), 50.0)
        chain.append(f"acompressor=threshold={thr}dB:ratio={ratio}:attack={atk}:release={rel}")

    sat = spec.get("sat") or None
    if sat:
        # Minimal deterministic saturation via asoftclip.
        stype = str(sat.get("type", "tanh")).strip().lower()
        if stype not in {"tanh", "atan", "cubic", "clip"}:
            stype = "tanh"
        drive = _flt(sat.get("drive", 1.0), 1.0)
        if abs(drive - 1.0) > 1e-6:
            chain.append(f"volume={drive}")
        chain.append(f"asoftclip=type={stype}")

    stereo = spec.get("stereo") or None
    if stereo:
        width = _flt(stereo.get("width", 1.0), 1.0)
        # Width via mid/side gains; keep mid 1.0, scale side.
        if abs(width - 1.0) > 1e-6:
            chain.append(f"stereotools=mlev=1.0:slev={width}")
        # Note: a true "mono-maker below X Hz" requires a labeled filtergraph; we keep this out of
        # the simple per-track chain for now (see docs for workaround via stems/bus processing).

    return ",".join([c for c in chain if c])


def _master_fx_chain(spec: dict[str, Any]) -> str:
    chain: list[str] = []

    for b in (spec.get("eq") or []):
        try:
            f = _flt(b.get("f"), 1000.0)
            q = _flt(b.get("q", 1.0), 1.0)
            g = _flt(b.get("g", 0.0), 0.0)
        except Exception:
            continue
        chain.append(f"equalizer=f={f}:t=q:width_type=q:width={q}:g={g}")

    comp = spec.get("comp") or None
    if comp:
        thr = _flt(comp.get("threshold_db", -18.0), -18.0)
        ratio = _flt(comp.get("ratio", 2.0), 2.0)
        atk = _flt(comp.get("attack_ms", 5.0), 5.0)
        rel = _flt(comp.get("release_ms", 50.0), 50.0)
        chain.append(f"acompressor=threshold={thr}dB:ratio={ratio}:attack={atk}:release={rel}")

    lim = spec.get("limiter") or None
    if lim:
        limit = _flt(lim.get("limit", 0.98), 0.98)
        chain.append(f"alimiter=limit={limit}")

    return ",".join([c for c in chain if c])


def mix_project_wav(
    project: Project,
    *,
    soundfont: str,
    out_wav: str,
    sample_rate: int = 44100,
    mix: MixSpec | None = None,
) -> str:
    """Render stems then mix with ffmpeg using a MixSpec.

    This is slower than the default renderer, but enables sound-engineering FX
    (EQ, dynamics, sidechain, sends, stereo tools) deterministically.
    """

    mix = MixSpec.from_dict(mix.raw if mix else None) if isinstance(mix, MixSpec) else MixSpec.from_dict((mix or None))
    ms = mix.raw

    outp = Path(out_wav).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="claw_daw_mix_") as td:
        tdir = Path(td)
        stems_dir = tdir / "stems"
        stems = export_stems(project, soundfont=soundfont, out_dir=str(stems_dir), sample_rate=sample_rate)

        # Inputs: one per track stem.
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for s in stems:
            cmd += ["-i", str(s)]

        tracks_spec = (ms.get("tracks") or {})
        returns_spec = (ms.get("returns") or {})
        sidechain_spec = (ms.get("sidechain") or [])
        master_spec = (ms.get("master") or {})
        transient = master_spec.get("transient") or None

        # Build filtergraph.
        # For each input i, produce a labeled stream and keep a mapping of the current label.
        fc: list[str] = []
        labels: dict[int, str] = {}
        for i in range(len(stems)):
            ts = tracks_spec.get(str(i), {}) or {}
            chain = _track_fx_chain(ts)
            out_lbl = f"t{i}"
            labels[i] = out_lbl
            if chain:
                fc.append(f"[{i}:a]{chain}[{out_lbl}]")
            else:
                fc.append(f"[{i}:a]anull[{out_lbl}]")

        # Sidechain: apply to destination track streams.
        # We do this after per-track FX.
        # NOTE: only one rule per dst is supported for now; later rules override earlier.
        sc_by_dst: dict[int, dict[str, Any]] = {}
        for sc in sidechain_spec:
            try:
                dst = _int(sc.get("dst"), -1)
                src = _int(sc.get("src"), -1)
            except Exception:
                continue
            if dst < 0 or src < 0 or dst >= len(stems) or src >= len(stems):
                continue
            sc_by_dst[dst] = dict(sc)

        # If a track is used as a sidechain key *and* also needs to stay audible in the mix,
        # we must split it; ffmpeg filtergraphs consume streams.
        key_srcs = sorted({int(_int(sc.get("src"), -1)) for sc in sc_by_dst.values()} - {-1})
        key_labels: dict[int, str] = {}
        for src in key_srcs:
            if src < 0 or src >= len(stems):
                continue
            base = labels.get(src, f"t{src}")
            dry_lbl = f"{base}_dry"
            key_lbl = f"{base}_key"
            fc.append(f"[{base}]asplit=2[{dry_lbl}][{key_lbl}]")
            labels[src] = dry_lbl
            key_labels[src] = key_lbl

        for dst, sc in sc_by_dst.items():
            src = _int(sc.get("src"), 0)
            thr = _flt(sc.get("threshold_db", -24.0), -24.0)
            ratio = _flt(sc.get("ratio", 6.0), 6.0)
            atk = _flt(sc.get("attack_ms", 5.0), 5.0)
            rel = _flt(sc.get("release_ms", 120.0), 120.0)
            main_lbl = labels.get(dst, f"t{dst}")
            key_lbl = key_labels.get(src, labels.get(src, f"t{src}"))
            out_lbl = f"t{dst}_sc"
            # sidechaincompress takes 2 inputs: main and sidechain.
            fc.append(f"[{main_lbl}][{key_lbl}]sidechaincompress=threshold={thr}dB:ratio={ratio}:attack={atk}:release={rel}[{out_lbl}]")
            labels[dst] = out_lbl

        # Sends/returns: support two fixed returns: reverb and delay.
        # We implement this as: per-track taps mixed into returns.
        send_reverb: list[str] = []
        send_delay: list[str] = []
        drys: list[str] = []
        for i in range(len(stems)):
            ts = tracks_spec.get(str(i), {}) or {}
            sends = (ts.get("sends") or {})
            r = _flt(sends.get("reverb", 0.0), 0.0)
            d = _flt(sends.get("delay", 0.0), 0.0)
            base_lbl = labels.get(i, f"t{i}")

            if r > 0 or d > 0:
                # We need both dry + one or more send taps, so split the stream.
                outs: list[str] = [f"dry{i}"]
                if r > 0:
                    outs.append(f"tapR{i}")
                if d > 0:
                    outs.append(f"tapD{i}")
                fc.append(f"[{base_lbl}]asplit={len(outs)}" + "".join([f"[{o}]" for o in outs]))
                drys.append(f"[dry{i}]")
                if r > 0:
                    fc.append(f"[tapR{i}]volume={r}[sr{i}]")
                    send_reverb.append(f"[sr{i}]")
                if d > 0:
                    fc.append(f"[tapD{i}]volume={d}[sd{i}]")
                    send_delay.append(f"[sd{i}]")
            else:
                drys.append(f"[{base_lbl}]")

        # Build return effects
        ret_streams: list[str] = []
        if send_reverb:
            rev = returns_spec.get("reverb", {}) or {}
            decay = _flt(rev.get("decay", 0.35), 0.35)
            predelay = _flt(rev.get("predelay_ms", 0.0), 0.0)
            # crude: aecho with short multi-tap
            ms1 = max(1.0, 30.0 + predelay)
            ms2 = max(1.0, 70.0 + predelay)
            fc.append(
                f"{''.join(send_reverb)}amix=inputs={len(send_reverb)}:normalize=0," +
                f"aecho=0.8:0.9:{ms1}|{ms2}:{decay}|{max(0.05,decay*0.7)}[rev]"
            )
            ret_streams.append("[rev]")

        if send_delay:
            dly = returns_spec.get("delay", {}) or {}
            msd = _flt(dly.get("ms", 240.0), 240.0)
            decay = _flt(dly.get("decay", 0.25), 0.25)
            fc.append(
                f"{''.join(send_delay)}amix=inputs={len(send_delay)}:normalize=0,"
                f"aecho=0.8:0.9:{msd}:{decay}[dly]"
            )
            ret_streams.append("[dly]")

        # Sum dry + returns.
        mix_inputs = drys + ret_streams
        # normalize=0 to keep deterministic levels; limiter later.
        fc.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0[mix]")

        # Master FX from spec.
        mchain = _master_fx_chain(master_spec)
        if mchain:
            fc.append(f"[mix]{mchain}[mix2]")
            final = "[mix2]"
        else:
            final = "[mix]"

        # Always add a limiter safety net at the end of the mix stage.
        fc.append(f"{final}alimiter=limit=0.98[out]")

        filter_complex = ";".join(fc)

        cmd += ["-filter_complex", filter_complex, "-map", "[out]", "-ar", str(int(sample_rate)), str(outp)]
        subprocess.run(cmd, check=True)

        # Optional master transient shaping (python). This runs before mastering presets.
        if transient:
            from claw_daw.audio.transient import TransientSpec, transient_shaper_wav

            atk = _flt(transient.get("attack", 0.0), 0.0)
            sus = _flt(transient.get("sustain", 0.0), 0.0)
            if abs(atk) > 1e-6 or abs(sus) > 1e-6:
                tmp2 = tdir / "mix_transient.wav"
                transient_shaper_wav(str(outp), str(tmp2), spec=TransientSpec(attack=atk, sustain=sus), sample_rate=sample_rate)
                Path(tmp2).replace(outp)

    return str(outp)
