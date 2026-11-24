#!/usr/bin/env python3
"""Scope gate: a PR may only touch the paths its task allows.

Used by CI (.github/workflows/gate.yml) and locally by `crowd check`.
Protected file: changes need human review.

Where the task comes from, in order:
  1. .crowd/tasks/T-<id>.yaml on the BASE branch (a PR can't rewrite its own scope)
  2. the task issue's yaml block, if the issue was written by a maintainer

Hardware checks: a task with `hardware` in acceptance.must_pass needs a
`RESULT: pass` comment on the PR for the exact head commit, from someone
other than the author with tier >= 2.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

DEFAULT_PROTECTED = [".github/", "PRINCIPLES.md", "cli/gate/", ".crowd/policy/", ".crowd/config.yaml"]
TASK_LABEL = "crowd:task"

# v0 stand-in for reputation tiers: GitHub's own record of who someone is to the repo.
TIERS = {"OWNER": 3, "MEMBER": 3, "COLLABORATOR": 3, "CONTRIBUTOR": 2}
MAINTAINER_TIER = 3
VERIFIER_TIER = 2


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def gh_lines(path):
    """GET a paginated list endpoint. Returns a list of objects."""
    out = gh("api", "--paginate", path, "--jq", ".[]")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def tier_of(association):
    return TIERS.get((association or "").upper(), 1)


def task_id_from(text):
    m = re.search(r"\bT-(\d+)\b", text or "")
    return f"T-{m.group(1)}" if m else None


def path_matches(path, pattern):
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or fnmatch.fnmatch(path, pattern)


def protected_paths(config=None):
    """The built-in list plus the project's. A project can add, never remove."""
    extra = (config or {}).get("protected_paths") or []
    return sorted(set(DEFAULT_PROTECTED) | set(extra))


def needs_hardware(task):
    return "hardware" in ((task.get("acceptance") or {}).get("must_pass") or [])


def policy_problems(changed, sizes, policy):
    """Project content rules from config `policy`: forbidden globs and a file size cap.

    Catches the common leak: an agent with private data on its machine
    (game dumps, datasets, keys) committing it or something derived from it.
    The project's own policy command (commands.policy) runs as well.
    """
    policy = policy or {}
    problems = []
    for path in changed:
        for pattern in policy.get("forbid") or []:
            if path_matches(path, pattern):
                problems.append(f"forbidden by project policy ({pattern}): {path}")
                break
        cap = policy.get("max_file_kb")
        size = (sizes or {}).get(path)
        if cap and size and size > cap * 1024:
            problems.append(f"file is {size // 1024} KB, project limit is {cap} KB: {path}")
    return problems


def check(task, changed, diff_lines, protected=None, hardware_ok=None, policy=None, sizes=None):
    """Return a list of problems. Empty list = pass.

    hardware_ok: None = don't check (local runs), True/False = result of the lookup.
    """
    protected = protected or DEFAULT_PROTECTED
    problems = policy_problems(changed, sizes, policy)
    allow = (task.get("scope") or {}).get("allow") or []
    if not allow:
        problems.append("task has an empty scope.allow")
    for path in changed:
        if not any(path_matches(path, p) for p in allow):
            problems.append(f"out of scope: {path}")
        if not task.get("protected") and any(path_matches(path, p) for p in protected):
            problems.append(f"protected path (needs a protected task + human review): {path}")
    limit = (task.get("acceptance") or {}).get("max_diff_lines")
    if limit and diff_lines > limit:
        problems.append(f"diff is {diff_lines} lines, limit is {limit}")
    if needs_hardware(task) and hardware_ok is False:
        problems.append("needs a hardware result for this commit: a matched machine runs "
                        "`crowd verify <pr>` (not the author, tier >= 2)")
    return problems


# ---------- config and tasks ----------

def load_config_at(rev):
    import yaml  # pip install pyyaml
    try:
        return yaml.safe_load(git("show", f"{rev}:.crowd/config.yaml")) or {}
    except subprocess.CalledProcessError:
        return {}


def task_from_body(body):
    """First ```yaml block in an issue body that has a scope. None if there isn't one."""
    import yaml
    for block in re.findall(r"```ya?ml\s*\n(.*?)```", body or "", flags=re.S):
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and "scope" in data:
            return data
    return None


def task_issues(repo, state="all"):
    items = gh_lines(f"repos/{repo}/issues?labels={TASK_LABEL}&state={state}&per_page=100")
    return [i for i in items if "pull_request" not in i]


def find_task_issue(repo, task_id, state="all"):
    for issue in task_issues(repo, state):
        if task_id_from(issue["title"]) == task_id:
            return issue
    return None


