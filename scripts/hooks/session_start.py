#!/usr/bin/env python3
"""SessionStart hook -- inject the anti-grind context.

Stdout becomes context at the start of every session. We surface, in order:

  1. the standing warning (a prose "step back and question the approach" rule
     gets ignored under momentum; the ledger is what actually enforces it);
  2. the pending forced-scout queue -- these BLOCK new same-class attempts;
  3. every `ceiling-claimed` line, re-challenged in place;
  4. the current WIP approach, if one is open;
  5. dirty working trees across the registered projects.

Always exits 0 -- a SessionStart hook must never block the session.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
APPROACHES = ROOT / "registry" / "approaches.jsonl"
CONFIG = ROOT / "projects.json"


def _load_approaches() -> list[dict]:
    if not APPROACHES.exists():
        return []
    rows = []
    for line in APPROACHES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _run(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return out.stdout.rstrip()
    except Exception:
        return ""


def main() -> int:
    print("DEV-HARNESS: anti-grind gate active.")
    print("  Under momentum an agent tunes variants of a failing idea instead of")
    print("  asking whether the objective is wrong. Prose rules do not stop that.")
    print("  The ledger does: N same-class refutes BLOCK the approach-class and")
    print("  FORCE a different-class scout. Log every approach before you build it.")

    queue = _run([sys.executable, str(SCRIPTS / "ledger.py"), "queue"])
    if queue:
        print("\n--- scout queue (ledger.py queue) ---")
        print(queue)

    rows = _load_approaches()

    wip = [r for r in rows if r.get("status") == "testing"]
    if wip:
        print("\n--- WIP (close it out before opening another) ---")
        for r in wip:
            print(f"  id {r.get('id')} [{r.get('approach_class')}] {r.get('project')}: "
                  f"{r.get('hypothesis', '')}")
    else:
        print("\n--- WIP: none open. Clock-in must open exactly one. ---")

    ceilings = [r for r in rows if r.get("status") == "ceiling-claimed"]
    if ceilings:
        print("\n--- ceiling-claimed RE-CHALLENGE (a ceiling is not a stop) ---")
        for r in ceilings:
            print(f"  id {r.get('id')} [{r.get('approach_class')}] {r.get('project')}: "
                  f"{r.get('hypothesis', '')}")
            print("    -> Did you try the next ORTHOGONAL sub-variant? A DIFFERENT")
            print("       objective or representation? Run /approach-scout, then either")
            print("       open a new row or extend the sub-variant list.")

    # dirty trees in the registered projects
    if CONFIG.exists():
        try:
            projects = json.loads(CONFIG.read_text(encoding="utf-8")).get("projects", [])
        except json.JSONDecodeError:
            projects = []
        dirty = []
        for p in projects:
            loc = (ROOT / p.get("path", "")).resolve()
            if not (loc / ".git").exists():
                continue
            out = _run(["git", "-C", str(loc), "status", "--porcelain"])
            if out:
                dirty.append(p.get("name"))
        if dirty:
            print(f"\nDEV-HARNESS WARNING: dirty working tree in: {', '.join(dirty)}")
            print("  WHY: new scope on an unverified baseline compounds failures.")
            print("  FIX: commit or revert there first, then run the project's check.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
