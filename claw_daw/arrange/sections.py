from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Section:
    name: str
    start: int  # ticks
    length: int  # ticks

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "start": self.start, "length": self.length}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Section":
        return Section(name=str(d["name"]), start=int(d["start"]), length=int(d["length"]))


@dataclass
class Variation:
    """A pattern swap scoped to a section.

    Example: in section "chorus", swap pattern A->A2 for track 0.
    """

    section: str
    track_index: int
    src_pattern: str
    dst_pattern: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "track_index": self.track_index,
            "src_pattern": self.src_pattern,
            "dst_pattern": self.dst_pattern,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Variation":
        return Variation(
            section=str(d["section"]),
            track_index=int(d["track_index"]),
            src_pattern=str(d["src_pattern"]),
            dst_pattern=str(d["dst_pattern"]),
        )
