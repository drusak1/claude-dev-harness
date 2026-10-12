#!/usr/bin/env python3
"""Install the weekly-review hooks into the USER-level Claude Code settings.

User level, because the snapshot must cover sessions in every project, not
only sessions opened inside this harness:

  SessionEnd   -> review.py snapshot   copy the transcript (no LLM, seconds)
  SessionStart -> review.py status     remind about pending decisions / an
                                       overdue review (silent otherwise)

Merges into ~/.claude/settings.json without touching other keys or other
hooks, and is idempotent. Default is a dry run that prints the result.

    python scripts/install_review_hooks.py            # show what would change
    python scripts/install_review_hooks.py --apply    # write it
    python scripts/install_review_hooks.py --remove   # take the hooks out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REVIEW = (Path(__file__).resolve().parent / "review.py").as_posix()
MARK = "review.py"
HOOKS = {
    "SessionEnd": f'python "{REVIEW}" snapshot',
    "SessionStart": f'python "{REVIEW}" status',
}


def _strip(groups: list[dict]) -> list[dict]:
    """Drop our own hook entries; keep everyone else's."""
    out = []
    for g in groups:
        hooks = [h for h in g.get("hooks", [])
                 if MARK not in h.get("command", "")
                 or "claude-dev-harness" not in h.get("command", "")]
        if hooks:
            out.append({**g, "hooks": hooks})
    return out


def merge(settings: dict, remove: bool = False) -> dict:
    hooks = settings.setdefault("hooks", {})
    for event, cmd in HOOKS.items():
        groups = _strip(hooks.get(event, []))
        if not remove:
            groups.append({"hooks": [{"type": "command", "command": cmd,
                                      "timeout": 30}]})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks")
    return settings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--remove", action="store_true")
    p.add_argument("--settings",
                   default=str(Path.home() / ".claude" / "settings.json"))
    args = p.parse_args(argv)

    path = Path(args.settings)
    current = json.loads(path.read_text("utf-8")) if path.exists() else {}
    new = merge(json.loads(json.dumps(current)), remove=args.remove)
    text = json.dumps(new, indent=2) + "\n"
    if not (args.apply or args.remove):
        print(f"dry run -- {path} would become:\n{text}")
        print("re-run with --apply to write it")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
