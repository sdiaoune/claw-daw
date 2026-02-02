from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claw_daw.cli.headless import HeadlessRunner
from claw_daw.model.types import Project
from claw_daw.prompt.parse import parse_prompt
from claw_daw.prompt.script import brief_to_script
from claw_daw.prompt.similarity import project_similarity
from claw_daw.audio.spectrogram import band_energy_report


@dataclass(frozen=True)
class GenerationResult:
    brief_title: str
    out_prefix: str
    script_path: Path
    iterations: int
    similarities: list[float]
    # If rendered, path to last preview.
    preview_path: Path | None = None
    audio_reports: list[dict] | None = None


def _run_script_to_project(lines: list[str], *, base_dir: Path) -> Project:
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(lines, base_dir=base_dir)
    return r.require_project()


def generate_from_prompt(
    prompt: str,
    *,
    out_prefix: str,
    tools_dir: str = "tools",
    max_iters: int = 3,
    seed: int = 0,
    max_similarity: float | None = None,
    write_script: bool = True,
    # Closed-loop options
    soundfont: str | None = None,
    render: bool = False,
    preview_bars: int = 8,
    auto_tune: bool = True,
) -> GenerationResult:
    """Prompt→brief→script generator.

    Improvements included:
    - prompt→structured brief
    - style parameterization
    - default sound/palette selection hooks
    - novelty constraints via project similarity scoring
    - optional closed-loop preview→analyze→auto-tune iteration
    """

    brief = parse_prompt(prompt, title=out_prefix)
    if max_similarity is not None:
        brief.novelty = type(brief.novelty)(max_similarity=float(max_similarity))

    tool_dir_path = Path(tools_dir)
    tool_dir_path.mkdir(parents=True, exist_ok=True)
    script_path = tool_dir_path / f"{out_prefix}.txt"

    prev: Project | None = None
    similarities: list[float] = []
    audio_reports: list[dict] = []

    # Auto-tune state (simple mix + mastering choices)
    volumes: dict[str, int] = {}
    mastering_preset: str | None = None

    chosen_script = None
    chosen_seed = seed

    preview_path: Path | None = None

    for i in range(max(1, int(max_iters))):
        cur_seed = int(seed) + i
        gen = brief_to_script(
            brief,
            seed=cur_seed,
            out_prefix=out_prefix,
            mastering_preset=mastering_preset,
            volumes=volumes,
        )
        lines = gen.script.splitlines()
        proj = _run_script_to_project(lines, base_dir=Path.cwd())

        sim = 0.0
        if prev is not None:
            sim = project_similarity(prev, proj)
            similarities.append(sim)

        novelty_ok = prev is None or sim <= float(brief.novelty.max_similarity)
        chosen_script = gen.script
        chosen_seed = cur_seed

        # Closed-loop: render a short preview and analyze it.
        if render:
            if not soundfont:
                raise ValueError("render=True requires soundfont=...")

            # Rewrite preview bars in script without changing the generator.
            # (export_preview_mp3 already exists in the script.)
            rewritten: list[str] = []
            for ln in lines:
                if ln.strip().startswith("export_preview_mp3 "):
                    parts = ln.split()
                    # keep out path, override bars
                    outp = parts[1]
                    rewritten.append(f"export_preview_mp3 {outp} bars={int(preview_bars)} start=0:0 preset={gen.mastering_preset}")
                else:
                    rewritten.append(ln)

            r = HeadlessRunner(soundfont=str(Path(soundfont).expanduser().resolve()), strict=True, dry_run=False)
            r.run_lines(rewritten, base_dir=Path.cwd())

            preview_path = Path("out") / f"{out_prefix}.preview.mp3"
            if preview_path.exists():
                rep = band_energy_report(str(preview_path))
                audio_reports.append(rep)

                if auto_tune:
                    # Heuristic 1: too much sub → reduce bass
                    sub = float(rep["sub_lt90"]["mean_volume"])
                    rest = float(rep["rest_ge90"]["mean_volume"])
                    full = float(rep["full"]["mean_volume"])

                    if sub - rest > 6.0:
                        volumes["bass"] = max(60, int(volumes.get("bass", 105)) - 10)

                    # Heuristic 2: overall too quiet → switch to demo preset
                    if full < -30.0:
                        mastering_preset = "demo"

        # Stop early if novelty constraint met (and we at least did one comparison).
        if prev is not None and novelty_ok:
            break

        prev = proj

    if chosen_script is None:
        chosen_script = brief_to_script(brief, seed=chosen_seed, out_prefix=out_prefix).script

    if write_script:
        script_path.write_text(chosen_script, encoding="utf-8")

    return GenerationResult(
        brief_title=brief.title,
        out_prefix=out_prefix,
        script_path=script_path,
        iterations=max(1, int(max_iters)),
        similarities=similarities,
        preview_path=preview_path,
        audio_reports=audio_reports or None,
    )
