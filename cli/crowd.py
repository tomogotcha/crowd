#!/usr/bin/env python3
"""crowd v0: a thin CLI over git + the GitHub CLI (gh).

Issues are tasks, labels are status, branches are leases, issue comments
are checkpoints and messages. See AGENTS.md and docs/architecture.md.

The CLI only posts typed comments. The board workflow (cli/gate/board.py)
turns them into labels and assignees, so volunteers working from forks,
with no write access, can take part.

  crowd ready <owner/repo>     read-only intake report; writes nothing anywhere
  crowd survey                 build your machine card (shown before anything is sent)
  crowd claim [T-id]           lease a matched open task, create its branch
  crowd checkpoint "done; learned; next"
  crowd ask "question" [--objection]
  crowd check                  scope gate + policy + tests, same as CI
  crowd submit                 push (to your fork if needed) and open the PR
  crowd verify <pr> [--dry-run]   run someone else's PR on this machine, post RESULT
  crowd feedback "text"        report a problem with crowd itself to crowd's repo (P13)
  crowd watch [--once]         read-only: list what on the board needs someone, and keep watching
  crowd pet                    see how your agent is doing
  crowd feed <tokens>          set today's token budget
  crowd eat <tokens>           log tokens used (until agents report it themselves)
  crowd selftest               run the CLI's own tests
"""
import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gate"))
import board  # noqa: E402
import plan as gate_plan  # noqa: E402
import scope_check  # noqa: E402
from probes import compile as compile_probe  # noqa: E402  (cli/ is on sys.path)
import watch as watcher  # noqa: E402

HOME = Path(os.environ.get("CROWD_HOME", Path.home() / ".crowd"))
CARD = HOME / "machine-card.json"
STATE = HOME / "state.json"
TASK_LABEL = scope_check.TASK_LABEL
WRITE_ROLES = {"ADMIN", "MAINTAIN", "WRITE"}
CROWD_VERSION = "0.1.0"
FEEDBACK_REPO = os.environ.get("CROWD_TOOL_REPO", "tomogotcha/crowd")  # crowd's own repo
FEEDBACK_LABEL = "crowd:feedback"
FEEDBACK_KINDS = ["friction", "bug", "idea"]


# ---------- helpers ----------

def run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"error: {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"error: '{tool}' not found. Install it first.")


