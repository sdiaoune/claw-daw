from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GridCursor:
    step: int = 0  # horizontal position in steps
    pitch: int = 42  # MIDI pitch


@dataclass
class GridConfig:
    steps_per_beat: int = 4  # 16ths
    beats_per_bar: int = 4
    bars: int = 4

    @property
    def total_steps(self) -> int:
        return self.bars * self.beats_per_bar * self.steps_per_beat
