"""Genre Packs v1.

A Genre Pack is a deterministic, structured generator for a style/genre.
It defines:
- roles/tracks
- generator archetypes + rules
- acceptance tests (project-level constraints)

The goal is to generate from scratch (no templates) while remaining deterministic
(seed + attempt index => same output).
"""

from .v1 import GenrePackV1, get_pack_v1, list_packs_v1
from .pipeline import generate_from_genre_pack

__all__ = [
    "GenrePackV1",
    "get_pack_v1",
    "list_packs_v1",
    "generate_from_genre_pack",
]
