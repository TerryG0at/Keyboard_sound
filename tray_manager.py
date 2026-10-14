from __future__ import annotations

import threading
from typing import Any

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - exercised only when tray deps are missing
    pystray = None
    Image = None
    ImageDraw = None


class TrayManager:
    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.last_error: str | None = None
        self._icon: Any | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

    @property
    def is_available(self) -> bool:
        return pystray is not None and Image is not None and ImageDraw is not None

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self) -> bool:
        if not self.is_available:
            self.last_error = "pystray or Pillow is not installed."
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        if pystray is None:
            return

        self._icon = pystray.Icon(
            "Keyboard Sound",
            self._create_icon(),
            "Keyboard Sound",
            self._menu(),
        )
        self._running.set()
        try:
            self._icon.run()
        except Exception as exc:
            self.last_error = f"System tray failed: {exc}"
        finally:
            self._running.clear()

    def _menu(self) -> Any:
        return pystray.Menu(
            pystray.MenuItem("Show Window", self._show_window, default=True),
            pystray.MenuItem(self._toggle_label, self._toggle_sound),
            pystray.MenuItem("Exit", self._exit_app),
        )

    def _toggle_label(self, *_args: Any) -> str:
        return "Disable Sound" if self.controller.is_sound_enabled() else "Enable Sound"

    def _show_window(self, _icon: Any, _item: Any) -> None:
        self.controller.request_show_window()

    def _toggle_sound(self, _icon: Any, _item: Any) -> None:
        self.controller.request_toggle_sound()

    def _exit_app(self, _icon: Any, _item: Any) -> None:
        self.controller.request_exit()

    def refresh(self) -> None:
        icon = self._icon
        if icon is None:
            return
        try:
            icon.update_menu()
        except Exception as exc:
            self.last_error = f"Could not refresh tray menu: {exc}"

    def stop(self) -> None:
        icon = self._icon
        self._icon = None
        self._running.clear()

        if icon is None:
            return

        try:
            icon.stop()
        except Exception as exc:
            self.last_error = f"Could not stop tray icon cleanly: {exc}"

    @staticmethod
    def _create_icon() -> Any:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rounded_rectangle((6, 14, 46, 48), radius=7, fill=(38, 70, 83, 255))
        draw.rectangle((12, 21, 20, 29), fill=(238, 246, 247, 255))
        draw.rectangle((23, 21, 31, 29), fill=(238, 246, 247, 255))
        draw.rectangle((34, 21, 42, 29), fill=(238, 246, 247, 255))
        draw.rectangle((12, 33, 42, 41), fill=(238, 246, 247, 255))

        draw.arc((41, 18, 57, 34), start=-45, end=45, fill=(233, 196, 106, 255), width=3)
        draw.arc((44, 12, 64, 40), start=-45, end=45, fill=(244, 162, 97, 255), width=3)
        return image