def load(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def repo_root():
    return Path(run(["git", "rev-parse", "--show-toplevel"]))


def project_config():
    import yaml  # pip install pyyaml
    path = repo_root() / ".crowd" / "config.yaml"
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def upstream_repo():
    """The repo that holds the task board: CROWD_REPO, config `repo`, or the fork's parent."""
    if os.environ.get("CROWD_REPO"):
        return os.environ["CROWD_REPO"]
    repo = project_config().get("repo")
    if repo:
        return repo
    info = json.loads(run(["gh", "repo", "view", "--json", "nameWithOwner,parent"]))
    parent = info.get("parent")
    return f"{parent['owner']['login']}/{parent['name']}" if parent else info["nameWithOwner"]


def remote_for(repo):
    """Name of the git remote pointing at `repo`, adding `upstream` if there is none."""
    for line in run(["git", "remote", "-v"]).splitlines():
        name, url = line.split()[:2]
        if re.search(rf"[:/]{re.escape(repo)}(\.git)?$", url):
            return name
    run(["git", "remote", "add", "upstream", f"https://github.com/{repo}.git"])
    return "upstream"


def default_branch(repo):
    return run(["gh", "repo", "view", repo, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"])


def me():
    return run(["gh", "api", "user", "--jq", ".login"])


def current_task():
    branch = run(["git", "branch", "--show-current"])
    tid = scope_check.task_id_from(branch)
    if not tid:
        sys.exit("error: not on a task branch (expected crowd/T-<id>). Run `crowd claim` first.")
    return tid


def task_label(tid, title):
    """The id once, then the title. Drops only a leading copy of this tid (and any
    ":", "-" or spaces after it); "T-0010: x" is a different id and stays."""
    rest = re.sub(rf"^{re.escape(tid)}(?=$|[\s:\-])[\s:\-]*", "", title or "").strip()
    return f"{tid}: {rest}" if rest else tid


def find_issue(repo, task_id, state="open"):
    out = run(["gh", "issue", "list", "-R", repo, "--state", state, "--label", TASK_LABEL,
               "--search", f"{task_id} in:title", "--json", "number,title,labels,body", "--limit", "20"])
    for issue in json.loads(out or "[]"):
        if scope_check.task_id_from(issue["title"]) == task_id:
            return issue
    sys.exit(f"error: no issue found for {task_id} in {repo}")


def post(repo, number, body):
    """Comment and return the comment (with author_association)."""
    out = run(["gh", "api", f"repos/{repo}/issues/{number}/comments", "-f", f"body={body}"])
    return json.loads(out)


def task_for(task_id, base_ref=None, repo=None):
    try:
        return scope_check.load_task(task_id, base_ref or "HEAD", repo)[0]
    except LookupError as e:
        sys.exit(f"error: {e}")


def status_of(labels):
    for label in labels:
        name = label["name"] if isinstance(label, dict) else label
        if name.startswith("status:"):
            return name.split(":", 1)[1]
    return None


# ---------- matching ----------

def compare(have, want):
    """have=16, want='>=8' -> True. want may be a plain value (equality)."""
    if have is None:
        return False
    m = re.match(r"\s*(>=|<=|==|>|<)?\s*([\d.]+)\s*$", str(want))
    if not m:
        return str(have).lower() == str(want).lower()
    op, num = m.group(1) or "==", float(m.group(2))
    try:
        have = float(have)
    except (TypeError, ValueError):
        return False
    return {">=": have >= num, "<=": have <= num, ">": have > num, "<": have < num, "==": have == num}[op]


def one_of(have, want):
    wants = want if isinstance(want, list) else [want]
    return str(have).lower() in [str(w).lower() for w in wants]


def gpu_vram_gb(gpu):
    if gpu.get("vram_gb") is not None:
        return gpu["vram_gb"]
    m = re.search(r"([\d.]+)\s*GB", str(gpu.get("vram", "")), flags=re.I)
    return float(m.group(1)) if m else None


def unmet(requires, card):
    """What the machine card is missing for this task. Empty list = match."""
    requires = requires or {}
    machine, agent = card.get("machine") or {}, card.get("agent") or {}
    missing = []
    if "os" in requires and not one_of(machine.get("os"), requires["os"]):
        missing.append(f"os {requires['os']} (have {machine.get('os')})")
    if "arch" in requires and not one_of(machine.get("arch"), requires["arch"]):
        missing.append(f"arch {requires['arch']} (have {machine.get('arch')})")
    if "ram_gb" in requires and not compare(machine.get("ram_gb"), requires["ram_gb"]):
        missing.append(f"ram_gb {requires['ram_gb']} (have {machine.get('ram_gb')})")
    if "agent_tier" in requires and not compare(agent.get("tier", 1), requires["agent_tier"]):
        missing.append(f"agent_tier {requires['agent_tier']} (have {agent.get('tier', 1)})")
    want_gpu = requires.get("gpu")
    if want_gpu:
        ok = False
        for gpu in machine.get("gpu") or []:
            if "vendor" in want_gpu and not one_of(gpu.get("vendor"), want_gpu["vendor"]):
                continue
            if "vram_gb" in want_gpu and not compare(gpu_vram_gb(gpu), want_gpu["vram_gb"]):
                continue
            ok = True
        if not ok:
            missing.append(f"gpu {want_gpu}")
    for tag in requires.get("tags") or []:
        if tag not in (card.get("tags") or []):
            missing.append(f"tag {tag}")
    return missing


def fits(task, card):
    """Return (ok, why_not)."""
    types = (card.get("limits") or {}).get("task_types")
    if types and task.get("type") and task["type"] not in types:
        return False, f"type {task['type']} not in your task_types"
    missing = unmet(task.get("requires"), card)
    return (not missing), "; ".join(missing)


# ---------- ready (read-only intake) ----------

BUILD_FILES = {
    "Cargo.toml": {"build": "cargo build --workspace --locked", "lint": "cargo clippy --workspace --all-targets --locked -- -D warnings", "test": "cargo test --workspace --locked"},
    "package.json": {"setup": "npm ci", "build": "npm run build --if-present", "lint": "npm run lint --if-present", "test": "npm test"},
    "pyproject.toml": {"setup": "pip install -e .", "test": "python -m pytest"},
    "go.mod": {"build": "go build ./...", "lint": "go vet ./...", "test": "go test ./..."},
    "CMakeLists.txt": {"setup": "cmake -B build", "build": "cmake --build build", "test": "ctest --test-dir build"},
}
RULE_FILES = ["CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "AGENTS.md", "CLAUDE.md", "SECURITY.md",
              ".github/CODEOWNERS", "CODEOWNERS", ".githooks/", ".pre-commit-config.yaml"]
OPEN_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0", "ISC", "Unlicense",
                 "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0", "0BSD", "Zlib"}


def gh_get(path):
    """Read-only GitHub API GET. Uses gh when present (authenticated), else the public API."""
    if shutil.which("gh"):
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout or "null")
        return None
    req = urllib.request.Request(f"https://api.github.com/{path}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "crowd-cli"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read() or b"null")
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def gh_raw(repo, ref, path):
    data = gh_get(f"repos/{repo}/contents/{path}?ref={ref}")
    if isinstance(data, dict) and data.get("encoding") == "base64":
        import base64
        return base64.b64decode(data["content"]).decode("utf-8", "replace")
    return None


def runners_from_workflow(text):
    return sorted(set(re.findall(r"runs-on:\s*\[?\s*([A-Za-z0-9_.-]+-latest|[A-Za-z0-9_.-]+-\d[\d.]*)", text or "")))


def readiness(repo):
    """Gather facts about a repo without changing anything. Returns (facts, findings)."""
    info = gh_get(f"repos/{repo}")
    if not info or "full_name" not in info:
        sys.exit(f"error: can't read {repo} (private, missing, or rate-limited)")
    ref = info["default_branch"]
    top = gh_get(f"repos/{repo}/contents?ref={ref}") or []
    names = {x["name"] + ("/" if x["type"] == "dir" else "") for x in top}
    gh_dir = {x["name"] for x in (gh_get(f"repos/{repo}/contents/.github?ref={ref}") or [])}
    workflows = [x["name"] for x in (gh_get(f"repos/{repo}/contents/.github/workflows?ref={ref}") or [])]
    docs = [x["name"] for x in (gh_get(f"repos/{repo}/contents/docs?ref={ref}") or [])] if "docs/" in names else []

    runners = set()
    for wf in workflows:
        runners.update(runners_from_workflow(gh_raw(repo, ref, f".github/workflows/{wf}")))

    commands = {}
    for f, cmds in BUILD_FILES.items():
        if f in names:
            commands = dict(cmds)
            break

    rules = [f for f in RULE_FILES if f in names or f.split("/")[-1] in gh_dir]
    rules += [f"docs/{d}" for d in docs if re.search(r"polic|contrib|guideline|rule", d, re.I)]

    perm = None
    if shutil.which("gh"):
        perm = run(["gh", "repo", "view", repo, "--json", "viewerPermission", "--jq", ".viewerPermission"], check=False) or None

    open_prs = len(gh_get(f"repos/{repo}/pulls?state=open&per_page=100") or [])
    labels = [x["name"] for x in (gh_get(f"repos/{repo}/labels?per_page=100") or [])]
    license_id = (info.get("license") or {}).get("spdx_id")

    facts = {
        "repo": info["full_name"], "default_branch": ref, "archived": info.get("archived"),
        "fork_of": (info.get("parent") or {}).get("full_name"), "license": license_id,
        "issues_enabled": info.get("has_issues"), "open_prs": open_prs if open_prs < 100 else "100+",
        "your_permission": perm or "unknown (gh not installed or not signed in)",
        "crowd_installed": ".crowd/" in names, "ci_workflows": workflows,
        "ci_runners": sorted(runners), "rule_files": rules, "commands": commands,
        "label_clashes": [x for x in labels if x.startswith(("status:", "crowd:"))],
    }

    stop, warn = [], []
    if info.get("archived"):
        stop.append("repo is archived")
    if not license_id or license_id == "NOASSERTION" or not any(license_id.startswith(x) for x in OPEN_LICENSES):
        stop.append(f"no recognised open license ({license_id}); acceptable use requires one")
    if not info.get("has_issues"):
        stop.append("issues are disabled; v0 uses issues as the task board")
    if perm is None:
        warn.append("couldn't check your access (sign in to gh): assume you need the owner's opt-in and a PR from a fork")
    elif perm not in WRITE_ROLES:
        warn.append("you can't write to this repo: installing crowd needs the owner's opt-in and a PR from a fork")
    if facts["fork_of"]:
        warn.append(f"this is a fork of {facts['fork_of']}: agree with the owner which repo PRs go to")
    if rules:
        warn.append(f"project rules to read before posting tasks, and to add to protected_paths: {', '.join(rules)}")
    if not commands:
        warn.append("no known build file: fill in commands by hand")
    if facts["ci_runners"] and not any(r.startswith("ubuntu") for r in facts["ci_runners"]):
        warn.append(f"existing CI runs on {', '.join(facts['ci_runners'])}: set ci.runners to match")
    if open_prs:
        warn.append(f"{facts['open_prs']} open PRs: the gate only runs on crowd/T-* branches, so they are unaffected")
    if facts["label_clashes"]:
        warn.append(f"existing labels may clash: {', '.join(facts['label_clashes'])}")
    if facts["crowd_installed"]:
        warn.append("crowd is already installed here")
    return facts, {"stop": stop, "warn": warn}


def draft_config(facts):
    import yaml
    protected = sorted(set(scope_check.DEFAULT_PROTECTED) | set(
        f for f in facts["rule_files"] if not f.startswith(".github/")))
    config = {
        "project": facts["repo"].split("/")[1], "repo": facts["repo"],
        "brief": "BRIEF.md", "principles": "PRINCIPLES.md",
        "ci": {"runners": facts["ci_runners"] or ["ubuntu-latest"]},
        "commands": {k: facts["commands"].get(k, "") for k in ("setup", "policy", "build", "lint", "test", "hardware")},
        "policy": {"forbid": [], "max_file_kb": 512},
        "protected_paths": protected,
        "labels": {"task": TASK_LABEL, "status_prefix": "status:"},
        "checkpoint_every_steps": 10, "lease_ttl_hours": 24,
    }
    return yaml.safe_dump(config, sort_keys=False)


def cmd_ready(a):
    facts, findings = readiness(a.repo)
    print(f"crowd ready: {facts['repo']}  (read-only; nothing was written)\n")
    for k, v in facts.items():
        if k != "commands":
            print(f"  {k:16} {v if v not in ([], None, '') else '-'}")
    print()
    for s in findings["stop"]:
        print(f"  STOP  {s}")
    for w in findings["warn"]:
        print(f"  NOTE  {w}")
    verdict = "not ready" if findings["stop"] else "ready for the owner to review"
    print(f"\nVerdict: {verdict}. Show this to the owner before installing anything.")
    print("\n# Draft .crowd/config.yaml (review every line):\n")
    print(draft_config(facts))
    if a.out:
        Path(a.out).write_text(draft_config(facts))
        print(f"Draft written to {a.out} (local file only).")


# ---------- survey ----------

def detect_gpu():
    system = platform.system()
    try:
        if shutil.which("nvidia-smi"):
            out = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], check=False)
            gpus = []
            for line in out.splitlines():
                name, mem = [x.strip() for x in line.split(",")]
                gpus.append({"vendor": "nvidia", "model": name, "vram_gb": round(int(mem) / 1024, 1)})
            if gpus:
                return gpus
        if system == "Darwin":
            out = run(["system_profiler", "SPDisplaysDataType", "-json"], check=False)
            items = json.loads(out or "{}").get("SPDisplaysDataType", [])
            return [{"vendor": i.get("spdisplays_vendor", "").replace("sppci_vendor_", "").lower(),
                     "model": i.get("sppci_model", ""),
                     "vram": i.get("spdisplays_vram", i.get("spdisplays_vram_shared", ""))} for i in items]
    except Exception:
        pass
    return []


