from __future__ import annotations

from dataclasses import dataclass
import re
from random import Random
from typing import Callable, Literal

from claw_daw.genre_packs.variation import VariationEngine
from claw_daw.model.types import Project
from claw_daw.prompt.palette import select_track_sound
from claw_daw.genre_packs.acceptance import (
    AcceptanceFailure,
    pattern_has_pitch_near_step,
    pattern_note_count,
    require,
    track_index_by_name,
)


PackName = Literal["trap", "house", "boom_bap"]


@dataclass(frozen=True)
class GenrePackV1:
    name: PackName
    title: str
    bpm_min: int
    bpm_max: int
    bpm_default: int
    swing_percent: int
    roles: list[str]
    mastering_preset: str

    # Build a script. Signature is (seed, attempt, out_prefix) -> str
    generator: Callable[[int, int, str | None], str]

    def accept(self, proj: Project) -> None:
        """Raise AcceptanceFailure if generated project violates pack rules."""

        errors: list[str] = []

        require(self.bpm_min <= int(proj.tempo_bpm) <= self.bpm_max, f"tempo_bpm out of range: {proj.tempo_bpm}", errors)
        require(int(proj.swing_percent) == int(self.swing_percent), "swing_percent mismatch", errors)

        # Must have the declared roles as track names (Title case in generator).
        for r in self.roles:
            require(track_index_by_name(proj, r.lower()) is not None, f"missing track: {r}", errors)

        # Genre-specific checks
        if self.name == "house":
            # House: kick on 4-on-the-floor in drum pattern "d".
            ti = track_index_by_name(proj, "drums")
            if ti is not None:
                # pattern is 2 bars => 32 16th steps
                # kick pitch is 36 in gen_drums
                for step_idx in (0, 4, 8, 12, 16, 20, 24, 28):
                    require(
                        pattern_has_pitch_near_step(proj, ti, "d", pitch=36, step_index=step_idx, step_count=32),
                        f"house kick missing at step {step_idx}",
                        errors,
                    )

        if self.name == "trap":
            # Trap: halftime clap/snare on beat 3 of each bar (steps 8 and 24 of a 2-bar pattern)
            ti = track_index_by_name(proj, "drums")
            if ti is not None:
                require(
                    pattern_has_pitch_near_step(proj, ti, "d", pitch=38, step_index=8, step_count=32, tol_steps=0),
                    "trap snare missing near beat 3 (bar 1)",
                    errors,
                )
                require(
                    pattern_has_pitch_near_step(proj, ti, "d", pitch=38, step_index=24, step_count=32, tol_steps=0),
                    "trap snare missing near beat 3 (bar 2)",
                    errors,
                )

        if self.name == "boom_bap":
            # Boom-bap: snare on 2 and 4 of each bar (steps 4, 12, 20, 28)
            ti = track_index_by_name(proj, "drums")
            if ti is not None:
                for step_idx in (4, 12, 20, 28):
                    require(
                        pattern_has_pitch_near_step(proj, ti, "d", pitch=38, step_index=step_idx, step_count=32),
                        f"boom-bap snare missing at step {step_idx}",
                        errors,
                    )

        # Must be non-empty music.
        for name in ("drums", "bass"):
            ti = track_index_by_name(proj, name)
            if ti is not None:
                require(pattern_note_count(proj, ti, "d" if name == "drums" else "b") > 0, f"{name} has 0 notes", errors)

        if errors:
            raise AcceptanceFailure(errors)


# ---------------------- pack generators ----------------------


def _safe_name(name: str) -> str:
    safe = (name or "untitled").replace("\n", " ").strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", safe).strip("_") or "untitled"
    return safe


def _scale_a_minor() -> list[int]:
    return [45, 47, 48, 50, 52, 53, 55]


