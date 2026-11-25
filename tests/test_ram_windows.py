"""Acceptance tests for T-004: `crowd survey` reads RAM on Windows (report #14).

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-004's scope. Until detect_ram_gb() takes a `system`
argument, these tests skip, so main stays green while the task is open.

The gate runs on Linux, so Windows is faked here. The task requires a
Windows machine so the agent can also try the real thing.

Run: python3 -m unittest discover -s tests
"""
import inspect
import platform
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
import crowd  # noqa: E402

READY = "system" in inspect.signature(crowd.detect_ram_gb).parameters


@unittest.skipUnless(READY, "T-004 not done yet: detect_ram_gb has no `system` argument")
class TestWindowsRam(unittest.TestCase):
    def test_rounds_to_whole_gb(self):
        self.assertEqual(crowd.detect_ram_gb(system="Windows", windows_bytes=lambda: 16 * 2**30), 16)
        self.assertEqual(crowd.detect_ram_gb(system="Windows", windows_bytes=lambda: int(15.8 * 2**30)), 16)

    def test_unknown_is_none(self):
        self.assertIsNone(crowd.detect_ram_gb(system="Windows", windows_bytes=lambda: None))

    def test_a_failing_reader_is_none(self):
        def boom():
            raise OSError("no")
        self.assertIsNone(crowd.detect_ram_gb(system="Windows", windows_bytes=boom))

    def test_reader_is_only_used_on_windows(self):
        calls = []
        crowd.detect_ram_gb(system="Plan9", windows_bytes=lambda: calls.append(1) or 2**30)
        self.assertEqual(calls, [])

    def test_windows_ram_bytes_is_safe_elsewhere(self):
        got = crowd.windows_ram_bytes()
        if platform.system() == "Windows":
            self.assertGreater(got, 2**28)
        else:
            self.assertIsNone(got)

    def test_default_is_this_machine(self):
        got = crowd.detect_ram_gb()
        self.assertTrue(got is None or got >= 1)


if __name__ == "__main__":
    unittest.main()
