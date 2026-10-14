from __future__ import annotations

import threading
import time
from array import array
from pathlib import Path
from typing import Any, Callable

from config_manager import DEFAULT_COOLDOWN_MS, MAX_VOLUME


def prepare_audio(raw: bytes, sample_rate: int, channels: int) -> tuple[bytes, float]:
    samples = array("h")
    samples.frombytes(raw)
    if not samples:
        return raw, 1.0

    peak = max(abs(sample) for sample in samples)
    gain = min(MAX_VOLUME / 100, 32000 / peak) if peak else 1.0
    gain = max(1.0, gain)

    # Remove leading digital silence, retaining 2 ms before the attack.
    first_sample = next((index for index, sample in enumerate(samples) if sample), 0)
    start_frame = max(0, first_sample // channels - sample_rate // 500)
    samples = samples[start_frame * channels:]
    boosted = array(
        "h", (max(-32768, min(32767, round(sample * gain))) for sample in samples)
    )
    return boosted.tobytes(), gain

try:
    import pygame
except Exception:  # pragma: no cover - exercised only when pygame is unavailable
    pygame = None


class AudioManager:
    def __init__(
        self,
        sound_file: str | None = None,
        volume: int = 70,
        cooldown_ms: int = DEFAULT_COOLDOWN_MS,
        channel_count: int = 64,
        pygame_module: Any | None = None,
        time_source: Callable[[], float] | None = None,
        max_channel_count: int = 256,
    ) -> None:
        self.sound_file = sound_file
        self.volume = self._clamp_volume(volume)
        self.cooldown_ms = max(0, int(cooldown_ms))
        self.channel_count = max(1, int(channel_count))
        self.max_channel_count = max(self.channel_count, int(max_channel_count))
        self.last_error: str | None = None

        self._pygame = pygame_module if pygame_module is not None else pygame
        self._time_source = time_source or time.monotonic
        self._lock = threading.RLock()
        self._initialized = False
        self._sound: Any | None = None
        self._channels: list[Any] = []
        self._last_played_at: float | None = None
        self._gain = 1.0

    @staticmethod
    def _clamp_volume(volume: int | float) -> int:
        try:
            value = int(volume)
        except (TypeError, ValueError):
            value = 70
        return max(0, min(MAX_VOLUME, value))

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._sound is not None

    def initialize(self) -> bool:
        with self._lock:
            if self._pygame is None:
                self.last_error = "pygame is not installed."
                return False

            try:
                mixer = self._pygame.mixer
                mixer.pre_init(44100, -16, 2, 256)
                if not mixer.get_init():
                    mixer.init(
                        frequency=44100, size=-16, channels=2,
                        buffer=256, allowedchanges=0,
                    )
                if mixer.get_init()[1] != -16:
                    raise RuntimeError("Audio boost requires a signed 16-bit mixer.")
                mixer.set_num_channels(self.channel_count)
                self._channels = [
                    mixer.Channel(index) for index in range(self.channel_count)
                ]
                self._initialized = True
                self.last_error = None
            except Exception as exc:
                self._initialized = False
                self.last_error = f"Could not initialize audio: {exc}"
                return False

        if self.sound_file:
            self.load_sound(self.sound_file)

        return self._initialized

    def load_sound(self, sound_file: str) -> bool:
        path = Path(sound_file)
        with self._lock:
            if not self._initialized or self._pygame is None:
                self.last_error = "Audio system is not initialized."
                return False

            if path.suffix.lower() not in (".wav", ".mp3"):
                self.last_error = "Please choose a .wav or .mp3 audio file."
                return False

            if not path.exists():
                self.last_error = f"Sound file not found: {path}"
                return False

        # Decode and amplify once, outside the lock used by the keyboard callback.
        try:
            source = self._pygame.mixer.Sound(str(path))
            sample_rate, _format, channels = self._pygame.mixer.get_init()
            raw, gain = prepare_audio(source.get_raw(), sample_rate, channels)
            sound = self._pygame.mixer.Sound(buffer=raw)
            with self._lock:
                if not self._initialized:
                    return False
                sound.set_volume(min(1.0, self.volume / 100 / gain))
                self._gain = gain
                self._sound = sound
                self.sound_file = str(path)
                self.last_error = None
        except Exception as exc:
            with self._lock:
                self.last_error = f"Could not load sound file: {exc}"
            return False

        return True

    def set_volume(self, volume: int | float) -> int:
        with self._lock:
            self.volume = self._clamp_volume(volume)
            if self._sound is not None:
                try:
                    self._sound.set_volume(min(1.0, self.volume / 100 / self._gain))
                except Exception as exc:
                    self.last_error = f"Could not update volume: {exc}"
        return self.volume

    def set_cooldown_ms(self, cooldown_ms: int | float) -> int:
        with self._lock:
            self.cooldown_ms = max(0, int(cooldown_ms))
        return self.cooldown_ms

    def can_play_now(self, now: float | None = None) -> bool:
        with self._lock:
            if self._last_played_at is None:
                return True
            current = self._time_source() if now is None else now
            elapsed_ms = (current - self._last_played_at) * 1000
            return elapsed_ms >= self.cooldown_ms

    def play(self) -> bool:
        with self._lock:
            if not self.is_ready:
                return False

            now = self._time_source()
            if not self.can_play_now(now):
                return False

            channel = self._next_available_channel()
            if channel is None:
                return False

            try:
                channel.play(self._sound)
                self._last_played_at = now
                self.last_error = None
            except Exception as exc:
                self.last_error = f"Could not play sound: {exc}"
                return False

        return True

    def _next_available_channel(self) -> Any | None:
        for channel in self._channels:
            try:
                if not channel.get_busy():
                    return channel
            except Exception:
                continue
        # Grow only when necessary; never steal a playing voice or queue old keys.
        old_count = len(self._channels)
        if old_count < self.max_channel_count and self._pygame is not None:
            try:
                new_count = min(self.max_channel_count, old_count + 32)
                self._pygame.mixer.set_num_channels(new_count)
                added = [
                    self._pygame.mixer.Channel(index)
                    for index in range(old_count, new_count)
                ]
                self._channels.extend(added)
                return added[0]
            except Exception as exc:
                self.last_error = f"Could not allocate playback channels: {exc}"
        return None

    def stop_playback(self) -> None:
        with self._lock:
            if not self._initialized:
                return
            error = None
            for channel in self._channels:
                try:
                    channel.stop()
                except Exception as exc:
                    error = f"Could not stop playback: {exc}"
            self._last_played_at = None
            self.last_error = error

    def shutdown(self) -> None:
        with self._lock:
            if not self._initialized or self._pygame is None:
                return

            try:
                self._pygame.mixer.quit()
            except Exception as exc:
                self.last_error = f"Could not shut down audio cleanly: {exc}"
            finally:
                self._initialized = False
                self._sound = None
                self._channels = []
