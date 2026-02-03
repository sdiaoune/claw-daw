"""Deterministic drum macros: variations + fills.

Goal: given a base drum pattern, generate:
- multi-bar loop variations (4-bar and/or 8-bar)
- 1-bar fill patterns (hat roll endings, kick turnarounds)

These are intentionally *simple* and deterministic so they can be used in
headless scripts and compiler passes.
"""

from __future__ import annotations


from dataclasses import replace
from random import Random

from claw_daw.arrange.types import Pattern
from claw_daw.model.types import Note, Track


# --- helpers ---


def ticks_per_bar(ppq: int) -> int:
    # 4/4 assumption (consistent with the rest of the project)
    return int(ppq) * 4


def _is_pitch(n: Note, pitches: set[int]) -> bool:
    return int(n.pitch) in pitches


def _copy_notes_with_offset(notes: list[Note], *, offset: int, length: int) -> list[Note]:
    out: list[Note] = []
    for n in notes:
        if 0 <= n.start < length:
            out.append(replace(n, start=int(n.start) + int(offset)))
    return out


def _dedupe(notes: list[Note]) -> list[Note]:
    # dedupe exact start/pitch (keep the loudest)
    best: dict[tuple[int, int], Note] = {}
    for n in notes:
        k = (int(n.start), int(n.pitch))
        cur = best.get(k)
        if cur is None or int(cur.velocity) < int(n.velocity):
            best[k] = n
        else:
            # keep existing
            pass
    return sorted(best.values(), key=lambda x: (x.start, x.pitch, -x.velocity))


def _ensure_pattern(track: Track, name: str, length: int, *, max_patterns: int) -> Pattern:
    if name not in track.patterns:
        if len(track.patterns) >= max_patterns:
            raise RuntimeError(f"max patterns reached ({max_patterns})")
        track.patterns[name] = Pattern(name=name, length=length)
    p = track.patterns[name]
    p.name = name
    p.length = int(length)
    return p


# --- fills ---


