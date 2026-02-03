from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from claw_daw.cli.headless import HeadlessRunner
from claw_daw.genre_packs.acceptance import AcceptanceFailure
from claw_daw.genre_packs.v1 import get_pack_v1
from claw_daw.prompt.similarity import project_similarity
from claw_daw.stylepacks.compile import compile_to_script, normalize_beatspec
from claw_daw.stylepacks.io import beatspec_to_dict, save_report_json
from claw_daw.audio.sanity import MixSanity, analyze_mix_sanity
from claw_daw.stylepacks.score import spectral_balance_score
from claw_daw.stylepacks.stylepacks_v1 import get_stylepack
from claw_daw.stylepacks.types import AttemptReport, BeatSpec


def _tweak_knobs_for_retry(spec: BeatSpec, attempt: int) -> BeatSpec:
    """If scoring is poor, adjust a few parameters deterministically."""

    knobs = dict(spec.knobs)

    # Increase humanization gradually.
    knobs["humanize_timing"] = int(knobs.get("humanize_timing", 0)) + 2
    knobs["humanize_velocity"] = int(knobs.get("humanize_velocity", 0)) + 2

    # Reduce lead density a bit (less busy highs).
    knobs["lead_density"] = max(0.10, float(knobs.get("lead_density", 0.4)) - 0.10)

    # If still failing later attempts, swap drum kit to change overall tone.
    if attempt >= 2:
        cur = str(knobs.get("drum_kit") or "trap_hard")
        cycle = ["trap_hard", "house_clean", "boombap_dusty", "gm_basic"]
        if cur in cycle:
            knobs["drum_kit"] = cycle[(cycle.index(cur) + 1) % len(cycle)]

    # Nudge drum density down if too busy.
    if attempt >= 1:
        knobs["drum_density"] = max(0.40, float(knobs.get("drum_density", 0.8)) - 0.05)

    return BeatSpec(
        name=spec.name,
        stylepack=spec.stylepack,
        seed=spec.seed,
        max_attempts=spec.max_attempts,
        length_bars=spec.length_bars,
        bpm=spec.bpm,
        swing_percent=spec.swing_percent,
        knobs=knobs,
        score_threshold=spec.score_threshold,
        max_similarity=spec.max_similarity,
    )


def _autofix_for_mix_sanity(spec: BeatSpec, sanity: MixSanity | None, attempt: int) -> BeatSpec:
    """Deterministic small mix/mastering fixes based on audio analysis.

    This is intentionally conservative: it tweaks a few stylepack knobs and
    optionally forces a mastering preset. It never uses randomness.
    """

    if sanity is None:
        return spec

    knobs = dict(spec.knobs)

    mean_db = float(sanity.metrics.get("mean_dbfs", 0.0))
    max_db = float(sanity.metrics.get("max_dbfs", 0.0))
    silence = float(sanity.metrics.get("silence_fraction", 0.0))

    # Mostly silent? Increase densities and choose a louder preset.
    if silence >= 0.50 or mean_db < -40.0:
        knobs["drum_density"] = min(1.0, float(knobs.get("drum_density", 0.8)) + 0.10)
        knobs["lead_density"] = min(1.0, float(knobs.get("lead_density", 0.4)) + 0.10)
        knobs["mastering_preset"] = "demo"

    # Too hot / near clipping? Back off brightness and choose the safer preset.
    if max_db >= -1.0 or mean_db > -10.0:
        knobs["lead_density"] = max(0.05, float(knobs.get("lead_density", 0.4)) - 0.10)
        knobs["drum_density"] = max(0.30, float(knobs.get("drum_density", 0.8)) - 0.05)
        knobs["mastering_preset"] = "clean"

    # If harsh highs, thin leads a bit and optionally switch to "lofi" later.
    if any("highs dominate" in r for r in sanity.reasons):
        knobs["lead_density"] = max(0.05, float(knobs.get("lead_density", 0.4)) - 0.10)
        if attempt >= 1:
            knobs["mastering_preset"] = str(knobs.get("mastering_preset") or "lofi")

    # If boomy lows, nudge drum density down slightly (often kick/808).
    if any("lows dominate" in r for r in sanity.reasons):
        knobs["drum_density"] = max(0.25, float(knobs.get("drum_density", 0.8)) - 0.05)
        if attempt >= 2:
            knobs["mastering_preset"] = "clean"

    return BeatSpec(
        name=spec.name,
        stylepack=spec.stylepack,
        seed=spec.seed,
        max_attempts=spec.max_attempts,
        length_bars=spec.length_bars,
        bpm=spec.bpm,
        swing_percent=spec.swing_percent,
        knobs=knobs,
        score_threshold=spec.score_threshold,
        max_similarity=spec.max_similarity,
    )


