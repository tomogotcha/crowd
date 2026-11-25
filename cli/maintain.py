"""The maintainer's brain: watcher items -> proposed actions (docs/maintainer.md, D-15).

decide() is pure: no GitHub, no clock, no files, inputs untouched. It proposes;
the rung (checked later, by T-007 and on) decides what actually runs.
"""

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
