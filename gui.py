from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config_manager import MAX_VOLUME


class KeyboardSoundGUI:
    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Keyboard Sound")
        self.root.geometry("390x285")
        self.root.minsize(390, 285)
        self.root.resizable(False, False)

        self.status_var = tk.StringVar()
        self.volume_var = tk.IntVar()
        self.volume_label_var = tk.StringVar()
        self.sound_file_var = tk.StringVar()

        self._build_styles()
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.controller.hide_window)

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Primary.TButton", padding=(12, 8))
        style.configure("Secondary.TButton", padding=(10, 7))

    def _build_layout(self) -> None:
        frame = ttk.Frame(self.root, padding=22)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="Keyboard Sound", style="Title.TLabel")
        title.pack(anchor="w")

        status_row = ttk.Frame(frame)
        status_row.pack(fill="x", pady=(18, 10))

        status = ttk.Label(
            status_row,
            textvariable=self.status_var,
            style="Status.TLabel",
        )
        status.pack(side="left")

        self.toggle_button = ttk.Button(
            status_row,
            style="Primary.TButton",
            command=self.controller.toggle_sound,
        )
        self.toggle_button.pack(side="right")

        volume_row = ttk.Frame(frame)
        volume_row.pack(fill="x", pady=(8, 6))

        ttk.Label(volume_row, text="Volume").pack(side="left")
        ttk.Label(volume_row, textvariable=self.volume_label_var).pack(side="right")

        volume_scale = ttk.Scale(
            frame,
            from_=0,
            to=MAX_VOLUME,
            orient="horizontal",
            variable=self.volume_var,
            command=self._volume_changed,
        )
        volume_scale.pack(fill="x", pady=(0, 14))

        sound_row = ttk.Frame(frame)
        sound_row.pack(fill="x", pady=(6, 12))

        ttk.Button(
            sound_row,
            text="Choose Sound",
            style="Secondary.TButton",
            command=self._choose_sound,
        ).pack(side="left")

        ttk.Label(
            sound_row,
            textvariable=self.sound_file_var,
            width=28,
            anchor="e",
        ).pack(side="right")

        ttk.Button(
            frame,
            text="Minimize to Tray",
            style="Secondary.TButton",
            command=self.controller.hide_window,
        ).pack(fill="x", pady=(10, 0))

    def _volume_changed(self, value: str) -> None:
        volume = int(float(value))
        self.volume_label_var.set(f"{volume}%")
        self.controller.set_volume(volume)

    def _choose_sound(self) -> None:
        sound_file = filedialog.askopenfilename(
            title="Choose keyboard sound",
            filetypes=(
                ("Audio files", ("*.wav", "*.mp3")),
                ("WAV files", "*.wav"),
                ("MP3 files", "*.mp3"),
                ("All files", "*.*"),
            ),
        )
        if not sound_file:
            return

        success, message = self.controller.set_sound_file(sound_file)
        if not success:
            messagebox.showerror("Keyboard Sound", message)

    def refresh(self) -> None:
        config = self.controller.get_config_snapshot()
        enabled_label = "ON" if config.enabled else "OFF"

        self.status_var.set(f"Status: {enabled_label}")
        self.toggle_button.configure(
            text="Disable Sound" if config.enabled else "Enable Sound"
        )
        self.volume_var.set(config.volume)
        self.volume_label_var.set(f"{config.volume}%")

        sound_name = Path(config.sound_file or "").name
        self.sound_file_var.set(sound_name or "No sound selected")

    def call_threadsafe(self, callback: Callable[..., None], *args: Any) -> None:
        self.root.after(0, lambda: callback(*args))

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self) -> None:
        self.root.withdraw()

    def minimize_window(self) -> None:
        self.root.iconify()

    def destroy(self) -> None:
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
