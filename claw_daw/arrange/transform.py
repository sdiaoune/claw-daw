from __future__ import annotations

from dataclasses import replace

from claw_daw.arrange.types import Pattern
from claw_daw.model.types import Note


def transpose(pattern: Pattern, semitones: int) -> Pattern:
    notes: list[Note] = []
    for n in pattern.notes:
        notes.append(
            Note(start=n.start, duration=n.duration, pitch=max(0, min(127, n.pitch + semitones)), velocity=n.velocity)
        )
    return replace(pattern, notes=notes)


def shift(pattern: Pattern, ticks: int) -> Pattern:
    notes: list[Note] = []
    for n in pattern.notes:
        notes.append(
            Note(start=max(0, n.start + ticks), duration=n.duration, pitch=n.pitch, velocity=n.velocity)
        )
    return replace(pattern, notes=notes)


def stretch(pattern: Pattern, factor: float) -> Pattern:
    if factor <= 0:
        raise ValueError("factor must be > 0")
    notes: list[Note] = []
    for n in pattern.notes:
        notes.append(
            Note(
                start=int(round(n.start * factor)),
                duration=max(1, int(round(n.duration * factor))),
                pitch=n.pitch,
                velocity=n.velocity,
            )
        )
    length = max(1, int(round(pattern.length * factor)))
    return replace(pattern, length=length, notes=notes)


def reverse(pattern: Pattern) -> Pattern:
    notes: list[Note] = []
    for n in pattern.notes:
        new_start = max(0, pattern.length - (n.start + n.duration))
        notes.append(Note(start=new_start, duration=n.duration, pitch=n.pitch, velocity=n.velocity))
    notes.sort(key=lambda x: (x.start, x.pitch))
    return replace(pattern, notes=notes)


def velocity_scale(pattern: Pattern, scale: float) -> Pattern:
    if scale <= 0:
        raise ValueError("scale must be > 0")
    notes: list[Note] = []
    for n in pattern.notes:
        v = max(1, min(127, int(round(n.velocity * scale))))
        notes.append(Note(start=n.start, duration=n.duration, pitch=n.pitch, velocity=v))
    return replace(pattern, notes=notes)
