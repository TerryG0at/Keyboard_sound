from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from keyboard_listener import KeyboardListenerManager


class KeyboardListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.play = Mock()
        self.manager = KeyboardListenerManager(self.play)
        self.manager._running = True

    def test_fifth_press_and_later_repeats_do_not_trigger_playback(self) -> None:
        for _ in range(4):
            self.manager._handle_press("a")
        self.assertEqual(self.play.call_count, 4)

        self.manager._handle_press("a")
        self.assertEqual(self.play.call_count, 4)
        for _ in range(1000):
            self.manager._handle_press("a")
        self.assertEqual(self.play.call_count, 4)
        self.assertEqual(self.manager._consecutive_presses, 5)

    def test_different_key_restores_playback_and_starts_new_count(self) -> None:
        for _ in range(10):
            self.manager._handle_press("a")
        self.manager._handle_press("b")
        self.assertEqual(self.play.call_count, 5)
        self.assertEqual(self.manager._consecutive_presses, 1)
        for _ in range(4):
            self.manager._handle_press("b")
        self.assertEqual(self.play.call_count, 8)

    def test_every_different_key_resets_the_run(self) -> None:
        for key in "aaaabaaaab":
            self.manager._handle_press(key)
        self.assertEqual(self.play.call_count, 10)

    def test_backspace_auto_repeat_is_suppressed(self) -> None:
        backspace = object()
        for _ in range(50):
            self.manager._handle_press(backspace)
        self.assertEqual(self.play.call_count, 4)
        self.manager._handle_press("a")
        self.manager._handle_press(backspace)
        self.assertEqual(self.play.call_count, 6)

    def test_stopped_listener_ignores_presses_and_clears_state(self) -> None:
        self.manager._handle_press("a")
        self.manager.stop()
        self.manager._handle_press("b")
        self.assertEqual(self.play.call_count, 1)
        self.assertIsNone(self.manager._last_key)
        self.assertEqual(self.manager._consecutive_presses, 0)

    def test_restart_resets_muted_key(self) -> None:
        for _ in range(5):
            self.manager._handle_press("a")
        self.manager.stop()
        backend = SimpleNamespace(Listener=Mock())
        with patch("keyboard_listener.keyboard", backend):
            self.assertTrue(self.manager.start())
            self.manager._handle_press("a")
            self.assertEqual(self.play.call_count, 5)
            self.assertEqual(self.manager._consecutive_presses, 1)
            self.manager.stop()


if __name__ == "__main__":
    unittest.main()
