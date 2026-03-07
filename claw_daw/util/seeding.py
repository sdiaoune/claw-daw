from __future__ import annotations

import secrets


_AUTO_SEED_MAX = 2_147_483_647


def resolve_generation_seed(seed: int | None) -> int:
    """Resolve an optional generation seed to a concrete integer."""

    if seed is None:
        return secrets.randbelow(_AUTO_SEED_MAX) + 1
    return int(seed)
