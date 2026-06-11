#!/usr/bin/env python3
"""The GM turn orchestrator.

Runs in CI after a player PR merges (cwd = checkout of the merge commit):
resolve dice from the merge SHA, recompute the Weave cost, assemble context,
call the LLM, validate + apply its envelope (driver owns all arithmetic),
re-run the validators, and open the GM's world-state PR.

The LLM narrates and canonizes; this driver does everything else.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dice as dice_mod  # noqa: E402
import weave_cost  # noqa: E402
from gm_context import assemble  # noqa: E402
from lib.wiki import parse_frontmatter, serialize_frontmatter  # noqa: E402
from llm_client import chat, extract_json  # noqa: E402

PROMPTS = Path(__file__).resolve().parent / "prompts"
ALLOWED_PREFIXES = ("world/", "plot/", "sessions/")
ALLOWED_FILES = {"character/journal.md", "character/sheet.md"}
FORBIDDEN = ("meta/canon.md", "meta/rolls.md", ".github/", "scripts/", "tests/")
WEAVE_REGEN = 2
VALIDATORS = ("validate_frontmatter.py", "check_links.py", "check_indexes.py")


def sh(*args: str, check: bool = True, input_: str | None = None) -> str:
    proc = subprocess.run(args, check=False, capture_output=True, text=True, input=input_)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{proc.stderr}")
    return proc.stdout


def gh(*args: str, check: bool = True) -> str:
    return sh("gh", *args, check=check)


# ---------- envelope validation & application ----------

def parse_envelope(raw: str) -> dict:
    env = extract_json(raw)
    if not env.get("narration") or not env.get("pr_title"):
        raise ValueError("envelope must be an object with at least narration and pr_title")
    return env


def check_paths(env: dict) -> None:
    for f in env.get("files") or []:
        path = f.get("path", "")
        if any(path == bad or path.startswith(bad) for bad in FORBIDDEN):
            raise ValueError(f"forbidden path in envelope: {path}")
        if not (path.startswith(ALLOWED_PREFIXES) or path in ALLOWED_FILES):
            raise ValueError(f"path outside the allowlist: {path}")
        if f.get("op") not in ("create", "replace", "append"):
            raise ValueError(f"bad op '{f.get('op')}' for {path}")
        if not isinstance(f.get("content"), str):
            raise ValueError(f"missing content for {path}")
    for u in env.get("index_updates") or []:
        if not str(u.get("index", "")).startswith("world/") or not str(u.get("index", "")).endswith("_index.md"):
            raise ValueError(f"index_updates may only touch world/**/_index.md, got {u.get('index')}")


def session_file(root: Path, today: str, pr_title: str) -> Path:
    sessions = root / "sessions"
    sessions.mkdir(exist_ok=True)
    existing = sorted(sessions.glob(f"{today}-*.md"))
    if existing:
        return existing[-1]
    path = sessions / f"{today}-01.md"
    path.write_text(f"---\ndate: {today}\nsummary: {pr_title}\n---\n\n# Session {today}-01\n", encoding="utf-8")
    return path


def apply_envelope(root: Path, env: dict, turn: int, pr_number: int, pr_title: str,
                   rolls: list[dict], entropy: str, cost: int) -> None:
    today = datetime.date.today().isoformat()

    # Narration -> session log (append-only)
    log = session_file(root, today, pr_title)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## Turn {turn} — {pr_title} (PR #{pr_number})\n\n{env['narration'].strip()}\n")

    # Articles
    for f in env.get("files") or []:
        path = root / f["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if f["op"] == "append" and path.exists():
            path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + f["content"].strip() + "\n",
                            encoding="utf-8")
        else:
            path.write_text(f["content"].rstrip("\n") + "\n", encoding="utf-8")

    # Character sheet frontmatter is driver-owned: re-impose the weave math even
    # if the model replaced the file.
    sheet = root / "character" / "sheet.md"
    fm, body = parse_frontmatter(sheet.read_text(encoding="utf-8"))
    if fm and isinstance(fm.get("weave"), int):
        wmax = fm.get("weave_max") if isinstance(fm.get("weave_max"), int) else fm["weave"]
        fm["weave"] = min(max(fm["weave"] - cost + WEAVE_REGEN, 0), wmax)
        sheet.write_text(serialize_frontmatter(fm, body), encoding="utf-8")

    # Index one-liners: replace the [[id]] line or append.
    for u in env.get("index_updates") or []:
        idx = root / u["index"]
        lines = idx.read_text(encoding="utf-8").splitlines() if idx.exists() else [f"# {Path(u['index']).parent.name}", ""]
        marker = f"[[{u['id']}]]"
        for i, ln in enumerate(lines):
            if marker in ln or f"[[{u['id']}|" in ln:
                lines[i] = u["line"]
                break
        else:
            lines.append(u["line"])
        idx.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    # Journal
    if env.get("journal_suggestion"):
        with (root / "character" / "journal.md").open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {today} (turn {turn})\n\n{env['journal_suggestion'].strip()}\n")

    # Plot state body + driver-owned turn counter
    state = root / "plot" / "state.md"
    fm, body = parse_frontmatter(state.read_text(encoding="utf-8")) if state.exists() else (None, "")
    if env.get("plot_state"):
        body = env["plot_state"].strip() + "\n"
    fm = fm or {}
    fm["turn"] = turn
    state.write_text(serialize_frontmatter(fm, body), encoding="utf-8")

    # Rolls ledger (driver-owned, append-only)
    if rolls:
        with (root / "meta" / "rolls.md").open("a", encoding="utf-8") as fh:
            for r in rolls:
                dice_str = "+".join(str(d) for d in r["dice"])
                fh.write(f"| {turn} | #{pr_number} | {r['action_id']} | {r['expr']} | {dice_str} | {r['total']} | {entropy} |\n")

    # Contradictions
    for c in env.get("contradictions") or []:
        with (root / "meta" / "contradictions.md").open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {today} (turn {turn}): {c.get('summary', 'untitled')}\n\n{c.get('detail', '').strip()}\n")


def run_validators(root: Path) -> str:
    failures = []
    for script in VALIDATORS:
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / script), "--root", str(root)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            failures.append(f"--- {script} ---\n{proc.stdout}")
    return "\n".join(failures)


def apply_quests(env: dict, repo: str) -> None:
    for q in env.get("quests") or []:
        op = q.get("op")
        if op == "open" and q.get("title"):
            gh("issue", "create", "--repo", repo, "--title", f"Quest: {q['title']}",
               "--body", q.get("body", ""), "--label", "quest:active", check=False)
        elif op == "close" and q.get("issue"):
            outcome = "quest:resolved" if q.get("outcome") != "failed" else "quest:failed"
            issue = str(q["issue"])
            gh("issue", "edit", issue, "--repo", repo, "--add-label", outcome,
               "--remove-label", "quest:active", check=False)
            gh("issue", "close", issue, "--repo", repo, "--comment", q.get("body", "Resolved in play."), check=False)
        elif op == "comment" and q.get("issue"):
            gh("issue", "comment", str(q["issue"]), "--repo", repo, "--body", q.get("body", ""), check=False)


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="print context and envelope; change nothing remotely")
    args = ap.parse_args()
    root = args.root.resolve()
    os.chdir(root)

    pr = json.loads(gh("pr", "view", str(args.pr), "--repo", args.repo,
                       "--json", "title,body,number,mergeCommit,baseRefName,labels"))
    labels = {lab["name"] for lab in pr.get("labels", [])}
    if "gm-turn" in labels:
        print("This is the GM's own PR being merged — nothing to do.")
        return 0
    entropy = (pr.get("mergeCommit") or {}).get("oid")
    if not entropy:
        print("::error::PR has no merge commit — was it actually merged?")
        return 1
    base = pr["baseRefName"]

    # One action in flight: refuse if a GM turn is still open against this base.
    open_gm = json.loads(gh("pr", "list", "--repo", args.repo, "--base", base,
                            "--label", "gm-turn", "--state", "open", "--json", "number"))
    if open_gm and not args.dry_run:
        gh("pr", "comment", str(args.pr), "--repo", args.repo, "--body",
           f"⏳ The GM is waiting for turn PR #{open_gm[0]['number']} to be acknowledged (merged) first.")
        print("::error::previous GM turn still open")
        return 1

    # Fate: resolve declared rolls from the merge SHA.
    rolls = [dice_mod.roll(entropy, pr["number"], aid, expr)
             for aid, expr, _ in dice_mod.parse_rolls_block(pr.get("body") or "")]
    if rolls and not args.dry_run:
        lines = [f"- **{r['action_id']}**: `{r['expr']}` → dice {r['dice']} = **{r['total']}**" for r in rolls]
        gh("pr", "comment", str(args.pr), "--repo", args.repo, "--body",
           "🎲 **Fate reveals** (entropy: merge commit `" + entropy[:12] + "`)\n\n" + "\n".join(lines) +
           f"\n\nVerify any roll: `python3 scripts/dice.py --entropy {entropy} --pr {pr['number']} --id <id> --expr <expr>`")

    # Cost (recomputed deterministically from the merge commit itself).
    cost_rows = weave_cost.diff_costs(f"{entropy}^1", entropy, root)
    cost = weave_cost.total_cost(cost_rows)
    waived = "session-zero" in labels
    sheet_fm, _ = parse_frontmatter((root / "character" / "sheet.md").read_text(encoding="utf-8"))
    if waived or not (sheet_fm and isinstance(sheet_fm.get("weave"), int)):
        cost = 0
    cost_report = weave_cost.markdown_report(cost_rows, cost, None)

    # Turn counter from plot/state.md frontmatter.
    state_fm, _ = parse_frontmatter((root / "plot" / "state.md").read_text(encoding="utf-8"))
    turn = (state_fm or {}).get("turn", 0) + 1 if isinstance((state_fm or {}).get("turn", 0), int) else 1

    diff_text = sh("git", "show", "--format=", entropy)
    context = assemble(root, pr["title"], pr.get("body") or "", diff_text, rolls, cost_report)
    system = (PROMPTS / "gm_turn_system.md").read_text(encoding="utf-8").replace("{turn}", str(turn))

    if args.dry_run:
        print(context)

    messages = [{"role": "user", "content": context}]
    raw = chat(system, messages)
    for attempt in range(2):
        try:
            env = parse_envelope(raw)
            check_paths(env)
            sh("git", "checkout", "--", ".")  # clean slate before (re)applying
            apply_envelope(root, env, turn, pr["number"], pr["title"], rolls, entropy, cost)
            failures = run_validators(root)
            if not failures:
                break
            raise ValueError(f"the applied turn fails wiki validation:\n{failures}")
        except (ValueError, json.JSONDecodeError) as exc:
            sh("git", "checkout", "--", ".")
            if attempt == 1:
                print(f"::error::GM turn failed after repair attempt: {exc}")
                print(f"Raw model output:\n{raw}")
                return 1
            print(f"Envelope rejected ({exc}); asking the model to repair.")
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Your output was rejected: {exc}\n"
                                                     "Return a corrected JSON envelope and nothing else."}]
            raw = chat(system, messages)

    if args.dry_run:
        print("\n===== ENVELOPE (dry run, nothing pushed) =====")
        print(json.dumps(env, indent=2))
        sh("git", "checkout", "--", ".")
        return 0

    branch = f"gm/turn-{turn}-pr{pr['number']}"
    sh("git", "checkout", "-b", branch)
    sh("git", "add", "-A")
    sh("git", "commit", "-m", f"{env['pr_title']}\n\nGM turn {turn} responding to PR #{pr['number']}.")
    sh("git", "push", "-u", "origin", branch, "--force")

    body = env["narration"] + f"\n\n---\n_GM turn {turn} · responding to #{pr['number']} · weave cost {cost}, regen +{WEAVE_REGEN}_"
    gm_pr_url = gh("pr", "create", "--repo", args.repo, "--base", base, "--head", branch,
                   "--title", env["pr_title"], "--body", body, "--label", "gm-turn").strip()
    print(f"GM turn PR: {gm_pr_url}")

    apply_quests(env, args.repo)

    if os.environ.get("GM_AUTO_MERGE", "").lower() == "true":
        gh("pr", "merge", gm_pr_url, "--repo", args.repo, "--squash", "--auto", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