def load_task(task_id, base, repo=None):
    """Return (task, source). Raises LookupError with a plain reason."""
    import yaml
    try:
        return yaml.safe_load(git("show", f"{base}:.crowd/tasks/{task_id}.yaml")), "base branch"
    except subprocess.CalledProcessError:
        pass
    if not repo:
        raise LookupError(f"no .crowd/tasks/{task_id}.yaml on the base branch")
    try:
        issue = find_task_issue(repo, task_id)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise LookupError(f"no task file on the base branch, and the issue lookup failed: {e}")
    if not issue:
        raise LookupError(f"no task file on the base branch and no '{TASK_LABEL}' issue for {task_id}")
    if tier_of(issue.get("author_association")) < MAINTAINER_TIER:
        # The author can edit the body at any time, so only maintainers' issues count.
        raise LookupError(f"issue #{issue['number']} was not written by a maintainer; "
                          f"commit .crowd/tasks/{task_id}.yaml to the base branch instead")
    task = task_from_body(issue.get("body"))
    if not task:
        raise LookupError(f"issue #{issue['number']} has no yaml task block with a scope")
    return task, f"issue #{issue['number']}"


def load_task_at(rev, task_id):
    return load_task(task_id, rev)[0]


# ---------- hardware results ----------

def parse_result(body):
    """'RESULT: pass\\ncommit: <sha>' -> ('pass', '<sha>'). None if it isn't a result."""
    m = re.match(r"\s*RESULT:\s*(pass|fail)\b", body or "", flags=re.I)
    if not m:
        return None
    c = re.search(r"^commit:\s*([0-9a-f]{7,40})\s*$", body, flags=re.M | re.I)
    return m.group(1).lower(), (c.group(1).lower() if c else None)


def hardware_verdict(comments, head_sha, author):
    """Latest eligible result for this exact commit. True, False, or None (no result yet)."""
    verdict = None
    for c in comments:
        parsed = parse_result(c.get("body"))
        if not parsed or not parsed[1] or not head_sha.lower().startswith(parsed[1]):
            continue
        login = (c.get("user") or {}).get("login")
        if login == author or tier_of(c.get("author_association")) < VERIFIER_TIER:
            continue
        verdict = parsed[0] == "pass"
    return verdict


def hardware_ok(repo, pr_number, head_sha):
    pr = json.loads(gh("api", f"repos/{repo}/pulls/{pr_number}"))
    comments = gh_lines(f"repos/{repo}/issues/{pr_number}/comments?per_page=100")
    return bool(hardware_verdict(comments, head_sha, pr["user"]["login"]))


# ---------- diff ----------

def changed_files(base, head):
    out = git("diff", "--name-only", f"{base}...{head}")
    return [line for line in out.splitlines() if line]


def file_sizes(head, paths):
    """Size in bytes of each path at `head`. Deleted files are left out."""
    sizes = {}
    for path in paths:
        r = subprocess.run(["git", "cat-file", "-s", f"{head}:{path}"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            sizes[path] = int(r.stdout.strip())
    return sizes


def diff_size(base, head):
    total = 0
    for line in git("diff", "--numstat", f"{base}...{head}").splitlines():
        added, removed, _ = line.split("\t", 2)
        if added.isdigit() and removed.isdigit():
            total += int(added) + int(removed)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="", help="PR head branch, e.g. crowd/T-142")
    ap.add_argument("--title", default="")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--pr", default=os.environ.get("PR_NUMBER"))
    ap.add_argument("--head-sha", default=os.environ.get("HEAD_SHA"))
    a = ap.parse_args()

    task_id = task_id_from(a.ref) or task_id_from(a.title)
    if not task_id:
        print("FAIL: no task id. Branch must be crowd/T-<id>, or the PR title must start 'T-<id>: ...'")
        return 1
    try:
        task, source = load_task(task_id, a.base, a.repo)
    except LookupError as e:
        print(f"FAIL {task_id}: {e}")
        return 1

    hw = None
    if needs_hardware(task):
        hw = False
        if a.repo and a.pr and a.head_sha:
            try:
                hw = hardware_ok(a.repo, a.pr, a.head_sha)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"note: hardware result lookup failed: {e}")

    config = load_config_at(a.base)
    changed = changed_files(a.base, a.head)
    problems = check(task, changed, diff_size(a.base, a.head), protected_paths(config), hw,
                     config.get("policy"), file_sizes(a.head, changed))
    if problems:
        print(f"FAIL {task_id} (task from {source}):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"PASS {task_id}: scope ok (task from {source})"
          + (", hardware result found" if hw else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
