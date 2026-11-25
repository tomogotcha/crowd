"""Acceptance tests for T-006: the maintainer's decide() (docs/maintainer.md, D-15).

decide() turns watcher items into proposed actions. It is pure: no GitHub,
no clock, no files. Every "never" rule in docs/maintainer.md that decide()
can see has a test here.

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-006's scope. Until cli/maintain.py exists, these tests
skip, so main stays green while the task is open.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAINTAIN = ROOT / "cli" / "maintain.py"
sys.path.insert(0, str(ROOT / "cli"))

POLICY = {"enabled": True, "rung": 1, "login": "crowd-bot"}


def load():
    spec = importlib.util.spec_from_file_location("crowd_maintain", MAINTAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def it(key, who="maintainer"):
    return {"key": key, "who": who, "text": key, "url": ""}


def pr(author="alice", model="model-a", approvals=()):
    return {"author": author, "author_model": model,
            "approvals": [{"by": b, "model": m} for b, m in approvals]}


@unittest.skipUnless(MAINTAIN.exists(), "T-006 not done yet: cli/maintain.py doesn't exist")
class TestDecide(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def kinds(self, items, policy=POLICY, facts=None):
        return [(a["kind"], a["target"]) for a in self.m.decide(items, policy, facts or {})]

    # ---- shape ----

    def test_action_shape_and_rungs(self):
        self.assertEqual(self.m.RUNG, {"draft-task": 2, "escalate": 2, "expire-lease": 2,
                                       "resync": 2, "request-review": 2, "merge": 3})
        [a] = self.m.decide([it("stale-lease:T-001")], POLICY, {})
        self.assertEqual(set(a), {"kind", "target", "rung", "why"})
        self.assertEqual((a["kind"], a["target"], a["rung"]), ("expire-lease", "T-001", 2))
        self.assertTrue(a["why"])

    def test_each_maintainer_item(self):
        items = [it("feedback:8"), it("stale-lease:T-001"), it("no-status:T-003"), it("pr-ready:20")]
        self.assertEqual(self.kinds(items, facts={"prs": {20: pr()}}), [
            ("draft-task", "#8"), ("expire-lease", "T-001"), ("resync", "T-003"), ("request-review", "#20")])

    def test_every_action_is_returned_whatever_the_rung(self):
        # The rung limits what runs, not what is proposed: a dry run shows it all.
        facts = {"prs": {20: pr(approvals=[("bob", "model-b")])}}
        for rung in (0, 1, 3):
            self.assertEqual(self.kinds([it("pr-ready:20")], {**POLICY, "rung": rung}, facts), [("merge", "#20")])

    def test_unknown_items_are_ignored(self):
        self.assertEqual(self.kinds([it("something-new:1"), it("local-behind")]), [])

    def test_does_not_change_its_input(self):
        items, facts = [it("pr-ready:20")], {"prs": {20: pr()}}
        before = repr((items, facts))
        self.m.decide(items, POLICY, facts)
        self.assertEqual(repr((items, facts)), before)

    # ---- pause switch ----

    def test_paused_does_nothing(self):
        items = [it("feedback:8"), it("stale-lease:T-001")]
        for policy in ({**POLICY, "enabled": False}, {}, {"rung": 3}):
            self.assertEqual(self.m.decide(items, policy, {}), [], policy)

    # ---- never: act on what isn't its ----

    def test_human_and_author_items_are_left_alone(self):
        items = [it("blocked:T-002", "human"), it("issue:5", "human"), it("pr-protected:3", "human"),
                 it("main-red:gate", "human"), it("pr-red:4", "author")]
        self.assertEqual(self.kinds(items), [])

    # ---- never: merge what it shouldn't ----

    def test_merge_needs_an_approval_from_a_different_model(self):
        cases = {
            "no approvals": pr(),
            "same model": pr(approvals=[("bob", "model-a")]),
            "reviewer model unknown": pr(approvals=[("bob", None)]),
            "author model unknown": pr(model=None, approvals=[("bob", "model-b")]),
            "author approved itself": pr(approvals=[("alice", "model-b")]),
        }
        for name, facts_pr in cases.items():
            self.assertEqual(self.kinds([it("pr-ready:20")], facts={"prs": {20: facts_pr}}),
                             [("request-review", "#20")], name)

    def test_merge_when_another_model_approved(self):
        facts = {"prs": {20: pr(approvals=[("bob", "model-a"), ("carol", "model-b")])}}
        self.assertEqual(self.kinds([it("pr-ready:20")], facts=facts), [("merge", "#20")])

    def test_model_names_compare_without_case_or_spaces(self):
        facts = {"prs": {20: pr(model="Model-A", approvals=[("bob", " model-a ")])}}
        self.assertEqual(self.kinds([it("pr-ready:20")], facts=facts), [("request-review", "#20")])

    def test_never_merges_its_own_pr(self):
        facts = {"prs": {20: pr(author="crowd-bot", approvals=[("bob", "model-b")])}}
        self.assertEqual(self.kinds([it("pr-ready:20")], facts=facts), [("request-review", "#20")])

    def test_its_own_approval_does_not_count(self):
        facts = {"prs": {20: pr(approvals=[("crowd-bot", "model-b")])}}
        self.assertEqual(self.kinds([it("pr-ready:20")], facts=facts), [("request-review", "#20")])

    def test_never_merges_a_protected_pr(self):
        facts = {"prs": {20: pr(approvals=[("bob", "model-b")])}}
        items = [it("pr-protected:20", "human"), it("pr-ready:20")]
        self.assertNotIn(("merge", "#20"), self.kinds(items, facts=facts))

    def test_no_facts_means_no_merge(self):
        self.assertEqual(self.kinds([it("pr-ready:20")], facts={}), [("request-review", "#20")])

    # ---- never: redraft what a human turned down ----

    def test_escalates_instead_of_redrafting(self):
        facts = {"closed_drafts": {8}}
        self.assertEqual(self.kinds([it("feedback:8"), it("feedback:9")], facts=facts),
                         [("escalate", "#8"), ("draft-task", "#9")])


if __name__ == "__main__":
    unittest.main()
