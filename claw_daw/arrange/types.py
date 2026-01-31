from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# NOTE: avoid importing Note here to prevent circular imports. Import lazily inside methods.


@dataclass
class Pattern:
    name: str
    length: int  # ticks
    notes: list["Note"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError("pattern length must be > 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "length": self.length,
            "notes": [n.to_dict() for n in sorted(self.notes)],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Pattern":
        # lazy import to avoid circular import
        from claw_daw.model.types import Note

        p = Pattern(name=str(d["name"]), length=int(d["length"]))
        p.notes = [Note.from_dict(x) for x in d.get("notes", [])]
        return p


@dataclass
class Clip:
    pattern: str
    start: int
    repeats: int = 1

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("clip start must be >= 0")
        if self.repeats <= 0:
            raise ValueError("repeats must be > 0")

    def to_dict(self) -> dict[str, Any]:
        return {"pattern": self.pattern, "start": self.start, "repeats": self.repeats}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Clip":
        return Clip(pattern=str(d["pattern"]), start=int(d["start"]), repeats=int(d.get("repeats", 1)))
