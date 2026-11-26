"""The maintainer's brain: watcher items -> proposed actions (docs/maintainer.md, D-15).

decide() is pure: no GitHub, no clock, no files, inputs untouched. It proposes;
the rung (checked later, by T-007 and on) decides what actually runs.

Rung 1 (T-007): dry_run() reads the policy and the board, calls decide(), and
prints the plan. It writes nothing. load_policy, pr_facts and render are pure.
"""
import datetime as dt
import re
import subprocess

MAINTAINER = "maintainer"   # same tag as watch.MAINTAINER

RUNG = {"draft-task": 2, "escalate": 2, "expire-lease": 2,
        "resync": 2, "request-review": 2, "merge": 3}


def _norm(s):
    return s.strip().lower() if isinstance(s, str) and s.strip() else None


def _lookup(mapping, n):
    """Facts may key numbers as int or str; try both. Anything odd -> None."""
    if not isinstance(mapping, dict):
        return None
    if n in mapping:
        return mapping[n]
    try:
        return mapping.get(int(n))
    except (TypeError, ValueError):
        return None


def _in(collection, n):
    try:
        return n in collection or (n.isdigit() and int(n) in collection)
    except TypeError:
        return False


def merge_refusal(n, policy, facts, protected):
    """None if PR #n may be merged, else a plain reason why not."""
    if n in protected:
        return "it touches a protected path, so a human reviews it"
    me = _norm(policy.get("login"))
    if not me:
        return "the policy has no maintainer login, so it can't rule out its own PR"
    pr = _lookup(facts.get("prs") or {}, n)
    if not isinstance(pr, dict):
        return "nothing is known about this PR yet"
    author, model = _norm(pr.get("author")), _norm(pr.get("author_model"))
    if not author or author == me:
        return "the maintainer never merges its own PR (or the author is unknown)"
    if not model:
        return "the author's model is unknown"
    for ap in pr.get("approvals") or []:
        if not isinstance(ap, dict):
            continue
        by, by_model = _norm(ap.get("by")), _norm(ap.get("model"))
        if by and by not in (author, me) and by_model and by_model != model:
            return None
    return "it needs an approval from someone else using a different model"


def decide(items, policy, facts):
    """Watcher items -> [{"kind", "target", "rung", "why"}], in item order. See docs/maintainer.md."""
    policy, facts = policy or {}, facts or {}
    if policy.get("enabled") is not True:
        return []
    ours, protected = [], set()
    for it in items or []:
        kind, _, arg = str(it.get("key", "")).partition(":")
        if kind == "pr-protected":
            protected.add(arg)          # counts whoever it's tagged for
        elif it.get("who") == MAINTAINER and arg:
            ours.append((kind, arg, it.get("text") or it.get("key")))

    out = []
    for kind, arg, text in ours:
        if kind == "feedback":
            closed = _in(facts.get("closed_drafts") or (), arg)
            action, target = ("escalate" if closed else "draft-task"), f"#{arg}"
            why = f"a human closed the last draft for #{arg}; {text}" if closed else text
        elif kind == "stale-lease":
            action, target, why = "expire-lease", arg, text
        elif kind == "no-status":
            action, target, why = "resync", arg, text
        elif kind == "pr-ready":
            refusal = merge_refusal(arg, policy, facts, protected)
            action, target = ("request-review" if refusal else "merge"), f"#{arg}"
            why = f"Not merging: {refusal}." if refusal else text
        else:
            continue                    # not on the fixed list (D-02)
        out.append({"kind": action, "target": target, "rung": RUNG[action], "why": why})
    return out


# ---------- rung 1: --dry-run (T-007) ----------

POLICY_PATH = ".crowd/policy/maintainer.yaml"
ENABLED_LINE = re.compile(r"(?m)^enabled:[ \t]*true[ \t]*(#.*)?$")
MODEL_LINE = re.compile(r"(?m)^[ \t]*Model:[ \t]*(\S[^\r\n]*?)[ \t]*$")


def load_policy(text):
    """yaml text -> {"enabled", "rung", "login", "max_actions_per_day"}. Anything odd -> paused."""
    import yaml  # pip install pyyaml; a missing module is an error, not a pause
    out = {"enabled": False, "rung": 0, "login": "", "max_actions_per_day": 20}
    try:
        data = yaml.safe_load(text or "")
    except yaml.YAMLError:
        return out
    if not isinstance(data, dict):
        return out
    # Exactly `true`: YAML 1.1 would also read yes/on/True as true; those stay paused.
    out["enabled"] = data.get("enabled") is True and bool(ENABLED_LINE.search(text))
    rung = data.get("rung")
    if type(rung) is int and 0 <= rung <= 3:
        out["rung"] = rung
    if isinstance(data.get("login"), str):
        out["login"] = data["login"]
    cap = data.get("max_actions_per_day")
    if type(cap) is int and cap >= 0:
        out["max_actions_per_day"] = cap
    return out


def _login(obj):
    return obj.get("login") or None if isinstance(obj, dict) else None


def _model(body):
    m = MODEL_LINE.search(body) if isinstance(body, str) else None
    return m.group(1) if m else None


def pr_facts(pr):
    """`gh pr view N --json author,body,reviews` -> {"author", "author_model", "approvals"}."""
    pr = pr if isinstance(pr, dict) else {}
    latest = {}                     # reviewer -> latest review; keeps first-review order
    for r in pr.get("reviews") or []:
        by = _login(r.get("author")) if isinstance(r, dict) else None
        if by:
            latest[by] = r
    return {"author": _login(pr.get("author")), "author_model": _model(pr.get("body")),
            "approvals": [{"by": by, "model": _model(r.get("body"))}
                          for by, r in latest.items() if r.get("state") == "APPROVED"]}


def render(actions, rung):
    """One line per action; marks the ones above the policy's rung."""
    lines = []
    for a in actions or []:
        line = f"would {a['kind']} {a['target']}: {a['why']}"
        if a["rung"] > rung:
            line += f"  (needs rung {a['rung']}; now {rung})"
        lines.append(line)
    return lines or ["nothing to do"]


def dry_run(repo, config):
    """Read-only: the policy on the default branch, the watcher's list, PR facts; print the plan."""
    import watch                    # cli/ is on sys.path when run through crowd.py
    r = subprocess.run(["gh", "api", f"repos/{repo}/contents/{POLICY_PATH}",
                        "-H", "Accept: application/vnd.github.raw"], capture_output=True, text=True)
    policy = load_policy(r.stdout if r.returncode == 0 else "")
    items = watch.attention(watch.snapshot(repo), config, dt.datetime.now(dt.timezone.utc))
    prs = {}
    for it in items:
        kind, _, n = str(it.get("key", "")).partition(":")
        if kind == "pr-ready" and n:
            prs[n] = pr_facts(watch.gh_json("pr", "view", n, "-R", repo, "--json", "author,body,reviews"))
    print(f"crowd maintain --dry-run: {repo}, rung {policy['rung']} (read-only; writes nothing)")
    if not policy["enabled"]:
        print("paused")
        return 0
    for line in render(decide(items, policy, {"prs": prs, "closed_drafts": set()}), policy["rung"]):
        print(line)
    return 0
