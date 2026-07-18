#!/usr/bin/env python3
"""Project registry -- the harness works on N repos that live OUTSIDE it.

`projects.json` is the only place that knows where the code is. The harness
repo itself contains no project source, which is what makes it safe to publish
while the projects it drives stay private.

Schema (projects.json):

    {
      "projects": [
        {
          "name": "api",              # stable key used by ledger --project
          "path": "../my-api",        # relative to the harness root, or absolute
          "stack": "python",          # free-form label, for the agent's benefit
          "check": "make check"       # the ONE command that verifies the project
        }
      ]
    }

The contract is `check`: one command, exit 0 = green. Whatever the stack, the
harness only ever needs that. `make check` in the harness verifies the harness;
`make projects-check` runs each project's own `check`.

CLI:
  projects.py list
  projects.py validate            # paths exist and are git repos
  projects.py check [--name N]    # run each project's check command
  projects.py path <name>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "projects.json"


def load_projects() -> list[dict]:
    if not CONFIG.exists():
        raise SystemExit(
            f"projects.json not found at {CONFIG}\n"
            f"  WHY: the harness needs to know which repos it drives.\n"
            f"  FIX: copy projects.example.json to projects.json and edit the paths."
        )
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"projects.json: invalid JSON: {e}")
    projects = data.get("projects")
    if not isinstance(projects, list):
        raise SystemExit("projects.json: top-level key `projects` must be a list")
    return projects


def resolve_path(proj: dict) -> Path:
    return (ROOT / proj.get("path", "")).resolve()


def cmd_list(_args: argparse.Namespace) -> int:
    for p in load_projects():
        loc = resolve_path(p)
        mark = "OK " if loc.exists() else "MISSING"
        print(f"  [{mark}] {p.get('name'):<16} {p.get('stack', '?'):<12} {loc}")
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    for p in load_projects():
        if p.get("name") == args.name:
            print(resolve_path(p))
            return 0
    sys.stderr.write(f"no project named {args.name!r} in projects.json\n")
    return 2


def cmd_validate(_args: argparse.Namespace) -> int:
    problems: list[str] = []
    names: set[str] = set()
    projects = load_projects()
    if not projects:
        print("projects.json: no projects registered yet (that is fine on a fresh clone).")
        return 0
    for p in projects:
        name = p.get("name")
        if not name:
            problems.append("a project entry has no `name`")
            continue
        if name in names:
            problems.append(f"{name}: duplicate name")
        names.add(name)
        if not p.get("check"):
            problems.append(f"{name}: no `check` command -- the harness cannot verify it")
        loc = resolve_path(p)
        if not loc.exists():
            problems.append(f"{name}: path does not exist: {loc}")
        elif not (loc / ".git").exists():
            problems.append(f"{name}: {loc} is not a git repo (no .git)")

    if problems:
        print("projects validate FAILED:")
        for pr in problems:
            print(f"  - {pr}")
        return 1
    print(f"projects OK: {len(projects)} project(s), all paths present and git-tracked.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    failures: list[str] = []
    for p in load_projects():
        name = p.get("name")
        if args.name and name != args.name:
            continue
        loc = resolve_path(p)
        cmd = p.get("check")
        if not cmd:
            failures.append(f"{name}: no check command")
            continue
        if not loc.exists():
            failures.append(f"{name}: path missing ({loc})")
            continue
        print(f"== {name}: {cmd}  (cwd={loc})")
        rc = subprocess.run(cmd, shell=True, cwd=str(loc)).returncode
        if rc != 0:
            failures.append(f"{name}: `{cmd}` exited {rc}")

    if failures:
        print("\nprojects check FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nall project checks passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="projects.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list registered projects").set_defaults(func=cmd_list)
    sub.add_parser("validate", help="paths exist and are git repos").set_defaults(func=cmd_validate)

    c = sub.add_parser("check", help="run each project's check command")
    c.add_argument("--name", default=None)
    c.set_defaults(func=cmd_check)

    pa = sub.add_parser("path", help="print a project's absolute path")
    pa.add_argument("name")
    pa.set_defaults(func=cmd_path)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
