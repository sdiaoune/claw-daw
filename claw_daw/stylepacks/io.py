from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from claw_daw.stylepacks.types import BeatSpec


def load_beatspec_yaml(path: str | Path) -> BeatSpec:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("BeatSpec YAML must be a mapping/object")

    name = str(data.get("name") or p.stem)
    stylepack = data.get("stylepack")
    if stylepack is None:
        raise ValueError("BeatSpec YAML missing required field: stylepack")

    spec = BeatSpec(
        name=name,
        stylepack=str(stylepack),  # type: ignore[arg-type]
        seed=int(data.get("seed", 0)),
        max_attempts=int(data.get("max_attempts", data.get("attempts", 6))),
        length_bars=int(data.get("length_bars", 32)),
        bpm=data.get("bpm"),
        swing_percent=data.get("swing_percent"),
        knobs=dict(data.get("knobs") or {}),
        score_threshold=float(data.get("score_threshold", 0.60)),
        max_similarity=float(data.get("max_similarity", 0.92)),
    )

    # Normalize optional ints
    if spec.bpm is not None:
        spec.bpm = int(spec.bpm)
    if spec.swing_percent is not None:
        spec.swing_percent = int(spec.swing_percent)

    return spec


def save_report_json(path: str | Path, report: dict[str, Any]) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    import json

    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return str(out)


def beatspec_to_dict(spec: BeatSpec) -> dict[str, Any]:
    return asdict(spec)
