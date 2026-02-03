from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "claw-daw"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "claw-daw"
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "claw-daw"


def default_soundfont_paths() -> list[str]:
    paths: list[str] = []

    env_sf = os.environ.get("CLAW_DAW_SOUNDFONT")
    if env_sf:
        paths.append(env_sf)

    data_sf = app_data_dir() / "soundfonts" / "FluidR3_GM.sf2"
    paths.append(str(data_sf))

    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        paths.extend(
            [
                str(Path(local_app) / "Sounds" / "Banks" / "default.sf2"),
                r"C:\Program Files\Common Files\Sounds\Banks\default.sf2",
            ]
        )
        return paths

    if sys.platform == "darwin":
        paths.extend(
            [
                str(Path.home() / "Library" / "Audio" / "Sounds" / "Banks" / "default.sf2"),
                "/Library/Audio/Sounds/Banks/default.sf2",
            ]
        )
        return paths

    # Linux / other Unix
    paths.extend(
        [
            "/usr/share/sounds/sf2/default-GM.sf2",
            "/usr/share/sounds/sf2/FluidR3_GM.sf2",
            "/usr/share/sounds/sf2/GeneralUser-GS-v1.471.sf2",
            "/usr/share/sounds/sf2/GeneralUser-GS.sf2",
            "/usr/share/soundfonts/FluidR3_GM.sf2",
            "/usr/share/soundfonts/default.sf2",
        ]
    )
    return paths


def find_default_soundfont() -> str | None:
    for p in default_soundfont_paths():
        if Path(p).expanduser().exists():
            return str(Path(p).expanduser())
    return None
