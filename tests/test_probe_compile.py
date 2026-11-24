"""Acceptance tests for T-001: the fast_compile probe.

Written before the task was posted (P2). The task's agent may not edit this
file; it is outside T-001's scope. Until cli/probes/compile.py exists, these
tests skip, so main stays green while the task is open.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "cli" / "probes" / "compile.py"
sys.path.insert(0, str(ROOT / "cli"))


def load_probe():
    spec = importlib.util.spec_from_file_location("crowd_probe_compile", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PROBE.exists(), "T-001 not done yet: cli/probes/compile.py doesn't exist")
class TestCompileProbe(unittest.TestCase):
    def setUp(self):
        self.mod = load_probe()

    def fake(self, times):
        it = iter(times)
        calls = []

        def time_once():
            calls.append(1)
            return next(it)
        return time_once, calls

    def test_constants(self):
        self.assertEqual(self.mod.THRESHOLD_S, 0.25)
        self.assertEqual(self.mod.RUNS, 3)
        self.assertEqual(self.mod.REPEATS, 20)

    def test_shape_and_median(self):
        time_once, calls = self.fake([0.3, 0.1, 0.2])
        result = self.mod.probe(time_once=time_once)
        self.assertEqual(len(calls), 3)
        self.assertEqual(set(result), {"tags", "measured"})
        self.assertAlmostEqual(result["measured"]["compile_s_median"], 0.2)

    def test_tag_when_under_threshold(self):
        time_once, _ = self.fake([0.3, 0.1, 0.2])
        self.assertEqual(self.mod.probe(time_once=time_once)["tags"], ["fast_compile"])

    def test_no_tag_when_over_threshold(self):
        time_once, _ = self.fake([0.3, 0.3, 0.1])
        self.assertEqual(self.mod.probe(time_once=time_once)["tags"], [])

    def test_threshold_is_strict(self):
        time_once, _ = self.fake([0.25, 0.25, 0.25])
        self.assertEqual(self.mod.probe(time_once=time_once)["tags"], [])

    def test_runs_and_threshold_arguments(self):
        time_once, calls = self.fake([0.9, 0.8, 0.7, 0.6, 0.5])
        result = self.mod.probe(runs=5, threshold_s=1.0, time_once=time_once)
        self.assertEqual(len(calls), 5)
        self.assertAlmostEqual(result["measured"]["compile_s_median"], 0.7)
        self.assertEqual(result["tags"], ["fast_compile"])

    def test_real_timing(self):
        # One real run: compiles the json package REPEATS times, writes nothing to the repo.
        before = set(p for p in ROOT.rglob("*") if ".git" not in p.parts)
        result = self.mod.probe(runs=1)
        median = result["measured"]["compile_s_median"]
        self.assertIsInstance(median, float)
        self.assertGreater(median, 0)
        self.assertLess(median, 30)
        after = set(p for p in ROOT.rglob("*") if ".git" not in p.parts)
        self.assertEqual({p for p in after - before if "__pycache__" not in p.parts}, set())


@unittest.skipUnless(PROBE.exists(), "T-001 not done yet: cli/probes/compile.py doesn't exist")
class TestSurveyMerge(unittest.TestCase):
    def setUp(self):
        import crowd
        self.crowd = crowd

    def test_adds_tag_once_and_keeps_others(self):
        card = {"tags": ["low_spec", "fast_compile"], "measured": {"result_reliability": 0.9}}
        out = self.crowd.merge_probe(card, {"tags": ["fast_compile"], "measured": {"compile_s_median": 0.1}})
        self.assertEqual(out["tags"].count("fast_compile"), 1)
        self.assertIn("low_spec", out["tags"])
        self.assertEqual(out["measured"], {"result_reliability": 0.9, "compile_s_median": 0.1})

    def test_drops_stale_tag(self):
        # Measured over declared: a slower re-survey removes the tag.
        card = {"tags": ["low_spec", "fast_compile"], "measured": {}}
        out = self.crowd.merge_probe(card, {"tags": [], "measured": {"compile_s_median": 0.4}})
        self.assertEqual(out["tags"], ["low_spec"])

    def test_empty_card(self):
        out = self.crowd.merge_probe({}, {"tags": ["fast_compile"], "measured": {"compile_s_median": 0.1}})
        self.assertEqual(out["tags"], ["fast_compile"])
        self.assertEqual(out["measured"]["compile_s_median"], 0.1)


if __name__ == "__main__":
    unittest.main()
