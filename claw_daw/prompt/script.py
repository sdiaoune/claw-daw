from __future__ import annotations

from dataclasses import dataclass
from random import Random
import re

from claw_daw.prompt.palette import select_track_sound
from claw_daw.prompt.style import preset_for
from claw_daw.prompt.types import Brief


@dataclass(frozen=True)
class GeneratedScript:
    script: str
    mastering_preset: str


def _scale_pitches(key: str | None) -> list[int]:
    # A-minor-ish defaults.
    # We'll build in MIDI note numbers around A2/A3.
    # (This is intentionally naive; the goal is stable and pleasant-ish.)
    _ = key
    return [45, 47, 48, 50, 52, 53, 55]  # A2 B2 C3 D3 E3 F3 G3


def brief_to_script(
    brief: Brief,
    *,
    seed: int = 0,
    out_prefix: str | None = None,
    mastering_preset: str | None = None,
    volumes: dict[str, int] | None = None,
) -> GeneratedScript:
    preset = preset_for(brief.style)
    bpm = int(brief.bpm or preset.bpm_default)
    swing = int(preset.swing_percent)
    mpreset = mastering_preset or preset.mastering_preset

    # Arrange length: we place 1-2 bar patterns across the length.
    bars = max(4, int(brief.length_bars))

    rnd = Random(int(seed))
    scale = _scale_pitches(brief.key)

    lines: list[str] = []
    proj_name = out_prefix or brief.title
    safe_name = (proj_name or "untitled").replace("\n", " ").strip()
    # Must be a single token in headless scripts.
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name).strip("_") or "untitled"

    lines.append(f"new_project {safe_name} {bpm}")
    if swing:
        lines.append(f"set_swing {swing}")

    # Tracks (role order matters for later auto-tune heuristics).
    roles = [r for r in brief.roles if r]

    track_indices: dict[str, int] = {}
    volumes = volumes or {}

    for role in roles:
        ti = len(track_indices)
        track_indices[role] = ti

        # Choose sound.
        sound = select_track_sound(role, style=brief.style, mood=brief.mood)

        # add_track <name> [program]
        program = sound.program if sound.program is not None else 0
        lines.append(f"add_track {role.title()} {program}")

        if sound.sampler:
            lines.append(f"set_sampler {ti} {sound.sampler}")
            if sound.sampler_preset:
                lines.append(f"set_sampler_preset {ti} {sound.sampler_preset}")

        # small defaults (caller can override)
        if role == "bass":
            lines.append(f"set_volume {ti} {int(volumes.get(role, 105))}")
        elif role == "drums":
            lines.append(f"set_volume {ti} {int(volumes.get(role, 112))}")
        else:
            if role in volumes:
                lines.append(f"set_volume {ti} {int(volumes[role])}")

        if role in {"pad", "keys"}:
            lines.append(f"set_reverb {ti} 35")

    # Drums
    if "drums" in track_indices:
        ti = track_indices["drums"]
        lines.append(f"new_pattern {ti} d 2:0")
        style = (brief.style if brief.style != "unknown" else "hiphop")
        lines.append(f"gen_drums {ti} d 2:0 {style} seed={seed} density={preset.drum_density}")
        lines.append(f"place_pattern {ti} d 0:0 {bars // 2}")

    # Bass
    if "bass" in track_indices:
        ti = track_indices["bass"]
        lines.append(f"new_pattern {ti} b 2:0")
        # A simple 2-bar groove.
        root = scale[0]
        fifth = scale[4]
        octave = root + 12
        # Seed-controlled groove variation: choose between a couple of stable patterns.
        if rnd.random() < 0.5:
            hits = [("0:0", root), ("0:2", fifth), ("1:0", octave), ("1:2", fifth)]
        else:
            hits = [("0:0", root), ("0:3", fifth), ("1:0", root), ("1:2", octave)]

        for st, pitch in hits:
            vel = 92 + rnd.randint(-8, 10)
            lines.append(f"add_note_pat {ti} b {pitch} {st} 0:0:240 {vel}")
        lines.append(f"place_pattern {ti} b 0:0 {bars // 2}")

    # Keys
    if "keys" in track_indices:
        ti = track_indices["keys"]
        lines.append(f"new_pattern {ti} k 2:0")
        chord = [scale[0] + 12, scale[2] + 12, scale[4] + 12]  # triad-ish
        for beat in ["0:0", "0:2", "1:0", "1:2"]:
            for p in chord:
                vel = 70 + rnd.randint(-6, 6)
                lines.append(f"add_note_pat {ti} k {p} {beat} 0:1 {vel} chance=0.85")
        lines.append(f"place_pattern {ti} k 0:0 {bars // 2}")

    # Pad
    if "pad" in track_indices:
        ti = track_indices["pad"]
        lines.append(f"new_pattern {ti} p 4:0")
        pad_chord = [scale[0] + 12, scale[3] + 12, scale[5] + 12]
        for pch in pad_chord:
            vel = 55 + rnd.randint(-4, 4)
            lines.append(f"add_note_pat {ti} p {pch} 0:0 4:0 {vel}")
        lines.append(f"place_pattern {ti} p 0:0 {max(1, bars // 4)}")

    # Lead (optional, sparse)
    if "lead" in track_indices:
        ti = track_indices["lead"]
        lines.append(f"new_pattern {ti} l 2:0")
        # a small motif at the end of bar 2
        motif_steps = [rnd.choice(scale) + 12 for _ in range(4)]
        starts = ["1:2", "1:2:120", "1:3", "1:3:120"]
        for st, pitch in zip(starts, motif_steps, strict=False):
            vel = 76 + rnd.randint(-10, 12)
            lines.append(f"add_note_pat {ti} l {pitch} {st} 0:0:120 {vel} chance=0.55")
        lines.append(f"place_pattern {ti} l 0:0 {bars // 2}")

    # Exports
    if out_prefix:
        lines.append(f"save_project out/{out_prefix}.json")
        lines.append(f"export_midi out/{out_prefix}.mid")
        # Caller can decide whether to render full mp3. Script always includes a "preview" hook.
        lines.append(f"export_preview_mp3 out/{out_prefix}.preview.mp3 bars=8 start=0:0 preset={mpreset}")
        lines.append(f"export_mp3 out/{out_prefix}.mp3 trim=60 preset={mpreset} fade=0.15")

    return GeneratedScript(script="\n".join(lines) + "\n", mastering_preset=mpreset)
