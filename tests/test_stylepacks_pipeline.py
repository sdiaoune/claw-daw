from __future__ import annotations

from claw_daw.stylepacks.types import BeatSpec
from claw_daw.stylepacks.compile import normalize_beatspec


def test_stylepack_normalization_clamps() -> None:
    spec = BeatSpec(
        name="x",
        stylepack="trap_2020s",  # type: ignore[arg-type]
        bpm=999,
        swing_percent=999,
        length_bars=1,
        max_attempts=999,
        knobs={"drum_density": 9, "lead_density": -1, "humanize_timing": 999, "humanize_velocity": -2},
    )
    n = normalize_beatspec(spec)
    assert 140 <= int(n.bpm or 0) <= 165
    assert 0 <= int(n.swing_percent or 0) <= 75
    assert n.length_bars >= 8
    assert n.max_attempts <= 40
    assert 0.05 <= float(n.knobs["drum_density"]) <= 1.0
    assert 0.0 <= float(n.knobs["lead_density"]) <= 1.0
    assert 0 <= int(n.knobs["humanize_timing"]) <= 30
    assert 0 <= int(n.knobs["humanize_velocity"]) <= 30