def make_fill_hat_roll(
    base_bar: Pattern,
    *,
    ppq: int,
    seed: int,
    hat_pitch: int = 42,
) -> Pattern:
    """1-bar fill: add a 32nd hat roll at the end of the bar."""

    tpbar = ticks_per_bar(ppq)
    step16 = ppq // 4
    step32 = step16 // 2

    # start from base bar material
    notes = [replace(n) for n in base_bar.notes if 0 <= n.start < tpbar]

    rnd = Random(int(seed) + 801)

    # roll across the last beat (beat 4): 8 * 32nd notes
    roll_start = tpbar - ppq  # start of beat 4
    # optionally tighten: start slightly later sometimes
    if rnd.random() < 0.5:
        roll_start = tpbar - (ppq * 3) // 4  # 4-and

    vel0 = 52 + int(rnd.random() * 8)
    for i in range(8):
        t = roll_start + i * step32
        if t >= tpbar:
            break
        vel = max(1, min(127, vel0 + i * 6))
        notes.append(Note(start=int(t), duration=max(1, step32 // 2), pitch=int(hat_pitch), velocity=int(vel)))

    p = Pattern(name=f"{base_bar.name}_fill_hatroll", length=tpbar)
    p.notes = _dedupe(notes)
    return p


def make_fill_kick_turnaround(
    base_bar: Pattern,
    *,
    ppq: int,
    seed: int,
    kick_pitch: int = 36,
) -> Pattern:
    """1-bar fill: a small kick turnaround in the last beat."""

    tpbar = ticks_per_bar(ppq)
    step16 = ppq // 4

    notes = [replace(n) for n in base_bar.notes if 0 <= n.start < tpbar]
    rnd = Random(int(seed) + 901)

    # add 2-3 kicks in beat 4 (syncopated)
    b4 = tpbar - ppq
    candidates = [b4 + step16 * 0, b4 + step16 * 2, b4 + step16 * 3]
    # sometimes omit the downbeat kick to make it feel like a "turn"
    if rnd.random() < 0.35:
        candidates = candidates[1:]

    base_vel = 105 + int(rnd.random() * 10)
    for j, t in enumerate(candidates):
        if t >= tpbar:
            continue
        vel = max(1, min(127, base_vel - j * 6))
        notes.append(Note(start=int(t), duration=int(step16), pitch=int(kick_pitch), velocity=int(vel)))

    p = Pattern(name=f"{base_bar.name}_fill_kickturn", length=tpbar)
    p.notes = _dedupe(notes)
    return p


# --- variations ---


def make_variation_loop(
    base: Pattern,
    *,
    ppq: int,
    bars: int,
    seed: int,
    kick_pitch: int = 36,
    snare_pitch: int = 38,
    hat_pitch: int = 42,
    fill: Pattern | None = None,
) -> Pattern:
    """Create a multi-bar loop by repeating base and applying light variations.

    Variations are subtle by design:
    - hat velocity sway + occasional extra hat on last 8th
    - small kick pickup in bar before fill
    - optional fill overlaid on final bar
    """

    tpbar = ticks_per_bar(ppq)
    out_len = int(bars) * tpbar

    # Decide which chunk of the base is the "bar" source.
    # If the base is longer than a bar, we sample from its first bar.
    base_bar = Pattern(name=f"{base.name}_bar", length=tpbar)
    base_bar.notes = [replace(n) for n in base.notes if 0 <= n.start < tpbar]

    notes: list[Note] = []

    step16 = ppq // 4

    for bi in range(int(bars)):
        bar_offset = bi * tpbar

        # copy base bar
        notes.extend(_copy_notes_with_offset(base_bar.notes, offset=bar_offset, length=tpbar))

        rnd = Random(int(seed) + 10007 + bi * 97 + bars * 991)

        # Hat "sway": deterministic velocity nudges for hats in this bar.
        # Keep snares stable, keep kicks mostly stable.
        vel_delta = int(round((rnd.random() - 0.5) * 10))
        if vel_delta:
            patched: list[Note] = []
            for n in notes:
                if bar_offset <= n.start < bar_offset + tpbar and _is_pitch(n, {hat_pitch}):
                    v = max(1, min(127, int(n.velocity) + vel_delta))
                    patched.append(replace(n, velocity=v))
                else:
                    patched.append(n)
            notes = patched

        # Occasional extra hat near end of bar.
        if rnd.random() < 0.40:
            t = bar_offset + tpbar - step16 * 2  # 4-and (8th before end)
            notes.append(Note(start=int(t), duration=max(1, step16 // 2), pitch=int(hat_pitch), velocity=58))

        # Small kick pickup in the bar before the last bar.
        if bi == bars - 2 and rnd.random() < 0.90:
            t = bar_offset + tpbar - step16  # last 16th
            notes.append(Note(start=int(t), duration=int(step16), pitch=int(kick_pitch), velocity=106))

        # Slightly reduce hat density on bar 2 in a 4-bar loop (common "breath" bar).
        if bars == 4 and bi == 1:
            patched2: list[Note] = []
            for n in notes:
                if bar_offset <= n.start < bar_offset + tpbar and _is_pitch(n, {hat_pitch}) and (n.start - bar_offset) % step16 == 0:
                    # deterministically drop every other 16th hat
                    if ((n.start - bar_offset) // step16) % 2 == 1:
                        continue
                patched2.append(n)
            notes = patched2

    # Overlay fill on final bar.
    if fill is not None:
        final_offset = (bars - 1) * tpbar
        notes.extend(_copy_notes_with_offset(fill.notes, offset=final_offset, length=tpbar))

        # Ensure we don't stack snare doubles right at the barline.
        patched3: list[Note] = []
        for n in notes:
            if final_offset <= n.start < final_offset + tpbar and _is_pitch(n, {snare_pitch}):
                patched3.append(n)
            else:
                patched3.append(n)
        notes = patched3

    p = Pattern(name=f"{base.name}_v{bars}", length=out_len)
    p.notes = _dedupe(notes)
    return p


def generate_drum_macro_pack(
    track: Track,
    *,
    base_pattern: str,
    ppq: int,
    seed: int = 0,
    out_prefix: str | None = None,
    make_4: bool = True,
    make_8: bool = True,
    max_patterns: int = 256,
) -> dict[str, str]:
    """Generate fill + variation patterns into `track.patterns`.

    Returns a dict mapping logical names -> created pattern names.
    """

    if base_pattern not in track.patterns:
        raise KeyError(f"track has no pattern named: {base_pattern}")

    base = track.patterns[base_pattern]
    tpbar = ticks_per_bar(ppq)

    # Create a 1-bar "source" from the base.
    base_bar = Pattern(name=(out_prefix or base_pattern), length=tpbar)
    base_bar.notes = [replace(n) for n in base.notes if 0 <= n.start < tpbar]

    prefix = str(out_prefix or base_pattern)

    # Fill patterns
    hat_fill = make_fill_hat_roll(base_bar, ppq=ppq, seed=seed)
    hat_fill = replace(hat_fill, name=f"{prefix}_fill_hatroll")
    kick_fill = make_fill_kick_turnaround(base_bar, ppq=ppq, seed=seed)
    kick_fill = replace(kick_fill, name=f"{prefix}_fill_kickturn")

    p_hat = _ensure_pattern(track, hat_fill.name, hat_fill.length, max_patterns=max_patterns)
    p_hat.notes = hat_fill.notes

    p_kick = _ensure_pattern(track, kick_fill.name, kick_fill.length, max_patterns=max_patterns)
    p_kick.notes = kick_fill.notes

    created: dict[str, str] = {
        "fill_hatroll": hat_fill.name,
        "fill_kickturn": kick_fill.name,
    }

    # Variations
    if make_4:
        v4 = make_variation_loop(base, ppq=ppq, bars=4, seed=seed, fill=hat_fill)
        v4 = replace(v4, name=f"{prefix}_v4")
        p_v4 = _ensure_pattern(track, v4.name, v4.length, max_patterns=max_patterns)
        p_v4.notes = v4.notes
        created["v4"] = v4.name

    if make_8:
        # 8-bar: combine kick turnaround + hat roll by overlaying both fills
        # (simple approach: merge fills into one fill bar)
        merged_fill = Pattern(name=f"{prefix}_fill_merged", length=tpbar)
        merged_fill.notes = _dedupe([*kick_fill.notes, *hat_fill.notes])
        v8 = make_variation_loop(base, ppq=ppq, bars=8, seed=seed + 17, fill=merged_fill)
        v8 = replace(v8, name=f"{prefix}_v8")
        p_v8 = _ensure_pattern(track, v8.name, v8.length, max_patterns=max_patterns)
        p_v8.notes = v8.notes
        created["v8"] = v8.name

    return created