def _gen_common(
    *,
    pack: GenrePackV1,
    seed: int,
    attempt: int,
    out_prefix: str | None,
) -> tuple[list[str], dict[str, int], Random, list[int]]:
    rnd = Random(int(seed) + int(attempt) * 10_007)
    scale = _scale_a_minor()

    name = _safe_name(out_prefix or pack.title)
    bpm = pack.bpm_default

    lines: list[str] = [f"new_project {name} {bpm}"]
    if pack.swing_percent:
        lines.append(f"set_swing {int(pack.swing_percent)}")

    roles = list(pack.roles)
    idx: dict[str, int] = {}
    for role in roles:
        ti = len(idx)
        idx[role] = ti
        sound = select_track_sound(role, style=pack.name, mood=None)
        program = sound.program if sound.program is not None else 0
        lines.append(f"add_track {role.title()} {program}")
        if sound.sampler:
            # use explicit helpers when available
            if sound.sampler == "drums":
                lines.append(f"set_kit {ti} {sound.sampler_preset or 'default'}")
            elif sound.sampler == "808":
                lines.append(f"set_808 {ti} {sound.sampler_preset or 'default'}")
            else:
                lines.append(f"set_sampler {ti} {sound.sampler}")
                if sound.sampler_preset:
                    lines.append(f"set_sampler_preset {ti} {sound.sampler_preset}")

        if role == "drums":
            lines.append(f"set_volume {ti} 112")
        if role == "bass":
            lines.append(f"set_volume {ti} 105")

    return lines, idx, rnd, scale


def _gen_house(seed: int, attempt: int, out_prefix: str | None) -> str:
    pack = get_pack_v1("house")
    lines, idx, rnd, scale = _gen_common(pack=pack, seed=seed, attempt=attempt, out_prefix=out_prefix)
    eng = VariationEngine(seed)
    spec = eng.spec(attempt)

    bars = 32

    # Drums
    ti = idx["drums"]
    lines.append(f"new_pattern {ti} d 2:0")
    lines.append(f"gen_drums {ti} d 2:0 house seed={seed + attempt} density={0.80 + 0.03 * spec.drum_variant}")
    lines.append(f"place_pattern {ti} d 0:0 {bars // 2}")

    # Bass (simple offbeat)
    ti = idx["bass"]
    lines.append(f"new_pattern {ti} b 2:0")
    root = scale[0]
    # Variant chooses offbeat emphasis
    offbeats = ["0:2", "1:2"] if spec.bass_variant % 2 == 0 else ["0:2", "0:3", "1:2", "1:3"]
    for st in offbeats:
        vel = 92 + rnd.randint(-6, 10)
        lines.append(f"add_note_pat {ti} b {root} {st} 0:0:240 {vel}")
    lines.append(f"place_pattern {ti} b 0:0 {bars // 2}")

    # Chords stab
    ti = idx["keys"]
    lines.append(f"new_pattern {ti} k 2:0")
    chord = [scale[0] + 24, scale[2] + 24, scale[4] + 24]
    stabs = ["0:2", "1:2"] if spec.harmony_variant < 2 else ["0:1", "0:2", "1:1", "1:2"]
    for beat in stabs:
        for p in chord:
            vel = 70 + rnd.randint(-8, 8)
            lines.append(f"add_note_pat {ti} k {p} {beat} 0:0:180 {vel}")
    lines.append(f"place_pattern {ti} k 0:0 {bars // 2}")

    if out_prefix:
        mp = pack.mastering_preset
        lines += [
            f"save_project out/{out_prefix}.json",
            f"export_midi out/{out_prefix}.mid",
            f"export_preview_mp3 out/{out_prefix}.preview.mp3 bars=8 start=0:0 preset={mp}",
            f"export_mp3 out/{out_prefix}.mp3 trim=60 preset={mp} fade=0.15",
        ]

    return "\n".join(lines) + "\n"


