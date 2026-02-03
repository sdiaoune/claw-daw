from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator


def read_text_resource(rel_path: str) -> str:
    """Read a text resource from cwd if present, else from package data."""
    p = Path(rel_path)
    if p.exists():
        return p.read_text(encoding="utf-8")

    data_root = resources.files("claw_daw.data")
    return data_root.joinpath(rel_path).read_text(encoding="utf-8")


@contextmanager
def resource_path(rel_path: str) -> Iterator[Path]:
    """Yield a filesystem Path for a resource directory or file."""
    p = Path(rel_path)
    if p.exists():
        yield p
        return

    data_root = resources.files("claw_daw.data").joinpath(rel_path)
    with resources.as_file(data_root) as rp:
        yield rp