def run_stylepack(
    spec: BeatSpec,
    *,
    out_prefix: str,
    soundfont: str,
    base_dir: str | Path = ".",
    tools_dir: str = "tools",
    out_dir: str = "out",
) -> str:
    """Generate + render + score + iterate; write out/<name>.report.json."""

    base = Path(base_dir)
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    spec = normalize_beatspec(spec)
    sp = get_stylepack(spec.stylepack)
    pack = get_pack_v1(sp.pack)

    attempts: list[AttemptReport] = []

    prev_proj = None
    best_idx = None
    best_score = -1.0

    cur_spec = spec

    for attempt in range(int(spec.max_attempts)):
        # compile (writes tools/<out_prefix>.txt)
        script_path = compile_to_script(cur_spec, out_prefix=out_prefix, tools_dir=tools_dir)

        # render (fast path for scoring): preview only
        r = HeadlessRunner(soundfont=str(Path(soundfont).expanduser().resolve()), strict=True, dry_run=False)
        lines = Path(script_path).read_text(encoding="utf-8").splitlines()

        preview_only: list[str] = []
        for ln in lines:
            s = ln.strip()
            if s.startswith("export_mp3") or s.startswith("export_wav") or s.startswith("export_m4a"):
                continue
            preview_only.append(ln)

        r.run_lines(preview_only, base_dir=base)
        proj = r.require_project()

        # acceptance (genre pack)
        acceptance_ok = True
        acceptance_errors: list[str] = []
        try:
            pack.accept(proj)
        except AcceptanceFailure as e:
            acceptance_ok = False
            acceptance_errors = list(getattr(e, "errors", []) or [str(e)])

        # similarity to previous attempt
        sim = None
        if prev_proj is not None:
            sim = float(project_similarity(prev_proj, proj))

        prev_proj = proj

        # spectral score (preview preferred if available)
        preview = Path(out_dir) / f"{out_prefix}.preview.mp3"
        full = Path(out_dir) / f"{out_prefix}.mp3"
        audio_path = preview if preview.exists() else full

        spectral = None
        sanity: MixSanity | None = None
        score = None
        if audio_path.exists():
            ss = spectral_balance_score(str(audio_path))
            spectral = {"score": ss.score, "reasons": ss.reasons, "bands": ss.report}

            sanity = analyze_mix_sanity(str(audio_path))

            # Integrate as a gate: the final score is bounded by both.
            score = float(min(ss.score, sanity.score))

        attempts.append(
            AttemptReport(
                attempt=attempt,
                seed=int(cur_spec.seed) + attempt,
                knobs=dict(cur_spec.knobs),
                acceptance_ok=acceptance_ok,
                acceptance_errors=acceptance_errors,
                similarity_to_prev=sim,
                spectral=spectral,
                sanity=(sanity.to_dict() if sanity else None),
                score=score,
            )
        )

        # track best
        if score is not None and score > best_score and acceptance_ok:
            best_score = score
            best_idx = attempt

        # stop if good enough
        if acceptance_ok and score is not None and score >= float(spec.score_threshold):
            best_idx = attempt
            break

        # tweak and retry: first address obvious mix issues, then apply generic knob tweaks.
        cur_spec = _autofix_for_mix_sanity(cur_spec, sanity, attempt)
        cur_spec = _tweak_knobs_for_retry(cur_spec, attempt)

    # mark chosen
    if best_idx is not None and 0 <= best_idx < len(attempts):
        attempts[best_idx] = AttemptReport(**{**asdict(attempts[best_idx]), "chosen": True})  # type: ignore[arg-type]

    # Final render: rerun the chosen attempt script including full MP3 export.
    # Note: we render from the chosen attempt knobs directly so that any
    # auto-fixes (e.g. mastering preset overrides) are faithfully reproduced.
    if best_idx is not None:
        final_knobs = dict(attempts[best_idx].knobs) if 0 <= best_idx < len(attempts) else dict(spec.knobs)
        final_spec = BeatSpec(
            name=spec.name,
            stylepack=spec.stylepack,
            seed=spec.seed,
            max_attempts=spec.max_attempts,
            length_bars=spec.length_bars,
            bpm=spec.bpm,
            swing_percent=spec.swing_percent,
            knobs=final_knobs,
            score_threshold=spec.score_threshold,
            max_similarity=spec.max_similarity,
        )

        final_script = compile_to_script(final_spec, out_prefix=out_prefix, tools_dir=tools_dir)
        r = HeadlessRunner(soundfont=str(Path(soundfont).expanduser().resolve()), strict=True, dry_run=False)
        final_lines = Path(final_script).read_text(encoding="utf-8").splitlines()
        r.run_lines(final_lines, base_dir=base)

    report = {
        "name": out_prefix,
        "stylepack": sp.name,
        "pack": pack.name,
        "beatspec": beatspec_to_dict(spec),
        "attempts": [asdict(a) for a in attempts],
        "best_attempt": best_idx,
    }

    return save_report_json(Path(out_dir) / f"{out_prefix}.report.json", report)