def _gen_trap(seed: int, attempt: int, out_prefix: str | None) -> str:
    pack = get_pack_v1("trap")
    lines, idx, rnd, scale = _gen_common(pack=pack, seed=seed, attempt=attempt, out_prefix=out_prefix)
    eng = VariationEngine(seed)
    spec = eng.spec(attempt)

    bars = 24

    # Drums
    ti = idx["drums"]
    lines.append(f"new_pattern {ti} d 2:0")
    lines.append(f"gen_drums {ti} d 2:0 trap seed={seed + attempt} density={0.75 + 0.05 * spec.drum_variant}")
    lines.append(f"place_pattern {ti} d 0:0 {bars // 2}")

    # 808 Bass
    ti = idx["bass"]
    lines.append(f"set_glide {ti} 0:0:90")
    lines.append(f"new_pattern {ti} b 2:0")
    root = scale[0]
    fifth = scale[4]
    octave = root + 12

    if spec.bass_variant == 0:
        hits = [("0:0", root), ("0:3", root), ("1:0", fifth), ("1:2", octave)]
    elif spec.bass_variant == 1:
        hits = [("0:0", root), ("0:2", fifth), ("1:1", root), ("1:3", octave)]
    elif spec.bass_variant == 2:
        hits = [("0:0", root), ("0:2:120", octave), ("1:0", root), ("1:2", fifth)]
    else:
        hits = [("0:0", root), ("0:1:120", fifth), ("1:0", octave), ("1:2:120", root)]

    for st, pitch in hits:
        vel = 100 + rnd.randint(-8, 12)
        # a bit longer notes for trap subs
        lines.append(f"add_note_pat {ti} b {pitch} {st} 0:1 {vel}")

    lines.append(f"place_pattern {ti} b 0:0 {bars // 2}")

    # Dark keys
    ti = idx["keys"]
    lines.append(f"new_pattern {ti} k 4:0")
    chord1 = [scale[0] + 12, scale[2] + 12, scale[5] + 12]
    chord2 = [scale[3] + 12, scale[5] + 12, scale[0] + 24]
    chords = chord1 if spec.harmony_variant < 2 else chord2
    for p in chords:
        vel = 60 + rnd.randint(-5, 6)
        lines.append(f"add_note_pat {ti} k {p} 0:0 4:0 {vel} chance=0.9")
    lines.append(f"place_pattern {ti} k 0:0 {max(1, bars // 4)}")

    # Sparse lead
    ti = idx["lead"]
    lines.append(f"new_pattern {ti} l 2:0")
    density = 0.35 + 0.12 * (spec.lead_variant % 3)
    starts = ["0:2", "0:2:120", "1:2", "1:2:120"]
    for st in starts:
        if rnd.random() < density:
            pitch = rnd.choice(scale) + 24
            vel = 72 + rnd.randint(-10, 10)
            lines.append(f"add_note_pat {ti} l {pitch} {st} 0:0:120 {vel} chance=0.7")
    lines.append(f"place_pattern {ti} l 0:0 {bars // 2}")

    if out_prefix:
        mp = pack.mastering_preset
        lines += [
            f"save_project out/{out_prefix}.json",
            f"export_midi out/{out_prefix}.mid",
            f"export_preview_mp3 out/{out_prefix}.preview.mp3 bars=8 start=0:0 preset={mp}",
            f"export_mp3 out/{out_prefix}.mp3 trim=60 preset={mp} fade=0.15",
        ]

    return "\n".join(lines) + "\n"