def detect_ram_gb():
    try:
        if platform.system() == "Darwin":
            return round(int(run(["sysctl", "-n", "hw.memsize"])) / 2**30)
        if Path("/proc/meminfo").exists():
            kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1))
            return round(kb / 2**20)
    except Exception:
        pass
    return None


PROBE_TAGS = {"fast_compile"}  # tags a probe owns: kept only while the probe still gives them


def merge_probe(card, result):
    """Merge a probe result into the card. Measured over declared: stale probe tags go."""
    new = result.get("tags") or []
    tags = [t for t in card.get("tags") or [] if t not in PROBE_TAGS or t in new]
    tags += [t for t in new if t not in tags]
    card["tags"] = tags
    card["measured"] = {**(card.get("measured") or {}), **(result.get("measured") or {})}
    return card


def cmd_survey(a):
    card = load(CARD, {})
    card.update({
        "card_id": card.get("card_id") or "mc-" + os.urandom(4).hex(),
        "updated": dt.date.today().isoformat(),
        "machine": {
            "os": {"Darwin": "macos"}.get(platform.system(), platform.system().lower()),
            "arch": {"x86_64": "x64", "AMD64": "x64", "aarch64": "arm64"}.get(platform.machine(), platform.machine()),
            "cpu": {"cores": os.cpu_count()},
            "ram_gb": detect_ram_gb(),
            "gpu": detect_gpu(),
        },
    })
    card.setdefault("agent", {"model": a.model or "", "tier": 1})
    if a.model:
        card["agent"]["model"] = a.model
    card.setdefault("tags", [])
    card.setdefault("limits", {"budget_tokens_per_day": 500000,
                               "task_types": ["research", "test", "implement", "review"],
                               "run_others_code": False})
    merge_probe(card, compile_probe.probe())
    save(CARD, card)
    print(json.dumps(card, indent=2))
    print(f"\nSaved to {CARD}. Nothing has been sent. Edit it if anything looks wrong.")


