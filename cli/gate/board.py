#!/usr/bin/env python3
"""Board: turns typed comments into task status. The only writer of labels.

Volunteers working from forks can comment but can't edit labels or assignees.
So the CLI only posts typed comments, and this script (run by
.github/workflows/board.yml with the repo's own token) applies them:

  /claim        on a task issue  -> assign + status:leased, or LEASE DENIED
  /release      on a task issue  -> unassign + status:open
  QUESTION: / OBJECTION:         -> status:blocked
  PR opened from crowd/T-<id>    -> status:in_review
  that PR merged                 -> status:done
  that PR closed unmerged        -> status:leased (lease still held) or status:open
  RESULT: pass|fail on a PR      -> re-run the gate, which reads the result

Leases are decided from the comment history in order, never from who the
script happened to see first. The log is the source of truth.
Protected file: changes need human review.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_check  # noqa: E402
from scope_check import gh, gh_lines, task_id_from, tier_of  # noqa: E402

STATUS = "status:"
GATE_WORKFLOW = "crowd gate"


# ---------- decisions (pure, covered by `crowd selftest`) ----------

def lease_holders(comments, min_tier):
    """Logins holding a lease, in claim order."""
    holders = []
    for c in comments:
        body = (c.get("body") or "").strip()
        login = (c.get("user") or {}).get("login")
        if body.startswith("/claim"):
            if login not in holders and tier_of(c.get("author_association")) >= min_tier:
                holders.append(login)
        elif body.startswith("/release") and login in holders:
            holders.remove(login)
    return holders


def decide_claim(task, comments, login, association):
    """Return (granted, reason, new_status)."""
    min_tier = int(task.get("tier") or 1)
    slots = int(task.get("redundancy") or 1)
    if tier_of(association) < min_tier:
        return False, f"this task needs tier {min_tier}; you are tier {tier_of(association)}", None
    winners = lease_holders(comments, min_tier)[:slots]
    if login not in winners:
        return False, f"all {slots} lease(s) are taken ({', '.join(winners)})", None
    return True, "", "leased" if len(winners) >= slots else "open"


def decide_result(body, head_sha, commenter, association, author):
    """Return (accepted, reason) for a RESULT comment on a PR."""
    parsed = scope_check.parse_result(body)
    if not parsed:
        return False, "not a result"
    if not parsed[1]:
        return False, "add a line `commit: <sha>` so the result is tied to what you ran"
    if not head_sha.lower().startswith(parsed[1]):
        return False, f"that commit is not the PR head ({head_sha[:9]}); run the latest and post again"
    if commenter == author:
        return False, "the author can't verify their own PR"
    if tier_of(association) < scope_check.VERIFIER_TIER:
        return False, f"hardware results need tier {scope_check.VERIFIER_TIER}"
    return True, ""


# ---------- GitHub writes ----------

def ensure_label(repo, name):
    subprocess.run(["gh", "label", "create", name, "-R", repo, "--force"], capture_output=True, text=True)


def set_status(repo, number, new, labels):
    ensure_label(repo, STATUS + new)
    args = ["issue", "edit", str(number), "-R", repo, "--add-label", STATUS + new]
    for label in labels:
        name = label["name"] if isinstance(label, dict) else label
        if name.startswith(STATUS) and name != STATUS + new:
            args += ["--remove-label", name]
    gh(*args)


def say(repo, number, body):
    gh("issue", "comment", str(number), "-R", repo, "--body", body)


def rerun_gate(repo, sha):
    try:
        out = gh("run", "list", "-R", repo, "--workflow", GATE_WORKFLOW, "--commit", sha,
                 "--json", "databaseId", "--limit", "1")
        runs = json.loads(out or "[]")
        if runs:
            gh("run", "rerun", str(runs[0]["databaseId"]), "-R", repo)
            return True
    except subprocess.CalledProcessError:
        pass
    return False


# ---------- events ----------

def on_task_comment(repo, issue, comment):
    body = (comment.get("body") or "").strip()
    login = comment["user"]["login"]
    number = issue["number"]
    tid = task_id_from(issue["title"])
    if not tid:
        return
    if body.startswith("/claim"):
        try:
            task, _ = scope_check.load_task(tid, "HEAD", repo)
        except LookupError as e:
            say(repo, number, f"LEASE DENIED: @{login} {e}")
            return
        comments = gh_lines(f"repos/{repo}/issues/{number}/comments?per_page=100")
        granted, reason, status = decide_claim(task, comments, login, comment.get("author_association"))
        if not granted:
            say(repo, number, f"LEASE DENIED: @{login} {reason}")
            return
        gh("issue", "edit", str(number), "-R", repo, "--add-assignee", login)
        set_status(repo, number, status, issue["labels"])
        print(f"lease granted to {login} on {tid}, status:{status}")
    elif body.startswith("/release"):
        gh("issue", "edit", str(number), "-R", repo, "--remove-assignee", login)
        set_status(repo, number, "open", issue["labels"])
    elif body.startswith(("QUESTION:", "OBJECTION:")):
        if login in [a["login"] for a in issue.get("assignees") or []]:
            set_status(repo, number, "blocked", issue["labels"])


def on_pr_comment(repo, issue, comment):
    if not scope_check.parse_result(comment.get("body")):
        return
    pr = json.loads(gh("api", f"repos/{repo}/pulls/{issue['number']}"))
    if not pr["head"]["ref"].startswith("crowd/T-"):
        return
    login = comment["user"]["login"]
    ok, reason = decide_result(comment.get("body"), pr["head"]["sha"], login,
                               comment.get("author_association"), pr["user"]["login"])
    if not ok:
        say(repo, issue["number"], f"RESULT IGNORED: @{login} {reason}")
        return
    if not rerun_gate(repo, pr["head"]["sha"]):
        say(repo, issue["number"], "Result recorded. Couldn't re-run the gate automatically; re-run it by hand.")


def status_after_pr(action, merged, assigned):
    """Task status for a crowd PR event. None = leave it alone."""
    if action in ("opened", "reopened"):
        return "in_review"
    if action == "closed":
        if merged:
            return "done"
        return "leased" if assigned else "open"
    return None


def on_pr_event(repo, pr, action):
    tid = task_id_from(pr["head"]["ref"])
    # "all": a merge with "closes #N" may have closed the issue already.
    issue = scope_check.find_task_issue(repo, tid, "all") if tid else None
    if not issue:
        return
    new = status_after_pr(action, pr.get("merged"), bool(issue.get("assignees")))
    if new:
        set_status(repo, issue["number"], new, issue["labels"])
        print(f"{tid}: PR #{pr['number']} {action} -> status:{new}")


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    name = os.environ.get("GITHUB_EVENT_NAME")
    if name == "issue_comment":
        issue, comment = event["issue"], event["comment"]
        if "pull_request" in issue:
            on_pr_comment(repo, issue, comment)
        elif any(label["name"] == scope_check.TASK_LABEL for label in issue.get("labels") or []):
            on_task_comment(repo, issue, comment)
    elif name == "pull_request_target":
        on_pr_event(repo, event["pull_request"], event.get("action"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
