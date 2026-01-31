from __future__ import annotations

from enum import Enum


class View(str, Enum):
    TRACKS = "tracks"
    ARRANGE = "arrange"
    HELP = "help"
