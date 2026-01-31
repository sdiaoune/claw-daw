from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def default_config_dir() -> Path:
    return Path.home() / ".config" / "claw-daw"


def default_config_path() -> Path:
    return default_config_dir() / "config.json"


@dataclass
class AppConfig:
    soundfont_path: str | None = None
    audio_driver: str | None = None  # e.g. alsa, pulseaudio, coreaudio

    def to_dict(self) -> dict[str, Any]:
        return {
            "soundfont_path": self.soundfont_path,
            "audio_driver": self.audio_driver,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "AppConfig":
        return AppConfig(
            soundfont_path=d.get("soundfont_path") or None,
            audio_driver=d.get("audio_driver") or None,
        )


def load_config(path: Path | None = None) -> AppConfig:
    p = path or default_config_path()
    if not p.exists():
        return AppConfig()
    data = json.loads(p.read_text(encoding="utf-8"))
    return AppConfig.from_dict(data)


def save_config(cfg: AppConfig, path: Path | None = None) -> Path:
    p = path or default_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p
