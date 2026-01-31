from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claw_daw.model.types import Project
from claw_daw.util.validate import migrate_project_dict, validate_and_migrate_project


def load_project(path: str | Path) -> Project:
    p = Path(path)
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    data = migrate_project_dict(data)
    project = Project.from_dict(data)
    project = validate_and_migrate_project(project)
    project.path = str(p)
    project.dirty = False
    return project


def save_project(project: Project, path: str | Path | None = None) -> str:
    out_path = Path(path or project.path or f"{project.name}.json").expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = project.to_dict()
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    project.path = str(out_path)
    project.dirty = False
    return str(out_path)