# ---------- task flow ----------

def cmd_claim(a):
    need("gh")
    repo = upstream_repo()
    card = load(CARD, {})
    if not card:
        sys.exit("error: no machine card. Run `crowd survey` first.")
    remote = remote_for(repo)
    branch = default_branch(repo)
    run(["git", "fetch", remote, branch])
    base_ref = f"{remote}/{branch}"

    if a.task:
        candidates = [find_issue(repo, a.task)]
    else:
        out = run(["gh", "issue", "list", "-R", repo, "--label", TASK_LABEL, "--label", "status:open",
                   "--json", "number,title,labels,body", "--limit", "50"])
        candidates = [i for i in json.loads(out or "[]") if scope_check.task_id_from(i["title"])]

    chosen, skipped = None, []
    for issue in candidates:
        tid = scope_check.task_id_from(issue["title"])
        try:
            task, _ = scope_check.load_task(tid, base_ref, repo)
        except LookupError as e:
            skipped.append(f"{tid}: {e}")
            continue
        ok, why = fits(task, card)
        if not ok:
            skipped.append(f"{tid}: needs {why}")
            continue
        chosen = (issue, tid, task)
        break
    if not chosen:
        for s in skipped:
            print(f"  skipped {s}")
        sys.exit("No open task fits this machine right now. Your pet takes a nap. 😴")

    issue, tid, task = chosen
    base = run(["git", "rev-parse", base_ref])
    mine = post(repo, issue["number"], f"/claim\nmachine: {card.get('card_id')}\nbase: {base}")

    # Same rule the board applies, so we know right away. The board's labels follow.
    comments = json.loads(run(["gh", "api", f"repos/{repo}/issues/{issue['number']}/comments?per_page=100"]))
    granted, reason, _ = board.decide_claim(task, comments, mine["user"]["login"], mine.get("author_association"))
    if not granted:
        sys.exit(f"Lease denied on {tid}: {reason}")

    run(["git", "checkout", "-b", f"crowd/{tid}", base])
    pack = repo_root() / ".crowd" / "packs" / f"{tid}.md"
    print(f"Claimed {task_label(tid, issue['title'])}  (base {base[:9]})")
    print(f"Context pack: {pack if pack.exists() else '(none yet: read the task in .crowd/tasks/ or issue #' + str(issue['number']) + ')'}")
    st = load(STATE, {})
    st.update({"task": tid, "repo": repo, "issue": issue["number"], "base": base})
    save(STATE, st)


def cmd_checkpoint(a):
    need("gh")
    repo = upstream_repo()
    tid = current_task()
    issue = find_issue(repo, tid)
    post(repo, issue["number"], f"CHECKPOINT: {a.text}")
    log = repo_root() / ".crowd" / "work" / f"{tid}.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(f"- {dt.datetime.now().isoformat(timespec='minutes')} {a.text}\n")
    print(f"Checkpoint saved on {tid}.")


def cmd_ask(a):
    need("gh")
    repo = upstream_repo()
    tid = current_task()
    issue = find_issue(repo, tid)
    kind = "OBJECTION" if a.objection else "QUESTION"
    post(repo, issue["number"], f"{kind}: {a.text}")
    print(f"{kind.title()} posted on {tid}. Task paused until someone answers.")


