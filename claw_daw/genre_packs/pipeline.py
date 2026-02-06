from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claw_daw.cli.headless import HeadlessRunner
from claw_daw.genre_packs.v1 import get_pack_v1
from claw_daw.model.types import Project
from claw_daw.prompt.similarity import project_similarity


@dataclass(frozen=True)
class PackGenerationResult:
    pack: str
    out_prefix: str
    script_path: Path
    attempts: int
    similarities: list[float]


def _run_script_to_project(lines: list[str], *, base_dir: Path | None) -> Project:
    r = HeadlessRunner(soundfont=None, strict=True, dry_run=True)
    r.run_lines(lines, base_dir=base_dir)
    return r.require_project()


def generate_from_genre_pack(
    pack_name: str,
    *,
    out_prefix: str,
    tools_dir: str = "tools",
    seed: int = 0,
    max_attempts: int = 6,
    max_similarity: float | None = 0.92,
    write_script: bool = True,
) -> PackGenerationResult:
    """Generate a headless script using a Genre Pack.

    Determinism:
      (pack_name, seed, attempt_index) -> identical output.

    Novelty control:
      If max_similarity is provided, each subsequent attempt must be <= max_similarity
      vs the previous attempt.

    Acceptance:
      Pack-specific tests must pass before returning.
    """

    pack = get_pack_v1(pack_name)

    tool_dir_path = Path(tools_dir)
    tool_dir_path.mkdir(parents=True, exist_ok=True)
    script_path = tool_dir_path / f"{out_prefix}.txt"

    prev: Project | None = None
    similarities: list[float] = []

    chosen_script: str | None = None

    for attempt in range(max(1, int(max_attempts))):
        script = pack.generator(int(seed), int(attempt), out_prefix)
        proj = _run_script_to_project(script.splitlines(), base_dir=Path.cwd())

        # Acceptance tests (must pass)
        pack.accept(proj)

        # First accepted attempt becomes the reference.
        if prev is None:
            prev = proj
            chosen_script = script
            if max_similarity is None:
                break
            continue

        sim = project_similarity(prev, proj)
        similarities.append(sim)
        chosen_script = script
        if sim <= float(max_similarity):
            break

        prev = proj

    if chosen_script is None:
        # last resort: accept the final attempt (acceptance already passed) even if too similar
        chosen_script = script  # type: ignore[possibly-undefined]

    if write_script:
        script_path.write_text(chosen_script, encoding="utf-8")

    return PackGenerationResult(
        pack=str(pack_name),
        out_prefix=str(out_prefix),
        script_path=script_path,
        attempts=max(1, int(max_attempts)),
        similarities=similarities,
    )
