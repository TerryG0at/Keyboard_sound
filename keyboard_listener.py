from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

try:
    from pynput import keyboard
except Exception:  # pragma: no cover - exercised only when pynput is unavailable
    keyboard = None


class KeyboardListenerManager:
    def __init__(
        self,
        on_key_press: Callable[[], None],
    ) -> None:
        self.on_key_press = on_key_press
        self.last_error: str | None = None
        self._listener: Any | None = None
        self._lock = threading.RLock()
        self._running = False
        self._last_key: Any | None = None
        self._consecutive_presses = 0

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True

            if keyboard is None:
                self.last_error = "pynput is not installed or could not start."
                return False

            try:
                self._listener = keyboard.Listener(on_press=self._handle_press)
                self._listener.daemon = True
                self._last_key = None
                self._consecutive_presses = 0
                self._running = True
                self._listener.start()
                self.last_error = None
            except Exception as exc:
                self._listener = None
                self._running = False
                self.last_error = f"Could not start keyboard listener: {exc}"
                return False

        return True

    def _handle_press(self, key: Any) -> None:
        with self._lock:
            if not self._running:
                return
            # Keep only the latest key in memory for comparison, never a key log.
            if key == self._last_key:
                if self._consecutive_presses >= 5:
                    return
                self._consecutive_presses += 1
            else:
                self._last_key = key
                self._consecutive_presses = 1
            if self._consecutive_presses == 5:
                return
        try:
            self.on_key_press()
        except Exception as exc:
            self.last_error = f"Keyboard callback failed: {exc}"

    def stop(self) -> None:
        with self._lock:
            listener = self._listener
            self._listener = None
            self._running = False
            self._last_key = None
            self._consecutive_presses = 0

        if listener is None:
            return

        try:
            listener.stop()
            listener.join(timeout=1.0)
        except Exception as exc:
            self.last_error = f"Could not stop keyboard listener cleanly: {exc}"
