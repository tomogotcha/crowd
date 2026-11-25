"""Acceptance tests for T-003: a finished task stops showing up (report #9).

~/.crowd/state.json keeps the last task after its PR merges. The task only
counts while you are on its crowd/T-* branch.

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-003's scope. Until cli/crowd.py has active_task(),
these tests skip, so main stays green while the task is open.

Run: python3 -m unittest discover -s tests
"""
import argparse
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
import crowd  # noqa: E402

STATE = {"task": "T-001", "repo": "o/r", "issue": 3, "name": "pip", "points": 7}


@unittest.skipUnless(hasattr(crowd, "active_task"), "T-003 not done yet: crowd.active_task doesn't exist")
class TestActiveTask(unittest.TestCase):
    def test_on_the_task_branch(self):
        self.assertEqual(crowd.active_task(STATE, "crowd/T-001"), "T-001")

    def test_elsewhere(self):
        for branch in ("main", "crowd/T-002", "crowd/T-0010", "", None):
            self.assertIsNone(crowd.active_task(STATE, branch), branch)

    def test_no_task(self):
        self.assertIsNone(crowd.active_task({}, "crowd/T-001"))

    def test_current_branch_exists(self):
        self.assertTrue(callable(crowd.current_branch))

    def patched(self, branch):
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(crowd, "load", lambda path, default: dict(STATE)))
        stack.enter_context(mock.patch.object(crowd, "current_branch", lambda: branch))
        saved = []
        stack.enter_context(mock.patch.object(crowd, "save", lambda path, data: saved.append(data)))
        return stack, saved

    def test_feedback_leaves_out_a_finished_task(self):
        stack, _ = self.patched("main")
        with stack:
            ctx = crowd.feedback_context(argparse.Namespace(command="feedback"))
        self.assertNotIn("task", ctx)
        self.assertNotIn("task_type", ctx)
        self.assertNotIn("project", ctx)

    def test_feedback_keeps_the_task_on_its_branch(self):
        stack, _ = self.patched("crowd/T-001")
        with stack:
            ctx = crowd.feedback_context(argparse.Namespace(command="feedback"))
        self.assertEqual(ctx.get("task"), "T-001")

    def pet_output(self, branch):
        stack, saved = self.patched(branch)
        out = io.StringIO()
        with stack, contextlib.redirect_stdout(out):
            crowd.cmd_pet(argparse.Namespace(name=None))
        return out.getvalue(), saved

    def test_pet_shows_no_task_off_its_branch(self):
        text, saved = self.pet_output("main")
        self.assertNotIn("T-001", text)
        self.assertIn("no task", text)
        self.assertEqual(saved, [])   # looking doesn't rewrite state

    def test_pet_shows_the_task_on_its_branch(self):
        text, _ = self.pet_output("crowd/T-001")
        self.assertIn("T-001", text)


if __name__ == "__main__":
    unittest.main()
