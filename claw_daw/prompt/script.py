from __future__ import annotations

from dataclasses import dataclass
from random import Random
import re

from claw_daw.prompt.palette import select_track_preset
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

        preset_role = select_track_preset(role, style=brief.style, mood=brief.mood)
        sound = preset_role.sound
        mix = preset_role.mix

        # add_track <name> [program]
        program = sound.program if sound.program is not None else 0
        lines.append(f"add_track {role.title()} {program}")

        if sound.sampler:
            lines.append(f"set_sampler {ti} {sound.sampler}")
            if sound.sampler_preset:
                lines.append(f"set_sampler_preset {ti} {sound.sampler_preset}")

        # Mixer defaults (style palette), caller can override volume via volumes={...}
        if mix.volume is not None:
            lines.append(f"set_volume {ti} {int(volumes.get(role, mix.volume))}")
        elif role in volumes:
            lines.append(f"set_volume {ti} {int(volumes[role])}")

        if mix.pan is not None:
            lines.append(f"set_pan {ti} {int(mix.pan)}")
        if mix.reverb is not None:
            lines.append(f"set_reverb {ti} {int(mix.reverb)}")
        if mix.chorus is not None:
            lines.append(f"set_chorus {ti} {int(mix.chorus)}")

    # Drums
    if "drums" in track_indices:
        ti = track_indices["drums"]
        lines.append(f"new_pattern {ti} d 2:0")
        style = (brief.style if brief.style != "unknown" else "hiphop")
        lines.append(f"gen_drums {ti} d 2:0 {style} seed={seed} density={preset.drum_density}")
        lines.append(f"place_pattern {ti} d 0:0 {bars // 2}")

    # A tiny chord progression (roots only), used by keys + bass follower.
    # (These are scale degrees around A-minor-ish; deterministic & loopable.)
    chord_roots = [scale[0], scale[5], scale[3], scale[4]]

    # Bass (follows chord roots, adds cadences/turnarounds + occasional gaps/glides)
    if "bass" in track_indices:
        ti = track_indices["bass"]
        lines.append(f"new_pattern {ti} b 4:0")
        # For 808-ish lines, enable a little portamento; harmless for GM bass too.
        lines.append(f"set_glide {ti} 0:0:90")
        roots_csv = ",".join(str(int(r)) for r in chord_roots)
        lines.append(
            f"gen_bass_follow {ti} b 4:0 roots={roots_csv} seed={seed} "
            f"gap_prob={0.14:.2f} glide_prob={0.28:.2f} cadence_bars=4 turnaround=1"
        )
        lines.append(f"place_pattern {ti} b 0:0 {max(1, bars // 4)}")

    # Keys (simple stabs that follow the same chord roots)
    if "keys" in track_indices:
        ti = track_indices["keys"]
        lines.append(f"new_pattern {ti} k 4:0")
        # Build minor-ish triads off each root (naive but musical enough).
        stabs = ["0:0", "0:2", "1:0", "1:2", "2:0", "2:2", "3:0", "3:2"]
        for bar_i, root in enumerate(chord_roots):
            chord = [root + 12, root + 15, root + 19]  # root, m3, 5
            # 2 stabs per bar
            for beat in stabs[bar_i * 2 : bar_i * 2 + 2]:
                for p in chord:
                    vel = 68 + rnd.randint(-7, 7)
                    lines.append(f"add_note_pat {ti} k {p} {beat} 0:1 {vel} chance=0.88")
        lines.append(f"place_pattern {ti} k 0:0 {max(1, bars // 4)}")

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