def _gen_boom_bap(seed: int, attempt: int, out_prefix: str | None) -> str:
    pack = get_pack_v1("boom_bap")
    lines, idx, rnd, scale = _gen_common(pack=pack, seed=seed, attempt=attempt, out_prefix=out_prefix)
    eng = VariationEngine(seed)
    spec = eng.spec(attempt)

    bars = 24

    # Drums
    ti = idx["drums"]
    lines.append(f"new_pattern {ti} d 2:0")
    lines.append(f"gen_drums {ti} d 2:0 boom_bap seed={seed + attempt} density={0.70 + 0.05 * spec.drum_variant}")
    # add humanize on drums for groove
    lines.append(f"set_humanize {ti} timing=12 velocity=8 seed={seed + attempt}")
    lines.append(f"place_pattern {ti} d 0:0 {bars // 2}")

    # Bass
    ti = idx["bass"]
    lines.append(f"new_pattern {ti} b 2:0")
    root = scale[0]
    third = scale[2]
    fifth = scale[4]
    if spec.bass_variant < 2:
        hits = [("0:0", root), ("0:2", root), ("1:0", fifth), ("1:2", third)]
    else:
        hits = [("0:0", root), ("0:3", fifth), ("1:0", root), ("1:3", third)]

    for st, pitch in hits:
        vel = 88 + rnd.randint(-10, 10)
        lines.append(f"add_note_pat {ti} b {pitch} {st} 0:0:240 {vel}")
    lines.append(f"place_pattern {ti} b 0:0 {bars // 2}")

    # Sample-ish keys loop
    ti = idx["keys"]
    lines.append(f"new_pattern {ti} k 2:0")
    chord = [scale[0] + 12, scale[3] + 12, scale[5] + 12]
    if spec.harmony_variant % 2 == 0:
        beats = ["0:0", "1:0"]
        dur = "0:1"
    else:
        beats = ["0:0", "0:2", "1:0", "1:2"]
        dur = "0:0:180"
    for beat in beats:
        for p in chord:
            vel = 66 + rnd.randint(-8, 8)
            lines.append(f"add_note_pat {ti} k {p} {beat} {dur} {vel} chance=0.95")
    lines.append(f"place_pattern {ti} k 0:0 {bars // 2}")

    # Optional pad is omitted to stay boom-bap-ish.

    if out_prefix:
        mp = pack.mastering_preset
        lines += [
            f"save_project out/{out_prefix}.json",
            f"export_midi out/{out_prefix}.mid",
            f"export_preview_mp3 out/{out_prefix}.preview.mp3 bars=8 start=0:0 preset={mp}",
            f"export_mp3 out/{out_prefix}.mp3 trim=60 preset={mp} fade=0.15",
        ]

    return "\n".join(lines) + "\n"


_PACKS: dict[PackName, GenrePackV1] | None = None


def _init() -> dict[PackName, GenrePackV1]:
    return {
        "trap": GenrePackV1(
            name="trap",
            title="Trap Pack v1",
            bpm_min=120,
            bpm_max=170,
            bpm_default=140,
            swing_percent=0,
            roles=["drums", "bass", "keys", "lead"],
            mastering_preset="clean",
            generator=_gen_trap,
        ),
        "house": GenrePackV1(
            name="house",
            title="House Pack v1",
            bpm_min=118,
            bpm_max=132,
            bpm_default=124,
            swing_percent=0,
            roles=["drums", "bass", "keys"],
            mastering_preset="demo",
            generator=_gen_house,
        ),
        "boom_bap": GenrePackV1(
            name="boom_bap",
            title="Boom-Bap Pack v1",
            bpm_min=78,
            bpm_max=98,
            bpm_default=90,
            swing_percent=18,
            roles=["drums", "bass", "keys"],
            mastering_preset="lofi",
            generator=_gen_boom_bap,
        ),
    }


def list_packs_v1() -> list[str]:
    global _PACKS
    if _PACKS is None:
        _PACKS = _init()
    return sorted(_PACKS.keys())


def get_pack_v1(name: str) -> GenrePackV1:
    global _PACKS
    if _PACKS is None:
        _PACKS = _init()
    key = str(name).strip().lower().replace("-", "_")
    if key not in _PACKS:
        raise KeyError(f"unknown genre pack: {name}. Available: {', '.join(list_packs_v1())}")
    return _PACKS[key]  # type: ignore[index]
