"""Tests for cli/watch.py: what the watcher says needs someone, and what changed.

Only the pure decisions are tested; reading GitHub is not.

Run: python3 -m unittest discover -s tests
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
import watch  # noqa: E402

NOW = dt.datetime(2026, 11, 24, 12, 0, tzinfo=dt.timezone.utc)
CONFIG = {"lease_ttl_hours": 24, "protected_paths": ["docs/asset-policy.md"]}


def issue(n, title, labels, updated="2026-11-24T11:00:00Z"):
    return {"number": n, "title": title, "labels": [{"name": x} for x in labels], "updatedAt": updated, "url": ""}


def pr(n, files, checks, draft=False):
    return {"number": n, "title": f"PR {n}", "isDraft": draft, "url": "",
            "files": [{"path": f} for f in files],
            "statusCheckRollup": [{"conclusion": c} for c in checks]}


def keys(snap):
    return {i["key"]: i["who"] for i in watch.attention(snap, CONFIG, NOW)}


class Attention(unittest.TestCase):
    def test_quiet_board_needs_nobody(self):
        snap = {"issues": [issue(1, "T-001: x", ["crowd:task", "status:open"]),
                           issue(2, "T-002: y", ["crowd:task", "status:leased"])]}
        self.assertEqual(keys(snap), {})

    def test_issues(self):
        snap = {"issues": [
            issue(1, "T-001: x", ["crowd:task", "status:leased"], "2026-11-23T11:00:00Z"),
            issue(2, "T-002: y", ["crowd:task", "status:blocked"]),
            issue(3, "T-003: z", ["crowd:task"]),
            issue(4, "FEEDBACK (bug): claim prints twice", ["crowd:feedback"]),
            issue(5, "Warn direct PRs", ["enhancement"]),
        ]}
        self.assertEqual(keys(snap), {
            "stale-lease:T-001": "maintainer", "blocked:T-002": "human", "no-status:T-003": "maintainer",
            "feedback:4": "maintainer", "issue:5": "human"})

    def test_prs(self):
        snap = {"prs": [
            pr(1, ["cli/crowd.py"], ["SUCCESS"]),
            pr(2, ["cli/crowd.py"], ["SUCCESS", "FAILURE"]),
            pr(3, ["cli/gate/plan.py", "docs/asset-policy.md"], ["SUCCESS"]),
            pr(4, ["cli/crowd.py"], ["SUCCESS"], draft=True),
            pr(5, ["cli/crowd.py"], [None]),
        ]}
        self.assertEqual(keys(snap), {"pr-ready:1": "maintainer", "pr-red:2": "author", "pr-protected:3": "human"})

    def test_protected_pr_is_never_ready(self):
        got = keys({"prs": [pr(1, [".github/workflows/gate.yml"], ["SUCCESS"])]})
        self.assertNotIn("pr-ready:1", got)

    def test_only_latest_finished_run_counts(self):
        runs = [{"workflowName": "gate", "status": "in_progress", "conclusion": ""},
                {"workflowName": "gate", "status": "completed", "conclusion": "success"},
                {"workflowName": "gate", "status": "completed", "conclusion": "failure"},
                {"workflowName": "board", "status": "completed", "conclusion": "failure"}]
        self.assertEqual(keys({"runs": runs}), {"main-red:board": "human"})

    def test_local(self):
        self.assertEqual(keys({"local": {"branch": "main", "behind": True}}), {"local-behind": "human"})
        self.assertEqual(keys({"local": {"branch": "main"}}), {})


class Diff(unittest.TestCase):
    def test_raised_and_cleared(self):
        a, b, c = (watch.item(k, "human", k) for k in "abc")
        raised, cleared = watch.diff([a, b], [b, c])
        self.assertEqual([i["key"] for i in raised], ["c"])
        self.assertEqual([i["key"] for i in cleared], ["a"])


if __name__ == "__main__":
    unittest.main()