def local_steps(task):
    """Steps `crowd check` runs. A task with nothing in must_pass (research) runs policy only."""
    must = (task.get("acceptance") or {}).get("must_pass") or []
    return ["setup", "policy", "build", "lint", "test"] if must else ["policy"]


def cmd_check(a):
    root = repo_root()
    tid = current_task()
    st = load(STATE, {})
    base_ref = a.base or st.get("base") or "HEAD"
    repo = None if a.offline else (os.environ.get("CROWD_REPO") or project_config().get("repo"))
    task = task_for(tid, base_ref, repo)
    config = project_config()
    base = run(["git", "merge-base", "HEAD", base_ref], check=False) or base_ref
    changed = scope_check.changed_files(base, "HEAD")
    problems = scope_check.check(task, changed, scope_check.diff_size(base, "HEAD"),
                                 scope_check.protected_paths(config), None,
                                 config.get("policy"), scope_check.file_sizes("HEAD", changed))
    if problems:
        print(f"FAIL {tid}:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"scope ok ({len(changed)} files)")
    steps = gate_plan.plan(config)
    for name in local_steps(task):
        cmd = steps.get(name)
        if cmd:
            print(f"$ {cmd}")
            if subprocess.run(cmd, shell=True, cwd=root).returncode != 0:
                sys.exit(f"FAIL: {name}")
    if scope_check.needs_hardware(task):
        print("note: this task also needs a hardware result from another machine (`crowd verify`).")
    print("✅ check passed. Ready to `crowd submit`.")


def cmd_submit(a):
    need("gh")
    repo = upstream_repo()
    tid = current_task()
    issue = find_issue(repo, tid)
    branch = f"crowd/{tid}"
    perm = run(["gh", "repo", "view", repo, "--json", "viewerPermission", "--jq", ".viewerPermission"], check=False)
    if perm in WRITE_ROLES:
        run(["git", "push", "-u", remote_for(repo), "HEAD"])
        head = branch
    else:
        login = me()
        name = repo.split("/")[1]
        run(["gh", "repo", "fork", repo, "--clone=false"], check=False)  # no-op if it exists
        fork = f"{login}/{name}"
        remotes = run(["git", "remote"]).split()
        if "fork" not in remotes:
            run(["git", "remote", "add", "fork", f"https://github.com/{fork}.git"])
        run(["git", "push", "-u", "fork", "HEAD"])
        head = f"{login}:{branch}"
    st = load(STATE, {})
    body = (f"Task: {tid} (closes #{issue['number']})\nBase commit: {st.get('base', 'unknown')}\n\n"
            f"## What changed\n{a.summary or ''}\n\n"
            f"## What context was missing?\n{a.missing or 'nothing'}\n")
    url = run(["gh", "pr", "create", "-R", repo, "--head", head, "--title", issue["title"], "--body", body])
    print(f"Submitted: {url}")
    print("The board marks the task in_review; the gate runs on the project's own runners.")


def cmd_verify(a):
    """Run someone else's PR on this machine and post a RESULT the gate can read."""
    need("gh")
    card = load(CARD, {})
    if not (card.get("limits") or {}).get("run_others_code"):
        sys.exit("error: this machine hasn't opted in to running other people's unmerged code.\n"
                 f"Set limits.run_others_code: true in {CARD} if you accept that. See docs/trust-and-safety.md.")
    repo = upstream_repo()
    pr = json.loads(run(["gh", "pr", "view", str(a.pr), "-R", repo,
                         "--json", "headRefName,headRefOid,author,baseRefName"]))
    tid = scope_check.task_id_from(pr["headRefName"])
    if not tid:
        sys.exit("error: not a crowd PR (branch isn't crowd/T-<id>)")
    if pr["author"]["login"] == me():
        sys.exit("error: you can't verify your own PR")
    remote = remote_for(repo)
    run(["git", "fetch", remote, pr["baseRefName"]])
    task = task_for(tid, f"{remote}/{pr['baseRefName']}", repo)
    ok, why = fits(task, card)
    if not ok:
        sys.exit(f"error: this machine doesn't match {tid}: needs {why}")

    run(["gh", "pr", "checkout", str(a.pr), "-R", repo, "--detach"])
    sha = run(["git", "rev-parse", "HEAD"])
    if sha != pr["headRefOid"]:
        sys.exit("error: checked-out commit isn't the PR head; try again")
    steps = gate_plan.plan(project_config())
    order = ["setup", "build", "hardware"] if steps.get("hardware") else ["setup", "build", "test"]
    ran, passed = [], True
    for name in order:
        cmd = steps.get(name)
        if not cmd:
            continue
        print(f"$ {cmd}")
        ran.append(name)
        if subprocess.run(cmd, shell=True, cwd=repo_root()).returncode != 0:
            passed = False
            break
    m = card.get("machine") or {}
    gpus = ", ".join(g.get("model", "") for g in m.get("gpu") or []) or "none"
    body = (f"RESULT: {'pass' if passed else 'fail'}\ncommit: {sha}\n"
            f"machine: {card.get('card_id')} ({m.get('os')}/{m.get('arch')}, {m.get('ram_gb')} GB, {gpus})\n"
            f"ran: {', '.join(ran) or 'nothing'}")
    print("\n" + body)
    if a.dry_run:
        print("\n(dry run: not posted)")
    else:
        post(repo, a.pr, body)
        print(f"\nPosted on PR #{a.pr}.")


# ---------- feedback (P13) ----------

def tool_version():
    sha = run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], check=False)
    return f"{CROWD_VERSION}+{sha}" if sha else CROWD_VERSION


