from __future__ import annotations

from dataclasses import dataclass

from claw_daw.model.types import Project


@dataclass(frozen=True)
class ReferenceIssue:
    code: str
    message: str
    track_index: int | None = None


def analyze_references(project: Project) -> list[ReferenceIssue]:
    """Safe reference analysis.

    Looks for missing pattern references and other cheap-but-useful footguns.
    """

    issues: list[ReferenceIssue] = []

    for ti, t in enumerate(project.tracks):
        # missing patterns referenced by clips
        for ci, c in enumerate(t.clips):
            if c.pattern not in t.patterns:
                issues.append(
                    ReferenceIssue(
                        code="missing_pattern",
                        message=f"Track {ti} clip[{ci}] references missing pattern: {c.pattern}",
                        track_index=ti,
                    )
                )

        # patterns unused (informational)
        used = {c.pattern for c in t.clips}
        unused = sorted(set(t.patterns.keys()) - used)
        if unused:
            issues.append(
                ReferenceIssue(
                    code="unused_patterns",
                    message=f"Track {ti} has unused patterns: {', '.join(unused[:8])}" + (" …" if len(unused) > 8 else ""),
                    track_index=ti,
                )
            )

    return issues
