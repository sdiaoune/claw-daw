"""Prompt-driven music generation helpers.

This package is intentionally offline and deterministic.

Core pipeline:
- parse_prompt(prompt) -> Brief
- brief_to_script(brief, seed=...) -> headless script text
- similarity scoring utilities for novelty constraints
- optional closed-loop iteration via preview/analyze/auto-tune
"""

from .types import Brief, StyleName
from .parse import parse_prompt
from .script import brief_to_script
from .similarity import project_similarity
from .pipeline import generate_from_prompt

__all__ = [
    "Brief",
    "StyleName",
    "parse_prompt",
    "brief_to_script",
    "project_similarity",
    "generate_from_prompt",
]
