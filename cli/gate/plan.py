#!/usr/bin/env python3
"""Gate plan: read the project's runners and commands from .crowd/config.yaml.

The gate itself knows nothing about the project's language or OS. This turns
the config into job outputs so the workflow can run the project's own
commands on the project's own runners.

Reads the config from the BASE commit when it exists there (so a PR can't
swap the commands), else from the working tree (the bootstrap PR).
Protected file: changes need human review.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

STEPS = ["setup", "policy", "build", "lint", "test", "hardware"]  # hardware: run by `crowd verify`, not CI
DEFAULT_RUNNERS = ["ubuntu-latest"]


def load_config(base):
    import yaml  # pip install pyyaml
    if base:
        r = subprocess.run(["git", "show", f"{base}:.crowd/config.yaml"], capture_output=True, text=True)
        if r.returncode == 0:
            return yaml.safe_load(r.stdout) or {}, "base commit"
    path = Path(".crowd/config.yaml")
    if path.exists():
        return yaml.safe_load(path.read_text()) or {}, "working tree"
    return {}, "defaults"


def plan(config):
    """Config -> {runners: json list, setup/policy/build/lint/test: command or ''}."""
    runners = (config.get("ci") or {}).get("runners") or DEFAULT_RUNNERS
    if isinstance(runners, str):
        runners = [runners]
    commands = config.get("commands") or {}
    out = {"runners": json.dumps(runners)}
    for name in STEPS:
        out[name] = " ".join(str(commands.get(name) or "").split())  # one line
    return out


def main():
    config, source = load_config(os.environ.get("BASE_SHA"))
    result = plan(config)
    print(f"config from {source}")
    for key, value in result.items():
        print(f"  {key}: {value or '(none)'}")
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as f:
            for key, value in result.items():
                f.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
