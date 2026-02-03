from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from random import Random
from typing import Any

from claw_daw.genre_packs.pipeline import generate_from_genre_pack
from claw_daw.genre_packs.v1 import get_pack_v1
from claw_daw.stylepacks.stylepacks_v1 import get_stylepack
from claw_daw.stylepacks.types import BeatSpec


def _clamp_int(x: Any, lo: int, hi: int, *, default: int) -> int:
    try:
        v = int(x)
    except Exception:
        return default
    return max(lo, min(hi, v))


def _clamp_float(x: Any, lo: float, hi: float, *, default: float) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    return max(lo, min(hi, v))


def normalize_beatspec(spec: BeatSpec) -> BeatSpec:
    sp = get_stylepack(spec.stylepack)

    bpm = spec.bpm if spec.bpm is not None else sp.bpm_default
    bpm = _clamp_int(bpm, sp.bpm_min, sp.bpm_max, default=sp.bpm_default)

    swing = spec.swing_percent if spec.swing_percent is not None else sp.swing_percent
    swing = _clamp_int(swing, 0, 75, default=sp.swing_percent)

    length_bars = _clamp_int(spec.length_bars, 8, 256, default=32)
    max_attempts = _clamp_int(spec.max_attempts, 1, 40, default=6)

    max_similarity = _clamp_float(spec.max_similarity, 0.0, 1.0, default=0.92)
    score_threshold = _clamp_float(spec.score_threshold, 0.0, 1.0, default=0.60)

    knobs = dict(sp.default_knobs)
    knobs.update(spec.knobs or {})

    # clamp common knobs
    knobs["drum_density"] = _clamp_float(knobs.get("drum_density"), 0.05, 1.0, default=float(sp.default_knobs.get("drum_density", 0.8)))
    knobs["lead_density"] = _clamp_float(knobs.get("lead_density"), 0.0, 1.0, default=float(sp.default_knobs.get("lead_density", 0.4)))
    knobs["humanize_timing"] = _clamp_int(knobs.get("humanize_timing"), 0, 30, default=int(sp.default_knobs.get("humanize_timing", 0)))
    knobs["humanize_velocity"] = _clamp_int(knobs.get("humanize_velocity"), 0, 30, default=int(sp.default_knobs.get("humanize_velocity", 0)))

    return replace(
        spec,
        bpm=bpm,
        swing_percent=swing,
        length_bars=length_bars,
        max_attempts=max_attempts,
        max_similarity=max_similarity,
        score_threshold=score_threshold,
        knobs=knobs,
    )


def compile_to_script(
    spec: BeatSpec,
    *,
    out_prefix: str,
    tools_dir: str = "tools",
) -> Path:
    """Compile a BeatSpec into tools/<out_prefix>.txt.

    Implementation strategy (additive):
    - Use Genre Packs v1 generator (deterministic + acceptance + novelty)
    - Then post-process the script to apply stylepack knobs
    """

    sp = get_stylepack(spec.stylepack)
    pack = get_pack_v1(sp.pack)

    # Generate a base script with novelty control.
    base = generate_from_genre_pack(
        pack.name,
        out_prefix=out_prefix,
        seed=int(spec.seed),
        max_attempts=int(spec.max_attempts),
        max_similarity=float(spec.max_similarity),
        write_script=True,
    )

    # Post-process script lines.
    lines = Path(base.script_path).read_text(encoding="utf-8").splitlines()

    # Apply bpm/swing overrides.
    new_lines: list[str] = []
    for ln in lines:
        if ln.startswith("new_project "):
            parts = ln.split()
            if len(parts) >= 3:
                parts[2] = str(int(spec.bpm or pack.bpm_default))
                ln = " ".join(parts)
        if ln.startswith("set_swing "):
            ln = f"set_swing {int(spec.swing_percent or pack.swing_percent)}"
        new_lines.append(ln)

    lines = new_lines

    # Apply palette preset (programs + mixer defaults) for the style.
    # Insert before the first pattern creation, after tracks exist.
    palette_style = pack.name  # reuse pack name tokens
    out: list[str] = []
    inserted = False
    for ln in lines:
        if (not inserted) and ln.startswith("new_pattern "):
            out.append(f"apply_palette {palette_style}")
            inserted = True
        out.append(ln)
    lines = out

    # Apply drum kit selection.
    kit = str(spec.knobs.get("drum_kit") or "")
    if kit:
        patched: list[str] = []
        for ln in lines:
            if ln.startswith("set_kit 0 "):
                # Replace legacy kit label with new drum kit.
                patched.append(f"set_drum_kit 0 {kit}")
                continue
            patched.append(ln)
        lines = patched

    # Apply drum density: rewrite gen_drums lines.
    dd = float(spec.knobs.get("drum_density", 0.8))
    patched = []
    for ln in lines:
        if ln.strip().startswith("gen_drums ") and " density=" in ln:
            # preserve everything else, override density
            import re

            ln = re.sub(r"density=[0-9.]+", f"density={dd:.2f}", ln)
        patched.append(ln)
    lines = patched

    # Apply humanize defaults via set_humanize (drums + bass).
    ht = int(spec.knobs.get("humanize_timing", 0))
    hv = int(spec.knobs.get("humanize_velocity", 0))
    if ht or hv:
        # Insert after track creation block: after last add_track line.
        out: list[str] = []
        inserted = False
        for ln in lines:
            out.append(ln)
            if not inserted and ln.startswith("add_track "):
                # wait until we leave consecutive add_track block
                pass
            if not inserted and ln.startswith("new_pattern "):
                # insert before first pattern creation
                out.insert(len(out) - 1, f"set_humanize 0 timing={ht} velocity={hv} seed={spec.seed}")
                out.insert(len(out) - 1, f"set_humanize 1 timing={max(0, ht-2)} velocity={hv} seed={spec.seed+1}")
                inserted = True
        lines = out

    # Lead density: remove/scale lead placement by chance in scripts that include lead pattern "l".
    ld = float(spec.knobs.get("lead_density", 0.4))
    if ld < 0.99:
        rnd = Random(int(spec.seed) + 991)
        patched = []
        for ln in lines:
            if ln.startswith("add_note_pat ") and " l " in ln and " chance=" not in ln:
                # probabilistic thinning
                chance = max(0.0, min(1.0, ld))
                # add tiny deterministic jitter so multiple notes aren't identical
                jitter = (rnd.random() - 0.5) * 0.10
                patched.append(ln + f" chance={max(0.0, min(1.0, chance + jitter)):.2f}")
            else:
                patched.append(ln)
        lines = patched

    # Optional mix/mastering override.
    # If present, force export_* preset=... so the iteration loop can auto-tune mastering.
    mp = str(spec.knobs.get("mastering_preset") or "").strip()
    if mp:
        patched = []
        for ln in lines:
            s = ln.strip()
            if s.startswith("export_") and " preset=" in s:
                import re

                ln = re.sub(r"preset=[^\s]+", f"preset={mp}", ln)
            elif s.startswith("export_") and (s.startswith("export_mp3") or s.startswith("export_m4a") or s.startswith("export_wav") or s.startswith("export_preview_mp3")):
                ln = ln + f" preset={mp}" if " preset=" not in ln else ln
            patched.append(ln)
        lines = patched

    tool_dir = Path(tools_dir)
    tool_dir.mkdir(parents=True, exist_ok=True)
    script_path = tool_dir / f"{out_prefix}.txt"
    script_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return script_path
