from __future__ import annotations

import os
import unittest
from uuid import uuid4

from windows_integration import SingleInstance


@unittest.skipUnless(os.name == "nt", "Windows mutex test")
class SingleInstanceTests(unittest.TestCase):
    def test_second_instance_is_blocked_until_first_exits(self) -> None:
        name = f"Local\\KeyboardSound-test-{uuid4()}"
        first = SingleInstance(name)
        second = SingleInstance(name)
        try:
            self.assertTrue(first.acquire())
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
        finally:
            first.release()
            second.release()


if __name__ == "__main__":
    unittest.main()