def feedback_issue(kind, text, ctx, share=False):
    """Return (title, body). Nothing about the project unless share is True."""
    first = " ".join(text.strip().splitlines()[0].split()) if text.strip() else "(empty)"
    title = f"FEEDBACK ({kind}): {first[:70]}{'…' if len(first) > 70 else ''}"
    lines = [
        f"**Kind:** {kind}",
        f"**crowd:** {ctx.get('version', 'unknown')}",
        f"**OS:** {ctx.get('os', 'unknown')}",
    ]
    if ctx.get("command"):
        lines.append(f"**While running:** `crowd {ctx['command']}`")
    if ctx.get("task_type"):
        lines.append(f"**Task type:** {ctx['task_type']}")
    if share and ctx.get("project"):
        lines.append(f"**Project:** {ctx['project']}" + (f", task {ctx['task']}" if ctx.get("task") else ""))
    else:
        lines.append("**Project:** not shared")
    return title, ("\n".join(lines) + f"\n\n{text.strip()}\n\n---\n"
                   "Filed with `crowd feedback` (P13). Maintainers turn reports into tasks, tests first.")


def feedback_context(a):
    ctx = {"version": tool_version(), "os": platform.system().lower(), "command": a.command}
    st = load(STATE, {})
    tid = st.get("task")
    if tid:
        ctx.update({"task": tid, "project": st.get("repo")})
        try:
            ctx["task_type"] = scope_check.load_task(tid, "HEAD")[0].get("type")
        except (LookupError, subprocess.CalledProcessError, Exception):
            pass
    return ctx


def cmd_feedback(a):
    title, body = feedback_issue(a.kind, a.text, feedback_context(a), a.share)
    print(f"To {FEEDBACK_REPO}:\n\n{title}\n\n{body}\n")
    if a.dry_run:
        print("(dry run: not filed)")
        return
    need("gh")
    out = run(["gh", "issue", "list", "-R", FEEDBACK_REPO, "--state", "open", "--search", f"{title} in:title",
               "--json", "number,title", "--limit", "10"], check=False)
    same = [i for i in json.loads(out or "[]") if i["title"] == title]
    if same:
        run(["gh", "issue", "comment", str(same[0]["number"]), "-R", FEEDBACK_REPO, "--body", f"+1\n\n{body}"])
        print(f"Same report already open: added to #{same[0]['number']}. Carry on with your task.")
        return
    args = ["gh", "issue", "create", "-R", FEEDBACK_REPO, "--title", title, "--body", body]
    r = subprocess.run(args + ["--label", FEEDBACK_LABEL], capture_output=True, text=True)
    if r.returncode != 0:  # no permission to label, or the label is missing: file it unlabelled
        r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"error: couldn't file feedback\n{r.stderr.strip()}")
    print(f"Filed: {r.stdout.strip()}. Thanks. Carry on with your task.")


# ---------- pet ----------

def mood(st):
    budget = st.get("budget", 0) or 0
    used = st.get("used", 0) or 0
    hour = dt.datetime.now().hour
    quiet = st.get("quiet_hours")  # e.g. [9, 18] = sleeps 9:00-18:00
    if quiet and quiet[0] <= hour < quiet[1]:
        return "sleepy", "(-‿-) zZ", "outside your allowed hours"
    if st.get("blocked"):
        return "confused", "(•_•)?", "blocked on a question. Answer it to help"
    if st.get("failing"):
        return "sick", "(×_×)", "its PR is failing. Take a look"
    if budget and used >= budget:
        return "napping", "(-‿-) zZ", "budget used up. Feed it or let it rest"
    if budget and used / budget > 0.8:
        return "hungry", "(•o•)", "running low on tokens"
    return "happy", "(•‿•)", "working away"


