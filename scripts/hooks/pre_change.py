#!/usr/bin/env python3
"""Pre-change gate -- refuse to start work in a BLOCKED approach-class.

Run this before starting an implementation, not after. It exits NONZERO
(blocking) iff:

  * registry/queue.jsonl has a pending forced-scout / ceiling item, AND
  * the approach-class you are about to work in is one of the blocked ones.

The intended class is read from argv[1], else env CDH_CLASS. If neither is
given the gate is conservative: it blocks while ANY scout is pending, because
it cannot prove the new work is in a different class.

Exit 0 = proceed. Exit 2 = blocked (resolve the scout first).

Usage:
    python scripts/hooks/pre_change.py "<approach-class>"
    CDH_CLASS="<approach-class>" python scripts/hooks/pre_change.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
QUEUE = ROOT / "registry" / "queue.jsonl"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    rows = []
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    intended = (argv[0] if argv else os.environ.get("CDH_CLASS", "")).strip()

    scouts = [q for q in _load_queue()
              if q.get("type") in ("forced-scout", "ceiling-rechallenge")]
    if not scouts:
        return 0

    blocked = {_norm(q.get("class_blocked", "")) for q in scouts}

    def block(reason: str) -> int:
        sys.stderr.write("pre_change BLOCKED: a forced scout is pending.\n")
        sys.stderr.write(f"  {reason}\n  Pending items:\n")
        for q in scouts:
            sys.stderr.write(
                f"    [{q.get('type')}] blocked-class='{q.get('class_blocked')}' "
                f"project={q.get('created_for')} :: {q.get('reason')}\n"
            )
        sys.stderr.write(
            "  FIX: run /approach-scout and register a DIFFERENT-class row via\n"
            "       `ledger.py add`, OR start work in a non-blocked class. You cannot\n"
            "       keep grinding the blocked one. The block is mechanical, not a debate.\n"
        )
        return 2

    if not intended:
        return block(
            "No approach-class given (argv[1] / CDH_CLASS). Cannot prove this work is "
            "in a DIFFERENT class, so it is blocked."
        )
    if _norm(intended) in blocked:
        return block(f"Intended class '{intended}' is BLOCKED by a pending scout.")

    print(
        f"pre_change OK: '{intended}' is not a blocked class "
        f"(a scout is still pending -- working here counts as addressing it)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
