"""Acceptance tests for T-002: `crowd claim` prints the task id once (report #8).

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-002's scope. Until cli/crowd.py has task_label(), these
tests skip, so main stays green while the task is open.

Run: python3 -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
import crowd  # noqa: E402


@unittest.skipUnless(hasattr(crowd, "task_label"), "T-002 not done yet: crowd.task_label doesn't exist")
class TestTaskLabel(unittest.TestCase):
    def test_title_already_starts_with_the_id(self):
        self.assertEqual(crowd.task_label("T-001", "T-001: Add a probe"), "T-001: Add a probe")

    def test_title_without_the_id(self):
        self.assertEqual(crowd.task_label("T-001", "Add a probe"), "T-001: Add a probe")

    def test_only_a_leading_id_counts(self):
        self.assertEqual(crowd.task_label("T-001", "Follow up on T-001"), "T-001: Follow up on T-001")

    def test_other_id_is_not_stripped(self):
        self.assertEqual(crowd.task_label("T-002", "T-001: old"), "T-002: T-001: old")

    def test_separator_variants(self):
        for title in ("T-001: x", "T-001 x", "T-001 - x", "T-001:x"):
            self.assertEqual(crowd.task_label("T-001", title), "T-001: x", title)

    def test_id_only(self):
        self.assertEqual(crowd.task_label("T-001", "T-001"), "T-001")
        self.assertEqual(crowd.task_label("T-001", ""), "T-001")


if __name__ == "__main__":
    unittest.main()
