from __future__ import annotations

from claw_daw.arrange.sections import Section, Variation


def _section_at_tick(sections: list[Section], tick: int) -> str | None:
    for s in sections:
        if s.start <= tick < s.start + s.length:
            return s.name
    return None


def resolve_pattern_name(
    *,
    base_pattern: str,
    track_index: int,
    tick: int,
    sections: list[Section],
    variations: list[Variation],
) -> str:
    sec = _section_at_tick(sections, tick)
    if not sec:
        return base_pattern

    for v in variations:
        if v.section == sec and v.track_index == track_index and v.src_pattern == base_pattern:
            return v.dst_pattern
    return base_pattern