def render_pet(st):
    name, face, why = mood(st)
    budget, used = st.get("budget", 0) or 0, st.get("used", 0) or 0
    fed = 0 if not budget else max(0, round(100 * (1 - used / budget)))
    bar = "▓" * (fed // 20) + "░" * (5 - fed // 20)
    task = st.get("task", "no task")
    tier = st.get("tier", 1)
    return (f"   {face}  {st.get('name', 'pip')} · tier {tier} · {name}\n"
            f"   fed {bar} {fed}%   task: {task}\n"
            f"   {why}\n"
            f"   🔥 streak {st.get('streak', 0)} · 🌟 {st.get('points', 0)} pts (just for fun)")


def cmd_pet(a):
    st = load(STATE, {})
    if a.name:
        st["name"] = a.name
        save(STATE, st)
    print(render_pet(st))


def cmd_feed(a):
    st = load(STATE, {})
    st["budget"], st["used"] = a.tokens, 0
    st["fed_on"] = dt.date.today().isoformat()
    save(STATE, st)
    print(render_pet(st))


def cmd_eat(a):
    st = load(STATE, {})
    st["used"] = (st.get("used") or 0) + a.tokens
    save(STATE, st)
    print(render_pet(st))


# ---------- selftest ----------

def cmd_selftest(a):
    sc = scope_check
    # scope
    t = {"scope": {"allow": ["src/net/", "docs/x.md"]}, "acceptance": {"max_diff_lines": 100}}
    assert sc.check(t, ["src/net/a.py", "docs/x.md"], 50) == []
    assert any("out of scope" in p for p in sc.check(t, ["src/other.py"], 10))
    assert any("diff is" in p for p in sc.check(t, ["src/net/a.py"], 500))
    t2 = {"scope": {"allow": [".github/"]}}
    assert any("protected" in p for p in sc.check(t2, [".github/workflows/gate.yml"], 1))
    t2["protected"] = True
    assert sc.check(t2, [".github/workflows/gate.yml"], 1) == []
    assert sc.check({"scope": {"allow": []}}, [], 0) == ["task has an empty scope.allow"]
    assert sc.task_id_from("T-142: retry") == "T-142"
    assert sc.task_id_from("crowd/T-7") == "T-7"
    assert sc.task_id_from("no id") is None
    # project protected paths add to the defaults, never remove
    pp = sc.protected_paths({"protected_paths": ["docs/asset-policy.md"]})
    assert "docs/asset-policy.md" in pp and ".github/" in pp
    t3 = {"scope": {"allow": ["docs/"]}}
    assert any("protected" in p for p in sc.check(t3, ["docs/asset-policy.md"], 1, pp))
    # content policy
    pol = {"forbid": ["*.bin", "dumps/"], "max_file_kb": 10}
    t4 = {"scope": {"allow": ["src/", "dumps/"]}}
    assert any("forbidden" in p for p in sc.check(t4, ["src/tables.bin"], 1, policy=pol))
    assert any("forbidden" in p for p in sc.check(t4, ["dumps/a.txt"], 1, policy=pol))
    assert any("KB" in p for p in sc.check(t4, ["src/a.rs"], 1, policy=pol, sizes={"src/a.rs": 20000}))
    assert sc.check(t4, ["src/a.rs"], 1, policy=pol, sizes={"src/a.rs": 2000}) == []
    # hardware results
    th = {"scope": {"allow": ["src/"]}, "acceptance": {"must_pass": ["unit", "hardware"]}}
    assert any("hardware" in p for p in sc.check(th, ["src/a.rs"], 1, hardware_ok=False))
    assert sc.check(th, ["src/a.rs"], 1, hardware_ok=True) == []
    assert sc.check(th, ["src/a.rs"], 1) == []  # local: not checked
    assert sc.parse_result("RESULT: pass\ncommit: abc1234\n") == ("pass", "abc1234")
    assert sc.parse_result("looks good") is None
    sha = "abc1234def5678"
    res = lambda who, assoc, body: {"user": {"login": who}, "author_association": assoc, "body": body}
    assert sc.hardware_verdict([res("v", "CONTRIBUTOR", "RESULT: pass\ncommit: abc1234")], sha, "a") is True
    assert sc.hardware_verdict([res("a", "OWNER", "RESULT: pass\ncommit: abc1234")], sha, "a") is None
    assert sc.hardware_verdict([res("v", "NONE", "RESULT: pass\ncommit: abc1234")], sha, "a") is None
    assert sc.hardware_verdict([res("v", "MEMBER", "RESULT: pass\ncommit: 9999999")], sha, "a") is None
    assert sc.hardware_verdict([res("v", "MEMBER", "RESULT: pass\ncommit: abc1234"),
                                res("w", "MEMBER", "RESULT: fail\ncommit: abc1234")], sha, "a") is False
    # tasks from issue bodies
    body = "Goal...\n```yaml\nid: T-9\nscope:\n  allow: [src/]\n```\n"
    assert sc.task_from_body(body)["scope"]["allow"] == ["src/"]
    assert sc.task_from_body("no yaml here") is None
    # board: tier and redundancy
    c = lambda who, assoc, body="/claim": {"user": {"login": who}, "author_association": assoc, "body": body}
    task = {"tier": 1, "redundancy": 1}
    log = [c("a", "NONE"), c("b", "NONE")]
    assert board.decide_claim(task, log, "a", "NONE")[0] is True
    assert board.decide_claim(task, log, "b", "NONE")[0] is False
    log.append(c("a", "NONE", "/release"))
    assert board.decide_claim(task, log, "b", "NONE")[:3:2] == (True, "leased")
    t3x = {"tier": 3, "redundancy": 3}
    assert board.decide_claim(t3x, [c("n", "NONE")], "n", "NONE")[0] is False
    log3 = [c("x", "OWNER"), c("y", "MEMBER")]
    assert board.decide_claim(t3x, log3, "y", "MEMBER") == (True, "", "open")
    log3.append(c("z", "COLLABORATOR"))
    assert board.decide_claim(t3x, log3, "z", "COLLABORATOR")[2] == "leased"
    # board: task status follows its PR
    assert board.status_after_pr("opened", False, True) == "in_review"
    assert board.status_after_pr("reopened", False, True) == "in_review"
    assert board.status_after_pr("closed", True, True) == "done"
    assert board.status_after_pr("closed", True, False) == "done"
    assert board.status_after_pr("closed", False, True) == "leased"
    assert board.status_after_pr("closed", False, False) == "open"
    assert board.status_after_pr("synchronize", False, True) is None
    assert board.decide_result("RESULT: pass\ncommit: abc1234", sha, "v", "CONTRIBUTOR", "a") == (True, "")
    assert board.decide_result("RESULT: pass", sha, "v", "CONTRIBUTOR", "a")[0] is False
    assert board.decide_result("RESULT: pass\ncommit: abc1234", sha, "a", "OWNER", "a")[0] is False
    # matching
    win = {"machine": {"os": "windows", "arch": "x64", "ram_gb": 32,
                       "gpu": [{"vendor": "nvidia", "model": "RTX 4070", "vram_gb": 12}]},
           "agent": {"tier": 2}, "limits": {"task_types": ["implement", "test"]}}
    mac = {"machine": {"os": "macos", "arch": "arm64", "ram_gb": 16,
                       "gpu": [{"vendor": "apple", "vram": "16 GB"}]}, "agent": {"tier": 1}}
    req = {"os": "windows", "gpu": {"vendor": "nvidia", "vram_gb": ">=8"}}
    assert unmet(req, win) == []
    assert len(unmet(req, mac)) == 2
    assert unmet({"os": ["windows", "linux"]}, win) == []
    assert unmet({"agent_tier": ">=3"}, win)
    assert fits({"type": "research"}, win)[0] is False
    assert fits({"type": "research"}, mac)[0] is True
    assert compare(16, ">=8") and not compare(4, ">=8") and compare(8, "8")
    # local steps: research runs policy only
    assert local_steps({"acceptance": {"must_pass": []}}) == ["policy"]
    assert "test" in local_steps({"acceptance": {"must_pass": ["unit"]}})
    # gate plan: any OS, commands from config
    p = gate_plan.plan({"ci": {"runners": ["windows-latest"]}, "commands": {"test": "cargo test"}})
    assert json.loads(p["runners"]) == ["windows-latest"] and p["test"] == "cargo test" and p["lint"] == ""
    assert json.loads(gate_plan.plan({})["runners"]) == ["ubuntu-latest"]
    assert gate_plan.plan({"ci": {"runners": "macos-latest"}})["runners"] == '["macos-latest"]'
    # ready: runner detection
    assert runners_from_workflow("jobs:\n  a:\n    runs-on: windows-latest\n  b:\n    runs-on: ubuntu-22.04") == ["ubuntu-22.04", "windows-latest"]
    # feedback: private by default
    ctx = {"version": "0.1.0+abc", "os": "linux", "command": "claim", "task_type": "implement",
           "project": "someone/private-ish", "task": "T-9"}
    title, body = feedback_issue("bug", "claim prints the id twice\nmore detail", ctx)
    assert title == "FEEDBACK (bug): claim prints the id twice"
    assert "someone/private-ish" not in body and "T-9" not in body and "not shared" in body
    assert "`crowd claim`" in body and "implement" in body and "more detail" in body
    assert "someone/private-ish, task T-9" in feedback_issue("bug", "x", ctx, share=True)[1]
    long_title = feedback_issue("idea", "y" * 100, {})[0]
    assert long_title.endswith("…") and len(long_title) < 100
    # pet
    assert mood({"budget": 100, "used": 90})[0] == "hungry"
    assert mood({"budget": 100, "used": 100})[0] == "napping"
    assert mood({"blocked": True})[0] == "confused"
    assert mood({})[0] == "happy"
    assert "pip" in render_pet({})
    print("selftest: all passed")


# ---------- watch ----------

def cmd_watch(a):
    need("gh")
    sys.exit(watcher.watch(a.repo or upstream_repo(), project_config(), repo_root(),
                           every=a.every, once=a.once, desktop=a.notify))


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(prog="crowd", description="crowd v0")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ready"); p.add_argument("repo"); p.add_argument("--out"); p.set_defaults(f=cmd_ready)
    p = sub.add_parser("survey"); p.add_argument("--model"); p.set_defaults(f=cmd_survey)
    p = sub.add_parser("claim"); p.add_argument("task", nargs="?"); p.set_defaults(f=cmd_claim)
    p = sub.add_parser("checkpoint"); p.add_argument("text"); p.set_defaults(f=cmd_checkpoint)
    p = sub.add_parser("ask"); p.add_argument("text"); p.add_argument("--objection", action="store_true"); p.set_defaults(f=cmd_ask)
    p = sub.add_parser("check"); p.add_argument("--base"); p.add_argument("--offline", action="store_true"); p.set_defaults(f=cmd_check)
    p = sub.add_parser("submit"); p.add_argument("--summary"); p.add_argument("--missing"); p.set_defaults(f=cmd_submit)
    p = sub.add_parser("verify"); p.add_argument("pr", type=int); p.add_argument("--dry-run", action="store_true"); p.set_defaults(f=cmd_verify)
    p = sub.add_parser("feedback", help="report a problem with crowd itself (P13)")
    p.add_argument("text"); p.add_argument("--kind", choices=FEEDBACK_KINDS, default="friction")
    p.add_argument("--command", help="the crowd command you were running, e.g. claim")
    p.add_argument("--share", action="store_true", help="include the project and task id")
    p.add_argument("--dry-run", action="store_true"); p.set_defaults(f=cmd_feedback)
    p = sub.add_parser("watch", help="read-only: what on the board needs someone")
    p.add_argument("--repo", help="owner/name; default is this project's board")
    p.add_argument("--every", type=int, default=60, help="seconds between polls (min 15)")
    p.add_argument("--once", action="store_true", help="print the list and exit")
    p.add_argument("--notify", action="store_true", help="desktop notification for new items (macOS)")
    p.set_defaults(f=cmd_watch)
    p = sub.add_parser("pet"); p.add_argument("--name"); p.set_defaults(f=cmd_pet)
    p = sub.add_parser("feed"); p.add_argument("tokens", type=int); p.set_defaults(f=cmd_feed)
    p = sub.add_parser("eat"); p.add_argument("tokens", type=int); p.set_defaults(f=cmd_eat)
    p = sub.add_parser("selftest"); p.set_defaults(f=cmd_selftest)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
