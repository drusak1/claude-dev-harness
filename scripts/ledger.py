#!/usr/bin/env python3
"""Approach-Ledger CLI -- the anti-grind mechanism.

Tracks every approach an agent takes, across every project, in
registry/approaches.jsonl (one JSON object per line), and enforces the
structural guards that prose rules fail to enforce:

  * no silent re-try of a refuted/ceiling-claimed
    (approach_class, objective, hypothesis) signature;
  * N same-class refutes -> BLOCK the approach-class + FORCE a different-class
    scout item onto registry/queue.jsonl;
  * `ceiling-claimed` is a gated artifact (must enumerate orthogonal
    sub-variants + a null/control result) that auto-emits a scout item -- it
    never ends work;
  * banned stop-reason words are rejected as a closing `why`.

Pure stdlib. No dependencies, no network, no state outside registry/.

CLI (pinned -- every harness component agrees on this contract):

  ledger.py add --project P --class C --objective O --hypothesis H
                --source {failure-correlated|descriptive} [--why TEXT]
  ledger.py set-status <id> <untested|testing|works|refuted|ceiling-claimed>
                [--evidence JSON] [--why TEXT]
                [--sub-variants JSON] [--control JSON]   # for ceiling-claimed
  ledger.py list [--project P] [--status S]
  ledger.py check
  ledger.py queue
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry"
APPROACHES = REGISTRY / "approaches.jsonl"
QUEUE = REGISTRY / "queue.jsonl"

STATUSES = ("untested", "testing", "works", "refuted", "ceiling-claimed")
SOURCES = ("failure-correlated", "descriptive")
TERMINAL_NEGATIVE = ("refuted", "ceiling-claimed")

# Evidence tiers, weakest to strongest. A refute must name the tier that
# produced it -- see docs/DISCIPLINES.md rule 9.
GATE_TIERS = ("local-test", "integration", "e2e", "production")

# Closing-`why` words banned as a stop-reason. `ceiling-claimed` (a gated,
# auto-reopened status) is the ONLY legal "stuck" state.
#
# The first five are generic defeatism. The last three are the development-
# specific forms of the same move: closing a line by relocating the cause
# outside the code instead of explaining the failed mechanism.
BANNED_STOP_WORDS = (
    "ceiling",
    "impossible",
    "exhausted",
    "-ev",
    "rational-stop",
    "works-on-my-machine",
    "environment-issue",
    "wontfix",
)
# Whole-token match, so "exhaustive" in prose is not flagged. Only the closing
# line of a `refuted` entry's `why` is ever scanned.
_BANNED_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(w) for w in BANNED_STOP_WORDS) + r")(?![A-Za-z])",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# storage helpers
# --------------------------------------------------------------------------- #
def _ensure_registry() -> None:
    REGISTRY.mkdir(parents=True, exist_ok=True)


def _load_jsonl(path: Path, label: str) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{label}: unparseable line {n}: {e}")
    return rows


def load_approaches() -> list[dict]:
    return _load_jsonl(APPROACHES, "approaches.jsonl")


def load_queue() -> list[dict]:
    return _load_jsonl(QUEUE, "queue.jsonl")


def _append_jsonl(path: Path, obj: dict) -> None:
    _ensure_registry()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _rewrite_approaches(rows: list[dict]) -> None:
    _ensure_registry()
    with APPROACHES.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# signatures / threshold
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def signature(row: dict) -> tuple[str, str, str]:
    return (
        _norm(row.get("approach_class", "")),
        _norm(row.get("objective", "")),
        _norm(row.get("hypothesis", "")),
    )


def refute_threshold() -> int:
    """N = 3 by default; override with CDH_REFUTE_N.

    Lower it (2) when you want the harness to force a re-frame sooner -- e.g. a
    time-boxed spike where breadth beats depth."""
    raw = os.environ.get("CDH_REFUTE_N")
    if raw:
        try:
            n = int(raw)
            if n >= 1:
                return n
        except ValueError:
            pass
    return 3


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_add(args: argparse.Namespace) -> int:
    rows = load_approaches()
    new_sig = (_norm(args.approach_class), _norm(args.objective), _norm(args.hypothesis))
    for r in rows:
        if signature(r) == new_sig and r.get("status") in TERMINAL_NEGATIVE:
            sys.stderr.write(
                f"REJECTED: signature already {r['status']} as id {r['id']} "
                f"(class/objective/hypothesis match).\n"
                f"  WHY: a {r['status']} signature must not be silently re-tried.\n"
                f"  prior why: {r.get('why', '(none)')}\n"
                f"  FIX: change the objective or the representation (a DIFFERENT "
                f"approach-class row), or run `ledger.py queue` for the forced scout.\n"
            )
            return 2

    next_id = max((r.get("id", 0) for r in rows), default=0) + 1
    entry = {
        "id": next_id,
        "project": args.project,
        "approach_class": args.approach_class,
        "objective": args.objective,
        "hypothesis": args.hypothesis,
        "status": "untested",
        "evidence": [],
        "why": f"[{date.today().isoformat()}] {args.why}" if args.why else "",
        "source": args.source,
        "created": date.today().isoformat(),
    }
    _append_jsonl(APPROACHES, entry)
    print(f"added id {next_id} [{args.approach_class}] status=untested source={args.source}")
    if args.source == "descriptive":
        print(
            "  NOTE: source=descriptive. It may NOT be promoted to a build without a\n"
            "        failure-correlation artifact (a repro/log/metric showing this\n"
            "        pattern in OUR OWN failures). See docs/DISCIPLINES.md rule 1."
        )
    return 0


def _parse_json_arg(name: str, raw: str | None):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"REJECTED: --{name} must be valid JSON: {e}\n")
        raise SystemExit(2)


def _evidence_has_gate_tier(evidence) -> bool:
    if not evidence:
        return False
    items = evidence if isinstance(evidence, list) else [evidence]
    return any(isinstance(it, dict) and it.get("gate_tier") for it in items)


def _append_why(row: dict, why: str) -> None:
    """`why` is append-only: a new verdict adds a dated line, never overwrites."""
    line = f"[{date.today().isoformat()}] {why}"
    cur = row.get("why")
    row["why"] = f"{cur}\n{line}" if cur else line


def cmd_set_status(args: argparse.Namespace) -> int:
    rows = load_approaches()
    target = next((r for r in rows if r.get("id") == args.id), None)
    if target is None:
        sys.stderr.write(f"REJECTED: no approach with id {args.id}\n")
        return 2

    evidence = _parse_json_arg("evidence", args.evidence)
    sub_variants = _parse_json_arg("sub-variants", args.sub_variants)
    control = _parse_json_arg("control", args.control)

    # WIP = 1: at most one approach may be `testing` at a time.
    if args.status == "testing":
        others = [
            r for r in rows
            if r.get("status") == "testing" and r.get("id") != args.id
        ]
        if others:
            ids = ", ".join(str(r.get("id")) for r in others)
            sys.stderr.write(
                f"REJECTED: WIP=1 violated -- id {ids} already `testing`.\n"
                f"  WHY: breadth comes from the scout queue, not from juggling "
                f"half-tested approaches.\n"
                f"  FIX: close out id {ids} first (works/refuted/ceiling-claimed).\n"
            )
            return 2

    # A refute is only a refute if a measured tier produced it.
    if args.status == "refuted" and not _evidence_has_gate_tier(evidence):
        sys.stderr.write(
            "REJECTED: refuted requires --evidence carrying a gate_tier.\n"
            f"  tiers: {GATE_TIERS}\n"
            '  e.g. --evidence \'[{"date":"2026-07-18","cmd":"make test",'
            '"result":"3 failing -> still 3 failing","gate_tier":"local-test"}]\'\n'
        )
        return 2

    # ceiling-claimed is a GATED artifact: it must enumerate orthogonal
    # sub-variants + a null/control. It auto-emits a scout item; never a stop.
    if args.status == "ceiling-claimed":
        sv = sub_variants if sub_variants is not None else target.get("sub_variants")
        ctrl = control if control is not None else target.get("control")
        if not (isinstance(sv, (list, tuple)) and len(sv) >= 1):
            sys.stderr.write(
                "REJECTED: ceiling-claimed requires --sub-variants (>=1 orthogonal "
                "sub-variant actually tried).\n"
                "  WHY: a ceiling claim is credible only after orthogonal variants "
                "were tried under a control.\n"
            )
            return 2
        if not ctrl:
            sys.stderr.write(
                "REJECTED: ceiling-claimed requires --control -- a null/oracle result "
                "showing the limit is real and not ours\n"
                "  (e.g. a minimal repro outside our code that hits the same wall).\n"
            )
            return 2

    if args.why is not None:
        _append_why(target, args.why)
    if evidence is not None:
        cur = target.get("evidence")
        if not isinstance(cur, list):
            cur = []
        cur.extend(evidence if isinstance(evidence, list) else [evidence])
        target["evidence"] = cur
    if sub_variants is not None:
        target["sub_variants"] = sub_variants
    if control is not None:
        target["control"] = control

    prev_status = target.get("status")
    target["status"] = args.status
    _rewrite_approaches(rows)
    print(f"id {args.id}: {prev_status} -> {args.status}")

    if args.status == "refuted":
        _on_refute(rows, target)
    elif args.status == "ceiling-claimed":
        _on_ceiling(target)
    return 0


def _on_refute(rows: list[dict], target: dict) -> None:
    klass = _norm(target.get("approach_class", ""))
    n = refute_threshold()
    count = sum(
        1 for r in rows
        if _norm(r.get("approach_class", "")) == klass and r.get("status") == "refuted"
    )
    print(f"  approach-class '{target.get('approach_class')}' refute-count={count} (N={n})")
    if count < n:
        return

    for r in rows:
        if _norm(r.get("approach_class", "")) == klass:
            r["class_blocked"] = True
    _rewrite_approaches(rows)

    item = {
        "type": "forced-scout",
        "class_blocked": target.get("approach_class"),
        "reason": f"{count} same-class refutes (>= N={n})",
        "created_for": target.get("project"),
        "created": date.today().isoformat(),
    }
    if _queue_has(item):
        print(f"  >> class '{target.get('approach_class')}' already blocked (scout pending).")
        return
    _append_jsonl(QUEUE, item)
    print(
        f"  >> APPROACH-CLASS BLOCKED: '{target.get('approach_class')}'.\n"
        f"     Forced scout queued (`ledger.py queue`). Before the next attempt, ask\n"
        f"     whether the OBJECTIVE is wrong -- not which variant to try next."
    )


def _on_ceiling(target: dict) -> None:
    item = {
        "type": "ceiling-rechallenge",
        "class_blocked": target.get("approach_class"),
        "reason": f"ceiling-claimed on id {target.get('id')} -- auto-reopen via scout",
        "created_for": target.get("project"),
        "created": date.today().isoformat(),
    }
    if _queue_has(item):
        return
    _append_jsonl(QUEUE, item)
    print(
        "  >> ceiling-claimed is NOT a stop. Scout queued (`ledger.py queue`):\n"
        "     next session must try a different objective or representation."
    )


def _queue_has(item: dict) -> bool:
    for q in load_queue():
        if (
            q.get("type") == item.get("type")
            and _norm(q.get("class_blocked", "")) == _norm(item.get("class_blocked", ""))
            and q.get("created_for") == item.get("created_for")
        ):
            return True
    return False


def cmd_list(args: argparse.Namespace) -> int:
    rows = load_approaches()
    if args.project:
        rows = [r for r in rows if r.get("project") == args.project]
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if not rows:
        print("(no matching approaches)")
        return 0
    for r in rows:
        blocked = " BLOCKED" if r.get("class_blocked") else ""
        print(
            f"  id {r.get('id'):>3} [{r.get('status'):<15}] {r.get('project')} "
            f"/ {r.get('approach_class')}{blocked}"
        )
        print(f"        {r.get('hypothesis', '')}")
    return 0


def cmd_queue(_args: argparse.Namespace) -> int:
    q = load_queue()
    if not q:
        print("queue: (empty) -- no pending forced-scout / ceiling items.")
        return 0
    print(f"queue: {len(q)} pending item(s):")
    for item in q:
        print(
            f"  [{item.get('type')}] blocked-class='{item.get('class_blocked')}' "
            f"project={item.get('created_for')} :: {item.get('reason')}"
        )
    print("\nAddress these BEFORE starting another approach in a blocked class.")
    print("A forced-scout requires a DIFFERENT approach-class row "
          "(see .claude/skills/approach-scout).")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    """Consistency gate. Exits nonzero on any structural violation."""
    problems: list[str] = []

    try:
        rows = load_approaches()
        load_queue()
    except SystemExit as e:
        print(f"FAIL: {e}")
        return 1

    testing = [r for r in rows if r.get("status") == "testing"]
    if len(testing) > 1:
        ids = ", ".join(str(r.get("id")) for r in testing)
        problems.append(f"WIP=1 violated: ids {ids} are all `testing`")

    seen_ids: set[int] = set()
    for r in rows:
        rid = r.get("id", "?")
        status = r.get("status")

        if rid in seen_ids:
            problems.append(f"id {rid}: duplicate id")
        if isinstance(rid, int):
            seen_ids.add(rid)

        if status not in STATUSES:
            problems.append(f"id {rid}: invalid status {status!r}")
        if not _norm(r.get("approach_class", "")):
            problems.append(f"id {rid}: missing approach_class (the N-refute counter "
                            f"aggregates on it -- an untagged row makes a grind invisible)")
        if r.get("source") and r["source"] not in SOURCES:
            problems.append(f"id {rid}: invalid source {r['source']!r}")

        # Banned stop-reason in the CLOSING `why` of a refute. Non-terminal rows
        # and `ceiling-claimed` (the sanctioned, gated stuck state) are exempt --
        # they legitimately discuss ceilings.
        if status == "refuted":
            why = (r.get("why") or "").strip()
            closing = why.splitlines()[-1] if why else ""
            m = _BANNED_RE.search(closing)
            if m:
                problems.append(
                    f"id {rid}: banned stop-reason '{m.group(0)}' in closing why -- "
                    f"a refute must explain the failed MECHANISM, not declare the line "
                    f"dead. The only legal stuck state is status='ceiling-claimed', "
                    f"which is gated and auto-reopened."
                )

        if status == "refuted" and not _evidence_has_gate_tier(r.get("evidence")):
            problems.append(
                f"id {rid}: refuted without evidence.gate_tier -- an unmeasured "
                f"refutation is not a refutation."
            )

        if status == "ceiling-claimed":
            sv = r.get("sub_variants")
            if not (isinstance(sv, list) and len(sv) >= 1):
                problems.append(f"id {rid}: ceiling-claimed without sub-variant enumeration")
            if not r.get("control"):
                problems.append(f"id {rid}: ceiling-claimed without a null/control result")

    if problems:
        print("ledger check FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"ledger OK: {len(rows)} approach(es), WIP<=1, no banned stop-reasons, "
        f"all refutes/ceilings well-formed."
    )
    return 0


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledger.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="register a new approach (signature-checked)")
    a.add_argument("--project", required=True, help="project name from projects.json")
    a.add_argument("--class", dest="approach_class", required=True,
                   help="approach-class tag from registry/approach-classes.md")
    a.add_argument("--objective", required=True, help="what outcome this optimizes")
    a.add_argument("--hypothesis", required=True, help="concrete, testable claim")
    a.add_argument("--source", required=True, choices=SOURCES)
    a.add_argument("--why", default=None)
    a.set_defaults(func=cmd_add)

    s = sub.add_parser("set-status", help="update status (+ fire triggers)")
    s.add_argument("id", type=int)
    s.add_argument("status", choices=STATUSES)
    s.add_argument("--evidence", default=None,
                   help="JSON list/obj; required (with gate_tier) for refuted")
    s.add_argument("--why", default=None, help="append-only dated verdict line")
    s.add_argument("--sub-variants", dest="sub_variants", default=None,
                   help="JSON list of orthogonal sub-variants (ceiling-claimed)")
    s.add_argument("--control", default=None,
                   help="JSON null/control result (ceiling-claimed)")
    s.set_defaults(func=cmd_set_status)

    ls = sub.add_parser("list", help="list approaches")
    ls.add_argument("--project", default=None)
    ls.add_argument("--status", default=None, choices=STATUSES)
    ls.set_defaults(func=cmd_list)

    c = sub.add_parser("check", help="consistency gate (nonzero on violation)")
    c.set_defaults(func=cmd_check)

    q = sub.add_parser("queue", help="show pending forced-scout / ceiling items")
    q.set_defaults(func=cmd_queue)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
