from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_NAME = "KeyboardSound"
DEFAULT_VOLUME = 70
MAX_VOLUME = 400
DEFAULT_COOLDOWN_MS = 0
MAX_COOLDOWN_MS = 1000
SETTINGS_VERSION = 2


def resource_path(relative_path: str) -> Path:
    """Return a resource path that also works from a PyInstaller bundle."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return Path(__file__).resolve().parent / relative_path


def default_sound_file() -> str:
    return str(resource_path("assets/shotgun.wav"))


def _looks_like_default_sound(sound_file: str) -> bool:
    path = Path(sound_file)
    return path.name.lower() == "shotgun.wav" and path.parent.name.lower() == "assets"


def _normalize_sound_file(sound_file: str | None) -> str:
    if not isinstance(sound_file, str) or not sound_file.strip():
        return default_sound_file()

    if _looks_like_default_sound(sound_file) and not Path(sound_file).exists():
        return default_sound_file()

    return sound_file


def default_config_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME / "settings.json"
    return Path.home() / f".{APP_NAME}" / "settings.json"


def _coerce_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


@dataclass
class AppConfig:
    enabled: bool = True
    volume: int = DEFAULT_VOLUME
    sound_file: str | None = None
    cooldown_ms: int = DEFAULT_COOLDOWN_MS

    def __post_init__(self) -> None:
        self.sound_file = _normalize_sound_file(self.sound_file)
        self.volume = _coerce_int(self.volume, DEFAULT_VOLUME, 0, MAX_VOLUME)
        self.cooldown_ms = _coerce_int(
            self.cooldown_ms, DEFAULT_COOLDOWN_MS, 0, MAX_COOLDOWN_MS
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppConfig":
        if not isinstance(data, dict):
            return cls()

        cooldown_ms = data.get("cooldown_ms")
        # Replace the old typing throttle while preserving custom cooldowns.
        if data.get("settings_version") != SETTINGS_VERSION and cooldown_ms == 50:
            cooldown_ms = DEFAULT_COOLDOWN_MS

        return cls(
            enabled=_coerce_bool(data.get("enabled"), True),
            volume=_coerce_int(data.get("volume"), DEFAULT_VOLUME, 0, MAX_VOLUME),
            sound_file=_normalize_sound_file(data.get("sound_file")),
            cooldown_ms=_coerce_int(
                cooldown_ms, DEFAULT_COOLDOWN_MS, 0, MAX_COOLDOWN_MS
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings_version": SETTINGS_VERSION,
            "enabled": self.enabled,
            "volume": self.volume,
            "sound_file": self.sound_file,
            "cooldown_ms": self.cooldown_ms,
        }


class ConfigManager:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_config_path()

    def load(self) -> AppConfig:
        try:
            if not self.path.exists():
                return AppConfig()
            with self.path.open("r", encoding="utf-8") as config_file:
                data = json.load(config_file)
        except (OSError, json.JSONDecodeError):
            return AppConfig()

        return AppConfig.from_dict(data)

    def save(self, config: AppConfig) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(config.to_dict(), indent=2),
                encoding="utf-8",
            )
            temp_path.replace(self.path)
        except OSError:
            return False

        return True
