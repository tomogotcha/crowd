"""crowd watch: a small, read-only watcher for a crowd repo.

Every poll it reads the board (issues, PRs, CI runs) and the local checkout,
and boils them down to a list of things that need someone: a report nobody
has triaged, a lease gone quiet, a red gate, a PR on protected paths.

It writes nothing to GitHub. Its only output is the terminal, an optional
desktop notification, and an append-only local log (.crowd/work/watch.jsonl,
gitignored) of items raised and cleared. That log is what the maintainer
reads (docs/maintainer.md): the watcher is its eyes, never its hands.

Run it through the CLI: `crowd watch [--once] [--every 60] [--notify]`.
"""
import datetime as dt
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "gate"))
import scope_check  # noqa: E402

FEEDBACK_LABEL = "crowd:feedback"
STATUS = "status:"
BAD = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR"}
# Who should look. The maintainer design uses the same split.
HUMAN, MAINTAINER, AUTHOR = "human", "maintainer", "author"


# ---------- decisions (pure, covered by tests/test_watch.py) ----------

def parse_time(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def label_names(obj):
    return [label["name"] for label in obj.get("labels") or []]


def status_of(labels):
    for name in labels:
        if name.startswith(STATUS):
            return name[len(STATUS):]
    return None


def checks_state(rollup):
    """'fail', 'pending', 'pass' or 'none' for a PR's check rollup."""
    states = [(c.get("conclusion") or c.get("state") or c.get("status") or "").upper() for c in rollup or []]
    if not states:
        return "none"
    if any(s in BAD for s in states):
        return "fail"
    if all(s in ("SUCCESS", "NEUTRAL", "SKIPPED") for s in states):
        return "pass"
    return "pending"   # anything unfinished or unknown is not a pass


def item(key, who, text, url=""):
    return {"key": key, "who": who, "text": text, "url": url}


def attention(snap, config, now):
    """Everything in the snapshot that needs someone, keyed so polls can be compared."""
    out = []
    ttl = dt.timedelta(hours=float(config.get("lease_ttl_hours") or 24))
    protected = scope_check.protected_paths(config)
    # Issues an open PR will close ("Closes #N"). Someone is already on them,
    # so they aren't raised again; this is how a drafted report stops being
    # drafted twice. If that PR closes unmerged, the issue comes back.
    handled = {ref.get("number") for p in snap.get("prs") or []
               for ref in p.get("closingIssuesReferences") or []}

    for i in snap.get("issues") or []:
        n, labels, url = i["number"], label_names(i), i.get("url", "")
        if scope_check.TASK_LABEL in labels:
            tid = scope_check.task_id_from(i["title"]) or f"#{n}"
            status = status_of(labels)
            idle = now - parse_time(i["updatedAt"])
            if status == "blocked":
                out.append(item(f"blocked:{tid}", HUMAN, f"{tid} is blocked on a question", url))
            elif status == "leased" and idle > ttl:
                hours = int(idle.total_seconds() // 3600)
                out.append(item(f"stale-lease:{tid}", MAINTAINER,
                                f"{tid} lease has been quiet for {hours}h (limit {int(ttl.total_seconds() // 3600)}h)", url))
            elif status is None:
                out.append(item(f"no-status:{tid}", MAINTAINER, f"{tid} has no status label", url))
        elif n in handled:
            continue
        elif FEEDBACK_LABEL in labels:
            out.append(item(f"feedback:{n}", MAINTAINER, f"report #{n} not triaged: {i['title'][:70]}", url))
        else:
            out.append(item(f"issue:{n}", HUMAN, f"issue #{n} is not a task yet: {i['title'][:70]}", url))

    for p in snap.get("prs") or []:
        n, url = p["number"], p.get("url", "")
        files = [f["path"] for f in p.get("files") or []]
        touched = sorted({pat for f in files for pat in protected if scope_check.path_matches(f, pat)})
        state = checks_state(p.get("statusCheckRollup"))
        if touched:
            out.append(item(f"pr-protected:{n}", HUMAN,
                            f"PR #{n} touches protected paths ({', '.join(touched)}): human review", url))
        if state == "fail":
            out.append(item(f"pr-red:{n}", AUTHOR, f"PR #{n} has failing checks: {p['title'][:60]}", url))
        elif state in ("pass", "none") and not p.get("isDraft") and not touched:
            out.append(item(f"pr-ready:{n}", MAINTAINER, f"PR #{n} is green and waiting: {p['title'][:60]}", url))

    seen = set()
    for r in snap.get("runs") or []:   # newest first; only the latest finished run of each workflow counts
        name = r.get("workflowName")
        if name in seen or (r.get("status") or "").lower() != "completed":
            continue
        seen.add(name)
        if (r.get("conclusion") or "").upper() in BAD:
            out.append(item(f"main-red:{name}", HUMAN, f"'{name}' is failing on the default branch", r.get("url", "")))

    local = snap.get("local") or {}
    if local.get("behind"):
        out.append(item("local-behind", HUMAN, f"your {local['branch']} is behind the repo; pull before you work"))
    if local.get("ahead"):
        out.append(item("local-ahead", HUMAN, f"your {local['branch']} has commits that aren't pushed"))
    return out


def diff(old, new):
    """(raised, cleared) between two attention lists."""
    before, after = {i["key"]: i for i in old}, {i["key"]: i for i in new}
    return ([after[k] for k in after if k not in before],
            [before[k] for k in before if k not in after])


# ---------- reading (the only I/O; all read-only) ----------

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def gh_json(*args):
    out = sh("gh", *args)
    if out is None:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed")
    return json.loads(out or "[]")


def local_state(repo, branch):
    remote = sh("gh", "api", f"repos/{repo}/branches/{branch}", "--jq", ".commit.sha")
    mine = sh("git", "rev-parse", "--verify", "-q", branch)
    if not remote or not mine or remote == mine:
        return {"branch": branch}
    known = sh("git", "cat-file", "-e", f"{remote}^{{commit}}") is not None
    ahead = known and sh("git", "merge-base", "--is-ancestor", remote, mine) is not None
    return {"branch": branch, "behind": not ahead, "ahead": ahead}


def snapshot(repo):
    branch = sh("gh", "repo", "view", repo, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name") or "main"
    return {
        "issues": gh_json("issue", "list", "-R", repo, "--state", "open", "--limit", "200",
                          "--json", "number,title,labels,assignees,updatedAt,url"),
        "prs": gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "100",
                       "--json", "number,title,headRefName,isDraft,statusCheckRollup,files,closingIssuesReferences,url"),
        "runs": gh_json("run", "list", "-R", repo, "--branch", branch, "--limit", "30",
                        "--json", "workflowName,status,conclusion,url"),
        "local": local_state(repo, branch),
    }


# ---------- output ----------

def stamp():
    return dt.datetime.now().strftime("%H:%M:%S")


def line(mark, it):
    return f"  {mark} [{it['who']}] {it['text']}" + (f"\n      {it['url']}" if it["url"] else "")


def notify(title, text):
    if platform.system() == "Darwin":
        subprocess.run(["osascript", "-e", "on run argv", "-e",
                        "display notification (item 2 of argv) with title (item 1 of argv)",
                        "-e", "end run", title, text], capture_output=True)


def record(log, repo, kind, items):
    if not items:
        return
    log.parent.mkdir(parents=True, exist_ok=True)
    at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with log.open("a") as f:
        for it in items:
            f.write(json.dumps({"at": at, "actor": "watch", "repo": repo, "type": kind, "body": it}) + "\n")


def watch(repo, config, root, every=60, once=False, desktop=False):
    log = Path(root) / ".crowd" / "work" / "watch.jsonl"
    last, first = [], True
    print(f"watching {repo} (read-only){'' if once else f', every {every}s; ctrl-c to stop'}")
    while True:
        try:
            now_items = attention(snapshot(repo), config, dt.datetime.now(dt.timezone.utc))
        except (RuntimeError, json.JSONDecodeError) as e:
            print(f"{stamp()} couldn't read the repo ({e}); will retry")
            now_items = None
        if now_items is not None:
            raised, cleared = diff(last, now_items)
            if first:
                print(f"{stamp()} {len(now_items)} thing(s) need someone" if now_items else f"{stamp()} all quiet")
                for it in now_items:
                    print(line("•", it))
            else:
                for it in raised:
                    print(f"{stamp()} new\n{line('+', it)}")
                    if desktop:
                        notify(f"crowd: {repo}", it["text"])
                for it in cleared:
                    print(f"{stamp()} cleared\n{line('-', it)}")
            record(log, repo, "raised", raised)
            record(log, repo, "cleared", cleared)
            last, first = now_items, False
        if once:
            return 0
        try:
            time.sleep(max(15, every))
        except KeyboardInterrupt:
            print()
            return 0
