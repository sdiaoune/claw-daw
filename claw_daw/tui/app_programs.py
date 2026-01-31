from __future__ import annotations

from claw_daw.util.gm import GM_PROGRAMS


def format_program_list(max_items: int = 30) -> str:
    items = sorted(GM_PROGRAMS.items(), key=lambda kv: (kv[1], kv[0]))
    lines = ["GM programs (0-based):"]
    for name, program in items[:max_items]:
        lines.append(f"  {program:3d}  {name}")
    if len(items) > max_items:
        lines.append(f"  ... ({len(items) - max_items} more; see README / GM_PROGRAMS)")
    return "\n".join(lines)
