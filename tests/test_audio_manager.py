from __future__ import annotations

import tempfile
import unittest
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from audio_manager import AudioManager, prepare_audio


class FakeSound:
    def __init__(self) -> None:
        self.volume = None

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def get_raw(self) -> bytes:
        return array("h", [1000, -1000] * 16).tobytes()


class FakeChannel:
    def __init__(self, busy: bool = False) -> None:
        self.busy = busy
        self.play_count = 0

    def get_busy(self) -> bool:
        return self.busy

    def play(self, _sound: FakeSound) -> None:
        self.play_count += 1


class AudioManagerTests(unittest.TestCase):
    def test_load_accepts_wav_and_mp3_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".wav", ".WAV", ".mp3", ".MP3"):
                with self.subTest(suffix=suffix):
                    path = Path(directory) / f"sound{suffix}"
                    path.touch()
                    sound = FakeSound()
                    loader = Mock(return_value=sound)
                    module = SimpleNamespace(mixer=SimpleNamespace(Sound=loader, get_init=lambda: (44100, -16, 2)))
                    manager = AudioManager(volume=70, pygame_module=module)
                    manager._initialized = True

                    self.assertTrue(manager.load_sound(str(path)))
                    self.assertEqual(loader.call_args_list[0].args, (str(path),))
                    self.assertTrue(manager.is_ready)
                    self.assertEqual(sound.volume, 0.7 / 4)
                    self.assertEqual(manager.sound_file, str(path))
                    self.assertIsNone(manager.last_error)

    def test_unsupported_extension_is_rejected(self) -> None:
        loader = Mock()
        module = SimpleNamespace(mixer=SimpleNamespace(Sound=loader))
        manager = AudioManager(pygame_module=module)
        manager._initialized = True

        self.assertFalse(manager.load_sound("sound.txt"))
        self.assertFalse(manager.is_ready)
        self.assertEqual(manager.last_error, "Please choose a .wav or .mp3 audio file.")
        loader.assert_not_called()

    def test_corrupt_mp3_reports_load_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.mp3"
            path.touch()
            loader = Mock(side_effect=RuntimeError("Invalid audio data"))
            module = SimpleNamespace(mixer=SimpleNamespace(Sound=loader))
            manager = AudioManager(pygame_module=module)
            manager._initialized = True

            self.assertFalse(manager.load_sound(str(path)))
            self.assertFalse(manager.is_ready)
            self.assertEqual(manager.last_error, "Could not load sound file: Invalid audio data")

    def test_cooldown_prevents_rapid_replay(self) -> None:
        times = iter([0.00, 0.02, 0.06])
        channel = FakeChannel()
        manager = AudioManager(cooldown_ms=50, pygame_module=None, time_source=lambda: next(times))
        manager._initialized = True
        manager._sound = FakeSound()
        manager._channels = [channel]

        self.assertTrue(manager.play())
        self.assertFalse(manager.play())
        self.assertTrue(manager.play())
        self.assertEqual(channel.play_count, 2)

    def test_busy_channels_prevent_uncontrolled_stacking(self) -> None:
        channel = FakeChannel(busy=True)
        manager = AudioManager(cooldown_ms=0, channel_count=1, max_channel_count=1, pygame_module=None, time_source=lambda: 1.0)
        manager._initialized = True
        manager._sound = FakeSound()
        manager._channels = [channel]

        self.assertFalse(manager.play())
        self.assertEqual(channel.play_count, 0)

    def test_volume_is_clamped_and_applied(self) -> None:
        sound = FakeSound()
        manager = AudioManager(volume=70, pygame_module=None)
        manager._sound = sound

        manager._gain = 4.0
        self.assertEqual(manager.set_volume(200), 200)
        self.assertEqual(sound.volume, 0.5)
        self.assertEqual(manager.set_volume(999), 400)
        self.assertEqual(sound.volume, 1.0)

    def test_quiet_audio_is_amplified_four_times(self) -> None:
        raw, gain = prepare_audio(array("h", [1000, -1000]).tobytes(), 44100, 2)
        self.assertEqual(gain, 4.0)
        self.assertEqual(list(array("h", raw)), [4000, -4000])

    def test_boost_limits_peaks_without_wraparound(self) -> None:
        raw, gain = prepare_audio(array("h", [20000, -20000]).tobytes(), 44100, 2)
        self.assertEqual(gain, 1.6)
        self.assertEqual(list(array("h", raw)), [32000, -32000])

    def test_leading_silence_is_trimmed_on_frame_boundaries(self) -> None:
        samples = array("h", [0, 0] * 100 + [1000, -1000] * 10)
        raw, _gain = prepare_audio(samples.tobytes(), 1000, 2)
        self.assertEqual(list(array("h", raw))[:6], [0, 0, 0, 0, 4000, -4000])
        self.assertEqual(len(raw), 12 * 2 * 2)

    def test_silent_audio_stays_silent(self) -> None:
        original = array("h", [0] * 100).tobytes()
        raw, gain = prepare_audio(original, 44100, 2)
        self.assertEqual(raw, original)
        self.assertEqual(gain, 1.0)

    def test_channel_pool_grows_without_interrupting_active_sounds(self) -> None:
        active = [FakeChannel(busy=True) for _ in range(64)]
        created = []

        def create_channel(_index):
            channel = FakeChannel()
            created.append(channel)
            return channel

        mixer = SimpleNamespace(set_num_channels=Mock(), Channel=create_channel)
        manager = AudioManager(pygame_module=SimpleNamespace(mixer=mixer))
        manager._initialized = True
        manager._sound = FakeSound()
        manager._channels = active.copy()

        self.assertTrue(manager.play())
        mixer.set_num_channels.assert_called_once_with(96)
        self.assertEqual(len(manager._channels), 96)
        self.assertEqual(created[0].play_count, 1)
        self.assertTrue(all(channel.play_count == 0 for channel in active))

    def test_default_cooldown_allows_fast_keypresses(self) -> None:
        manager = AudioManager(time_source=lambda: 1.0)
        manager._initialized = True
        manager._sound = FakeSound()
        channel = FakeChannel()
        manager._channels = [channel]
        for _ in range(1000):
            self.assertTrue(manager.play())
        self.assertEqual(channel.play_count, 1000)

    def test_failed_selection_preserves_previous_sound(self) -> None:
        manager = AudioManager(sound_file="previous.wav")
        manager._initialized = True
        sound = FakeSound()
        manager._sound = sound
        self.assertFalse(manager.load_sound("unsupported.txt"))
        self.assertIs(manager._sound, sound)
        self.assertEqual(manager.sound_file, "previous.wav")

    def test_stop_playback_stops_all_channels_and_resets_cooldown(self) -> None:
        manager = AudioManager(cooldown_ms=1000, time_source=lambda: 1.0)
        manager._initialized = True
        manager._sound = FakeSound()
        manager._channels = [Mock(), Mock(), Mock()]
        manager._last_played_at = 1.0

        manager.stop_playback()

        for channel in manager._channels:
            channel.stop.assert_called_once_with()
        self.assertTrue(manager.can_play_now())
        self.assertTrue(manager.is_ready)

    def test_stop_playback_continues_if_one_channel_fails(self) -> None:
        manager = AudioManager()
        manager._initialized = True
        broken = Mock()
        broken.stop.side_effect = RuntimeError("Channel unavailable")
        healthy = Mock()
        manager._channels = [broken, healthy]

        manager.stop_playback()

        healthy.stop.assert_called_once_with()
        self.assertIn("Channel unavailable", manager.last_error)


if __name__ == "__main__":
    unittest.main()
