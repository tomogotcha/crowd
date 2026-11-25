"""Acceptance tests for T-007: `crowd maintain --dry-run` (rung 1, docs/maintainer.md).

Only the pure parts are tested (policy parsing, PR facts, the printed plan)
plus one CLI check that needs no network. Reading GitHub is not tested.

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-007's scope. Until cli/maintain.py has render(), these
tests skip, so main stays green while the task is open.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAINTAIN = ROOT / "cli" / "maintain.py"
sys.path.insert(0, str(ROOT / "cli"))


def load():
    spec = importlib.util.spec_from_file_location("crowd_maintain", MAINTAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


READY = MAINTAIN.exists() and hasattr(load(), "render")


def review(by, state, body=""):
    return {"author": {"login": by}, "state": state, "body": body}


@unittest.skipUnless(READY, "T-007 not done yet: cli/maintain.py has no render()")
class TestDryRun(unittest.TestCase):
    def setUp(self):
        self.m = load()

    # ---- policy ----

    def test_policy_file_on_main_parses(self):
        p = self.m.load_policy((ROOT / ".crowd" / "policy" / "maintainer.yaml").read_text())
        self.assertIs(p["enabled"], True)
        self.assertIn(p["rung"], (0, 1, 2, 3))

    def test_missing_or_broken_policy_is_paused(self):
        for text in ("", "   ", "not: [valid", "- a list\n", "rung: 2\n"):
            p = self.m.load_policy(text)
            self.assertIs(p["enabled"], False, text)

    def test_policy_defaults(self):
        p = self.m.load_policy("enabled: true\n")
        self.assertEqual((p["enabled"], p["rung"], p["login"], p["max_actions_per_day"]), (True, 0, "", 20))

    def test_bad_rung_is_zero(self):
        for rung in ("'three'", "7", "-1", "null"):
            self.assertEqual(self.m.load_policy(f"enabled: true\nrung: {rung}\n")["rung"], 0, rung)

    def test_enabled_must_be_true_not_truthy(self):
        self.assertIs(self.m.load_policy("enabled: 'yes please'\n")["enabled"], False)

    # ---- PR facts ----

    def test_pr_facts(self):
        pr = {"author": {"login": "alice"}, "body": "Task: T-002\nModel: model-a\n",
              "reviews": [review("bob", "APPROVED", "looks right\nModel: model-b"),
                          review("carol", "COMMENTED", "Model: model-c")]}
        self.assertEqual(self.m.pr_facts(pr), {
            "author": "alice", "author_model": "model-a",
            "approvals": [{"by": "bob", "model": "model-b"}]})

    def test_no_model_line_is_none(self):
        pr = {"author": {"login": "alice"}, "body": "no model here",
              "reviews": [review("bob", "APPROVED", "lgtm")]}
        self.assertEqual(self.m.pr_facts(pr), {
            "author": "alice", "author_model": None, "approvals": [{"by": "bob", "model": None}]})

    def test_latest_review_per_reviewer_counts(self):
        pr = {"author": {"login": "alice"}, "body": "",
              "reviews": [review("bob", "APPROVED", "Model: model-b"),
                          review("bob", "CHANGES_REQUESTED", "Model: model-b"),
                          review("dan", "CHANGES_REQUESTED", "Model: model-d"),
                          review("dan", "APPROVED", "Model: model-d")]}
        self.assertEqual(self.m.pr_facts(pr)["approvals"], [{"by": "dan", "model": "model-d"}])

    def test_missing_fields(self):
        self.assertEqual(self.m.pr_facts({}), {"author": None, "author_model": None, "approvals": []})

    # ---- the printed plan ----

    def test_render(self):
        actions = [{"kind": "expire-lease", "target": "T-001", "rung": 2, "why": "quiet 30h"},
                   {"kind": "merge", "target": "#20", "rung": 3, "why": "green and approved"}]
        self.assertEqual(self.m.render(actions, 2), [
            "would expire-lease T-001: quiet 30h",
            "would merge #20: green and approved  (needs rung 3; now 2)"])

    def test_render_nothing(self):
        self.assertEqual(self.m.render([], 1), ["nothing to do"])

    # ---- the command ----

    def test_maintain_without_dry_run_refuses(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, str(ROOT / "cli" / "crowd.py"), "maintain"],
                               capture_output=True, text=True, cwd=ROOT,
                               env={**os.environ, "CROWD_HOME": home, "GH_TOKEN": "", "PATH": ""})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--dry-run", r.stdout + r.stderr)

    def test_help_lists_maintain(self):
        r = subprocess.run([sys.executable, str(ROOT / "cli" / "crowd.py"), "maintain", "--help"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0)
        self.assertIn("--dry-run", r.stdout)


if __name__ == "__main__":
    unittest.main()
