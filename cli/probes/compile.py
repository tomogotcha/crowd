"""fast_compile probe: how quickly this machine byte-compiles a small, fixed workload.

One run compiles every .py file of the stdlib `json` package REPEATS times,
in-process, into a temporary directory. The median of RUNS runs is stored;
the card gets the `fast_compile` tag when it is strictly under THRESHOLD_S.
Nothing is written inside the repo.
"""
import json
import os
import py_compile
import statistics
import tempfile
import time

THRESHOLD_S = 0.25  # about twice a 2020 desktop i7
RUNS = 3
REPEATS = 20


def _json_sources():
    pkg = os.path.dirname(json.__file__)
    return [os.path.join(pkg, name) for name in sorted(os.listdir(pkg)) if name.endswith(".py")]


def _time_once():
    sources = _json_sources()
    with tempfile.TemporaryDirectory() as out:
        start = time.perf_counter()
        for r in range(REPEATS):
            for i, src in enumerate(sources):
                py_compile.compile(src, cfile=os.path.join(out, f"{r}-{i}.pyc"), doraise=True)
        return time.perf_counter() - start


def probe(runs=RUNS, threshold_s=THRESHOLD_S, time_once=None):
    """{"tags": ["fast_compile"] or [], "measured": {"compile_s_median": float}}"""
    time_once = time_once or _time_once
    median = float(statistics.median(time_once() for _ in range(runs)))
    return {
        "tags": ["fast_compile"] if median < threshold_s else [],
        "measured": {"compile_s_median": median},
    }
