from __future__ import annotations

import argparse
import os
import threading
from pathlib import Path
from types import SimpleNamespace

from audio_manager import AudioManager
from config_manager import AppConfig, ConfigManager, resource_path
from gui import KeyboardSoundGUI
from keyboard_listener import KeyboardListenerManager
from tray_manager import TrayManager
from windows_integration import SingleInstance


class KeyboardSoundController:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._shutting_down = False

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.audio = AudioManager(
            sound_file=self.config.sound_file,
            volume=self.config.volume,
            cooldown_ms=self.config.cooldown_ms,
        )
        self.keyboard_listener = KeyboardListenerManager(self._handle_key_press)

        self.gui: KeyboardSoundGUI | None = None
        self.tray: TrayManager | None = None

    def start(self, minimized: bool = False) -> None:
        self.audio.initialize()
        self.keyboard_listener.start()

        self.gui = KeyboardSoundGUI(self)
        if minimized:
            self.gui.hide_window()
        self.tray = TrayManager(self)
        self.tray.start()

        self.gui.refresh()
        if minimized:
            self.gui.root.after(500, self.hide_window)
        self.gui.run()

    def _handle_key_press(self) -> None:
        if self.is_sound_enabled():
            self.audio.play()

    def get_config_snapshot(self) -> AppConfig:
        with self._lock:
            return AppConfig.from_dict(self.config.to_dict())

    def is_sound_enabled(self) -> bool:
        with self._lock:
            return self.config.enabled

    def toggle_sound(self) -> None:
        self.set_enabled(not self.is_sound_enabled())

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.config.enabled = bool(enabled)
            snapshot = AppConfig.from_dict(self.config.to_dict())
        self.config_manager.save(snapshot)
        self.refresh_views()

    def set_volume(self, volume: int) -> None:
        adjusted_volume = self.audio.set_volume(volume)
        with self._lock:
            self.config.volume = adjusted_volume
            snapshot = AppConfig.from_dict(self.config.to_dict())
        self.config_manager.save(snapshot)

    def set_sound_file(self, sound_file: str) -> tuple[bool, str]:
        path = str(Path(sound_file))
        if not self.audio.load_sound(path):
            return False, self.audio.last_error or "Unable to load the selected sound."

        with self._lock:
            self.config.sound_file = path
            snapshot = AppConfig.from_dict(self.config.to_dict())
        self.config_manager.save(snapshot)

        self.refresh_views()
        return True, "Sound file updated."

    def refresh_views(self) -> None:
        if self.gui is not None:
            self.gui.refresh()
        if self.tray is not None:
            self.tray.refresh()

    def hide_window(self) -> None:
        if self.gui is None:
            return
        if self.tray is not None and self.tray.is_running:
            self.gui.hide_window()
        else:
            self.gui.minimize_window()

    def show_window(self) -> None:
        if self.gui is not None:
            self.gui.show_window()

    def request_show_window(self) -> None:
        self._run_on_ui_thread(self.show_window)

    def request_toggle_sound(self) -> None:
        self._run_on_ui_thread(self.toggle_sound)

    def request_exit(self) -> None:
        self._run_on_ui_thread(self.exit_application)

    def _run_on_ui_thread(self, callback) -> None:
        if self.gui is None:
            callback()
            return
        self.gui.call_threadsafe(callback)

    def exit_application(self) -> None:
        with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True

        self.keyboard_listener.stop()
        self.audio.shutdown()

        if self.tray is not None:
            self.tray.stop()

        if self.gui is not None:
            self.gui.destroy()


def packaging_self_test() -> None:
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    audio = AudioManager()
    try:
        if not audio.initialize():
            raise RuntimeError(audio.last_error)
        for name in ("shotgun.wav", "fahhh_KcgAXfs.mp3"):
            if not audio.load_sound(str(resource_path(f"assets/{name}"))):
                raise RuntimeError(audio.last_error)
            if not audio.play():
                raise RuntimeError(audio.last_error or "Packaged playback failed.")
        controller = SimpleNamespace(
            toggle_sound=lambda: None,
            hide_window=lambda: None,
            set_volume=lambda _volume: None,
        )
        gui = KeyboardSoundGUI(controller)
        try:
            gui.hide_window()
            gui.root.update()
            if TrayManager._create_icon().size != (64, 64):
                raise RuntimeError("Packaged tray icon failed.")
        finally:
            gui.destroy()
    finally:
        audio.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Keyboard Sound")
    parser.add_argument("--tray", action="store_true", help="Start in the system tray")
    parser.add_argument("--self-test", action="store_true", help="Check packaged runtime")
    args = parser.parse_args()
    if args.self_test:
        packaging_self_test()
        return
    instance = SingleInstance()
    if not instance.acquire():
        return
    try:
        app = KeyboardSoundController()
        app.start(minimized=args.tray)
    finally:
        instance.release()


if __name__ == "__main__":
    main()
