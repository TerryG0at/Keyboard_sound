from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config_manager import AppConfig, ConfigManager, DEFAULT_COOLDOWN_MS, DEFAULT_VOLUME


class ConfigManagerTests(unittest.TestCase):
    def test_missing_config_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConfigManager(Path(temp_dir) / "settings.json")

            config = manager.load()

            self.assertTrue(config.enabled)
            self.assertEqual(config.volume, DEFAULT_VOLUME)
            self.assertEqual(config.cooldown_ms, DEFAULT_COOLDOWN_MS)
            self.assertTrue(
                config.sound_file.endswith("assets\\shotgun.wav")
                or config.sound_file.endswith("assets/shotgun.wav")
            )

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            manager = ConfigManager(path)
            config = AppConfig(
                enabled=False,
                volume=25,
                sound_file="C:/sounds/click.wav",
                cooldown_ms=80,
            )

            self.assertTrue(manager.save(config))
            loaded = manager.load()

            self.assertFalse(loaded.enabled)
            self.assertEqual(loaded.volume, 25)
            self.assertEqual(loaded.sound_file, "C:/sounds/click.wav")
            self.assertEqual(loaded.cooldown_ms, 80)

    def test_invalid_json_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("{invalid json", encoding="utf-8")
            manager = ConfigManager(path)

            config = manager.load()

            self.assertTrue(config.enabled)
            self.assertEqual(config.volume, DEFAULT_VOLUME)

    def test_invalid_values_are_sanitized(self) -> None:
        config = AppConfig.from_dict(
            {
                "enabled": "yes",
                "volume": 999,
                "sound_file": "",
                "cooldown_ms": -10,
            }
        )

        self.assertTrue(config.enabled)
        self.assertEqual(config.volume, 400)
        self.assertEqual(config.cooldown_ms, 0)

    def test_boosted_volume_survives_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConfigManager(Path(temp_dir) / "settings.json")
            self.assertTrue(manager.save(AppConfig(volume=300)))
            self.assertEqual(manager.load().volume, 300)

    def test_legacy_default_cooldown_is_migrated(self) -> None:
        config = AppConfig.from_dict({"cooldown_ms": 50, "volume": 80})
        self.assertEqual(config.cooldown_ms, 0)
        self.assertEqual(config.volume, 80)
        self.assertEqual(AppConfig.from_dict({"cooldown_ms": 80}).cooldown_ms, 80)

    def test_current_custom_cooldown_is_preserved(self) -> None:
        config = AppConfig(cooldown_ms=50)
        self.assertEqual(AppConfig.from_dict(config.to_dict()).cooldown_ms, 50)


if __name__ == "__main__":
    unittest.main()
