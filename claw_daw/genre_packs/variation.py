from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class VariationSpec:
    """Deterministic knobs that change musical structure.

    Keep these as coarse switches so different attempts are meaningfully different
    and similarity constraints have a chance to pass.
    """

    drum_variant: int
    bass_variant: int
    harmony_variant: int
    lead_variant: int


class VariationEngine:
    """Deterministically generate a VariationSpec from (seed, attempt)."""

    def __init__(self, seed: int):
        self.seed = int(seed)

    def spec(self, attempt: int) -> VariationSpec:
        # Derive a stable RNG state from seed+attempt.
        rnd = Random((self.seed + 1) * 1_000_003 + int(attempt) * 97)
        return VariationSpec(
            drum_variant=rnd.randrange(0, 4),
            bass_variant=rnd.randrange(0, 4),
            harmony_variant=rnd.randrange(0, 4),
            lead_variant=rnd.randrange(0, 4),
        )
