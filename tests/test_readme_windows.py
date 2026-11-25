"""Acceptance tests for T-005: the README works for Windows users (report #13).

On Windows `python3` is often the Microsoft Store stub; `py -3` works.

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-005's scope. Until the README has an "On Windows"
heading, these tests skip, so main stays green while the task is open.

Run: python3 -m unittest discover -s tests
"""
import re
import unittest
from pathlib import Path

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
HEADING = re.compile(r"^#{3,4} On Windows\s*$", re.M)


def section(text, start_heading):
    """Text from a '## X' heading up to the next '## ' heading."""
    m = re.search(rf"^## {re.escape(start_heading)}\s*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    end = re.search(r"^## ", rest, re.M)
    return rest[: end.start()] if end else rest


@unittest.skipUnless(HEADING.search(README), "T-005 not done yet: README has no 'On Windows' heading")
class TestReadmeWindows(unittest.TestCase):
    def test_windows_heading_is_under_commands(self):
        self.assertRegex(section(README, "Commands"), HEADING)

    def test_windows_setup_uses_py_launcher(self):
        part = HEADING.split(section(README, "Commands"), 1)[1]
        part = re.split(r"^#{2,4} ", part, flags=re.M)[0]
        self.assertIn("py -3", part)
        self.assertIn("crowd.py", part)
        self.assertNotIn("python3 ", part)

    def test_agent_prompt_mentions_windows(self):
        step = next(line for line in README.splitlines() if "Check I have python3" in line)
        self.assertIn("py -3", step)

    def test_unix_alias_still_there(self):
        self.assertIn("alias crowd='python3 ~/crowd/cli/crowd.py'", README)


if __name__ == "__main__":
    unittest.main()
