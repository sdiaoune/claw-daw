from __future__ import annotations

from claw_daw.prompt.types import StyleName, StylePreset


STYLE_PRESETS: dict[StyleName, StylePreset] = {
    "hiphop": StylePreset(style="hiphop", bpm_default=74, swing_percent=18, drum_density=0.72, mastering_preset="clean"),
    "lofi": StylePreset(style="lofi", bpm_default=82, swing_percent=22, drum_density=0.60, mastering_preset="lofi"),
    "house": StylePreset(style="house", bpm_default=124, swing_percent=0, drum_density=0.85, mastering_preset="demo"),
    "techno": StylePreset(style="techno", bpm_default=132, swing_percent=0, drum_density=0.90, mastering_preset="demo"),
    "ambient": StylePreset(style="ambient", bpm_default=90, swing_percent=0, drum_density=0.35, mastering_preset="clean", prefer_sampler_808=False),
    "unknown": StylePreset(style="unknown", bpm_default=110, swing_percent=8, drum_density=0.70, mastering_preset="clean"),
}


def preset_for(style: StyleName) -> StylePreset:
    return STYLE_PRESETS.get(style, STYLE_PRESETS["unknown"])
