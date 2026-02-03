from __future__ import annotations

from pathlib import Path

from claw_daw.stylepacks.compile import compile_to_script
from claw_daw.stylepacks.types import BeatSpec


def test_compile_overrides_export_mastering_preset(tmp_path: Path) -> None:
    spec = BeatSpec(
        name="x",
        stylepack="trap_2020s",  # type: ignore[arg-type]
        seed=123,
        max_attempts=1,
        knobs={"mastering_preset": "clean"},
    )

    script_path = compile_to_script(spec, out_prefix="t", tools_dir=str(tmp_path))
    txt = script_path.read_text(encoding="utf-8")

    # We should force preset=clean on all export lines that include a preset.
    assert "export_" in txt
    assert "preset=clean" in txt
