#!/usr/bin/env python3
"""Weekly review loop -- the evaluator side of instruction self-improvement.

The agent proposes changes to its own instructions (review/rules.md); the user
decides. This script is the part the proposer must NOT be able to bend: it
extracts the correction signals deterministically, audits existing rules by
their own falsifiable predictions, and gates the report.

  review.py collect [--week YYYY-Www] [--source DIR]
      Copy the week's Claude Code transcripts into review/sessions/<week>/raw/
      (Claude Code deletes transcripts after cleanupPeriodDays, default 30) and
      write digest.jsonl: one line per signal -- user-msg (with a correction
      hint and the preceding assistant text), interrupt, tool-denied,
      tool-error. Every signal carries a `ref` = <raw file>:<line>.
  review.py audit [--week YYYY-Www] [--json]
      Per active rule: how often the correction it targets (predicts_re) still
      appears, how often its scope came up (trigger_re), and corrections inside
      its scope (possible side effect) -- this week vs. earlier weeks.
  review.py check
      Gate over rules.md, rejected.md and reports/*.md. Nonzero on violation.

  review.py snapshot            (user-level SessionEnd hook; JSON on stdin)
      Copy the ending session's transcript into review/sessions/_live/ so it
      survives Claude Code's cleanup. Never fails the session.
  review.py status [--today YYYY-MM-DD]   (user-level SessionStart hook)
      Print a reminder iff a report awaits the user's decision or last week's
      review was not written. Silent otherwise.

Sources of transcripts: every --source given, else env CDH_SESSIONS_SRC, else
~/.claude/projects + review/sessions/_live (every project; none special-cased).

Pure stdlib. No network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "review"
SESSIONS = REVIEW / "sessions"
LIVE = SESSIONS / "_live"
REPORTS = REVIEW / "reports"
RULES = REVIEW / "rules.md"
REJECTED = REVIEW / "rejected.md"

MAX_ITEMS = 5
RULE_STATUSES = {"active", "questioned", "quarantined"}
RULE_REQUIRED = ("rule", "scope", "hypothesis", "predicts_re", "at_risk",
                 "target", "evidence", "added", "last_hit", "status")
ITEM_KINDS = {"new", "questioned", "remove"}
SURFACES = {"prose", "skill", "hook", "check"}
DECISIONS = {"pending", "accepted", "rejected", "modified"}

# Harness-generated user turns: not something the user typed.
NOISE_PREFIXES = (
    "<", "Base directory for this skill", "Continue from where you left off",
    "I hit my usage limit", "Caveat:",
)
INTERRUPT_PREFIX = "[Request interrupted"
# Only the head of a message is matched: corrections are said up front, and a
# long pasted log or writeup would otherwise trip on words deep inside it.
HINT_HEAD = 300
CORRECTION_RE = re.compile(
    r"^\s*(нет|не надо|стоп|no\b|nope|stop|wrong)"
    r"|не так|не то\b|не это|я же (просил|говорил|сказал)|я просил"
    r"|опять|снова|зачем ты|почему ты|откати|верни как было"
    r"|то есть ты|ты (сначала|вообще|даже)|пропускаешь|\d+ раз\b"
    r"|бля|ахуе|нахуя|долба|пиздец|wtf"
    r"|not what i|i (said|asked)|don'?t do|that'?s wrong|revert|undo",
    re.IGNORECASE)
RETRY_RE = re.compile(r"^\s*(try again|retry|ещё раз|еще раз|повтори)\b",
                      re.IGNORECASE)
REF_RE = re.compile(r"[\w.\-]+__[\w.\-]+\.jsonl:\d+")


# ----------------------------------------------------------------- utilities
def _sha_self() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


def _week_bounds(week: str) -> tuple[dt.datetime, dt.datetime]:
    m = re.fullmatch(r"(\d{4})-W(\d{2})", week)
    if not m:
        raise SystemExit(f"REJECTED: week {week!r} is not YYYY-Www.\n"
                         "  FIX: e.g. --week 2026-W41")
    start = dt.datetime.combine(
        dt.date.fromisocalendar(int(m[1]), int(m[2]), 1), dt.time(),
        tzinfo=dt.timezone.utc)
    return start, start + dt.timedelta(days=7)


def _prev_week(today: dt.date | None = None) -> str:
    y, w, _ = ((today or dt.date.today()) - dt.timedelta(days=7)).isocalendar()
    return f"{y}-W{w:02d}"


def _ts(rec: dict) -> dt.datetime | None:
    raw = rec.get("timestamp")
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def _flat(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(_flat(b.get("text", b.get("content", "")))
                        if isinstance(b, dict) else str(b) for b in content)
    return str(content or "")


def _clip(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


# ------------------------------------------------------------------- collect
def _repeat_of(key: str, seen: dict[str, str]) -> str | None:
    """An earlier request this one restates: same text, or one extends the
    other (re-asked after an interrupt, with a clause added)."""
    if len(key) < 12:
        return None
    for prev, ref in seen.items():
        if len(prev) >= 12 and (key.startswith(prev) or prev.startswith(key)):
            return ref
    return None


def _scan(path: Path, raw_name: str, start, end) -> tuple[list[dict], bool]:
    """Signals from one transcript, and whether anything fell in the window."""
    signals: list[dict] = []
    tool_names: dict[str, str] = {}
    prev_assistant = ""
    seen_requests: dict[str, str] = {}
    in_window = False
    project_dir = raw_name.split("__", 1)[0]

    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("isSidechain"):
                continue
            kind = rec.get("type")
            content = (rec.get("message") or {}).get("content")
            ts = _ts(rec)
            here = ts is not None and start <= ts < end
            in_window = in_window or here

            if kind == "assistant":
                if rec.get("isApiErrorMessage"):
                    continue
                for b in content if isinstance(content, list) else []:
                    if b.get("type") == "tool_use":
                        tool_names[b.get("id", "")] = b.get("name", "?")
                    elif b.get("type") == "text" and b.get("text", "").strip():
                        prev_assistant = b["text"]
                continue
            if kind != "user" or not here or rec.get("isMeta"):
                continue

            base = {
                "ref": f"{raw_name}:{lineno}",
                "project": Path(rec.get("cwd") or project_dir).name,
                "ts": rec.get("timestamp"),
            }
            blocks = (content if isinstance(content, list)
                      else [{"type": "text", "text": content or ""}])
            for b in blocks:
                if b.get("type") == "tool_result":
                    if rec.get("toolDenialKind"):
                        k = "tool-denied"
                    elif b.get("is_error"):
                        k = "tool-error"
                    else:
                        continue
                    signals.append({**base, "kind": k,
                                    "tool": tool_names.get(
                                        b.get("tool_use_id", ""), "?"),
                                    "text": _clip(_flat(b.get("content")), 300)})
                    continue
                text = b.get("text", "") if b.get("type") == "text" else ""
                if not text.strip():
                    continue
                if text.startswith(INTERRUPT_PREFIX):
                    signals.append({**base, "kind": "interrupt", "text": text,
                                    "prev_assistant": _clip(prev_assistant, 400)})
                    continue
                if text.lstrip().startswith(NOISE_PREFIXES):
                    continue
                key = _norm(text)[:100]
                signals.append({
                    **base, "kind": "user-msg", "text": _clip(text, 600),
                    "prev_assistant": _clip(prev_assistant, 400),
                    "correction_hint": bool(
                        CORRECTION_RE.search(text[:HINT_HEAD])),
                    "retry_hint": bool(RETRY_RE.search(text)),
                    "repeat_of": _repeat_of(key, seen_requests),
                })
                seen_requests.setdefault(key, base["ref"])
    return signals, in_window


def cmd_collect(args) -> int:
    week = args.week or _prev_week()
    start, end = _week_bounds(week)
    if args.source:
        sources = [Path(x) for x in args.source]
    elif os.environ.get("CDH_SESSIONS_SRC"):
        sources = [Path(os.environ["CDH_SESSIONS_SRC"])]
    else:
        sources = [Path.home() / ".claude" / "projects", LIVE]
    sources = [x for x in sources if x.is_dir()]
    if not sources:
        print("REJECTED: no transcript source exists.\n"
              "  FIX: pass --source DIR or set CDH_SESSIONS_SRC.",
              file=sys.stderr)
        return 1
    # One session can exist in several sources (original + SessionEnd
    # snapshot); the longer copy is the more complete one.
    candidates: dict[str, Path] = {}
    for src in sources:
        for path in src.glob("*/*.jsonl"):
            name = f"{path.parent.name}__{path.name}"
            if (name not in candidates
                    or path.stat().st_size > candidates[name].stat().st_size):
                candidates[name] = path
    out = SESSIONS / week
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    signals: list[dict] = []
    files: list[str] = []
    for raw_name, path in sorted(candidates.items()):
        sig, in_window = _scan(path, raw_name, start, end)
        if not in_window:
            continue
        shutil.copy2(path, raw_dir / raw_name)
        files.append(raw_name)
        signals.extend(sig)

    with open(out / "digest.jsonl", "w", encoding="utf-8") as f:
        for s in signals:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    counts: dict[str, int] = {}
    for s in signals:
        k = s["kind"] + ("+correction" if s.get("correction_hint") else "")
        counts[k] = counts.get(k, 0) + 1
    meta = {"week": week, "sources": [str(x) for x in sources], "collector_sha": _sha_self(),
            "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "files": files, "counts": counts}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), "utf-8")
    print(f"collected {week}: {len(files)} transcript(s), "
          f"{len(signals)} signal(s) -> {out / 'digest.jsonl'}")
    for k, v in sorted(counts.items()):
        print(f"  {k:24} {v}")
    return 0


# -------------------------------------------------------------- md parsing
def _blocks(path: Path, level: str, id_re: str) -> list[dict]:
    """`<level> ID` headings followed by `- key: value` lines."""
    if not path.exists():
        return []
    items: list[dict] = []
    cur: dict | None = None
    in_fence = False
    for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if line.startswith("```"):
            in_fence = not in_fence
            if cur is not None:
                cur["_has_diff"] = cur.get("_has_diff") or "diff" in line
            continue
        if in_fence:
            continue
        m = re.match(rf"^{level} ({id_re})\b", line)
        if m:
            cur = {"_id": m[1], "_line": n}
            items.append(cur)
            continue
        kv = re.match(r"^- (\w+):\s*(.*)$", line)
        if kv and cur is not None:
            cur[kv[1]] = kv[2].strip()
    return items


def load_rules() -> list[dict]:
    return _blocks(RULES, "###", r"R-\d{3,}")


def load_rejected() -> list[dict]:
    return _blocks(REJECTED, "###", r"X-\d{3,}")


def _load_digests() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for d in sorted(SESSIONS.glob("*/digest.jsonl")) if SESSIONS.exists() else []:
        out[d.parent.name] = [json.loads(l) for l in
                              d.read_text("utf-8").splitlines() if l.strip()]
    return out


def _similar(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.8


# --------------------------------------------------------------------- audit
def cmd_audit(args) -> int:
    week = args.week or _prev_week()
    digests = _load_digests()
    if week not in digests:
        print(f"REJECTED: no digest for {week}.\n"
              f"  FIX: python scripts/review.py collect --week {week}",
              file=sys.stderr)
        return 1
    result: dict[str, dict] = {}
    for r in load_rules():
        if r.get("status") == "quarantined":
            continue
        pred = re.compile(r.get("predicts_re", "(?!)"), re.IGNORECASE)
        trig = re.compile(r["trigger_re"], re.IGNORECASE) \
            if r.get("trigger_re") else None
        row = {"status": r.get("status"), "history": {}}
        for wk, sigs in digests.items():
            msgs = [s for s in sigs if s["kind"] == "user-msg"]
            p = [s["ref"] for s in msgs if pred.search(s["text"])]
            t = [s for s in msgs if trig and trig.search(s["text"])]
            sc = [s["ref"] for s in t if s.get("correction_hint")]
            row["history"][wk] = {"predicted": len(p), "trigger": len(t),
                                  "scope_corrections": len(sc)}
            if wk == week:
                row.update(predicted_hits=len(p), predicted_refs=p,
                           trigger_hits=len(t), scope_correction_refs=sc,
                           last_trigger=max((s["ts"] for s in t), default=None))
        result[r["_id"]] = row
        h = " ".join(f"{wk}:{v['predicted']}/{v['trigger']}"
                     for wk, v in row["history"].items())
        print(f"{r['_id']} [{r.get('status')}] predicted/trigger by week: {h}")
        if row["predicted_hits"]:
            print(f"   still happening -> 'не работает'? {row['predicted_refs']}")
        if row["scope_correction_refs"]:
            print(f"   corrections in scope -> side effect? "
                  f"{row['scope_correction_refs']}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------- check
def _check_rules(errors: list[str]) -> set[str]:
    ids: set[str] = set()
    for r in load_rules():
        where = f"rules.md:{r['_line']} {r['_id']}"
        if r["_id"] in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(r["_id"])
        for k in RULE_REQUIRED:
            if not r.get(k):
                errors.append(f"{where}: missing `{k}` (every rule needs a "
                              "falsifiable hypothesis and its evidence)")
        if r.get("status") and r["status"] not in RULE_STATUSES:
            errors.append(f"{where}: status {r['status']!r} not in "
                          f"{sorted(RULE_STATUSES)}")
        for k in ("predicts_re", "trigger_re"):
            if r.get(k):
                try:
                    re.compile(r[k])
                except re.error as e:
                    errors.append(f"{where}: `{k}` is not a valid regex: {e}")
    return ids


def _check_report(path: Path, rule_ids: set[str], rejected: list[dict],
                  digests: dict[str, list[dict]], errors: list[str],
                  notes: list[str]) -> None:
    week = path.stem
    text = path.read_text("utf-8")
    items = _blocks(path, "##", r"P\d+")
    name = f"reports/{path.name}"
    if len(items) > MAX_ITEMS:
        errors.append(f"{name}: {len(items)} items; the cap is {MAX_ITEMS} "
                      "(rank by importance and cut)")

    meta_path = SESSIONS / week / "meta.json"
    known_refs = {s["ref"] for sigs in digests.values() for s in sigs}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text("utf-8"))
        m = re.search(r"^collector_sha:\s*(\S+)", text, re.MULTILINE)
        if not m or m[1] != meta["collector_sha"]:
            errors.append(f"{name}: collector_sha does not match the digest "
                          f"for {week} ({meta['collector_sha']}); the report "
                          "was not built on this week's collector output")
        if meta["collector_sha"] != _sha_self():
            notes.append(f"WARN {name}: scripts/review.py changed since "
                         f"{week} was collected")
    else:
        notes.append(f"SKIP {name}: no digest for {week} on this machine; "
                     "evidence refs not resolved")

    surfaces = []
    for it in items:
        where = f"{name}:{it['_line']} {it['_id']}"
        kind = it.get("kind")
        if kind not in ITEM_KINDS:
            errors.append(f"{where}: kind {kind!r} not in {sorted(ITEM_KINDS)}")
            continue
        need = ["decision", "evidence", "mechanism"]
        need += (["rule", "scope", "hypothesis", "predicts_re", "at_risk",
                  "surface"] if kind == "new" else ["rule_id"])
        for k in need:
            if not it.get(k):
                errors.append(f"{where}: missing `{k}`")
        if not it.get("_has_diff"):
            errors.append(f"{where}: no ```diff block (every item ships a "
                          "ready diff)")
        if it.get("decision") and it["decision"] not in DECISIONS:
            errors.append(f"{where}: decision {it['decision']!r} not in "
                          f"{sorted(DECISIONS)}")
        if it.get("surface"):
            if it["surface"] not in SURFACES:
                errors.append(f"{where}: surface {it['surface']!r} not in "
                              f"{sorted(SURFACES)}")
            surfaces.append(it["surface"])
        if it.get("predicts_re"):
            try:
                re.compile(it["predicts_re"])
            except re.error as e:
                errors.append(f"{where}: predicts_re invalid: {e}")
        if kind != "new" and it.get("rule_id") and it["rule_id"] not in rule_ids:
            errors.append(f"{where}: rule_id {it['rule_id']} not in rules.md")
        refs = REF_RE.findall(it.get("evidence", ""))
        if it.get("evidence") and not refs:
            errors.append(f"{where}: evidence has no <file>__<id>.jsonl:<line> "
                          "ref from a digest")
        if meta_path.exists():
            for ref in refs:
                if ref not in known_refs:
                    errors.append(f"{where}: evidence ref {ref} not found in "
                                  "any digest")
        if kind == "new" and it.get("rule"):
            for x in rejected:
                if x.get("rule") and _similar(it["rule"], x["rule"]):
                    errors.append(f"{where}: matches rejected {x['_id']} "
                                  f"({x.get('reason', 'no reason')}); do not "
                                  "re-propose a rejected rule")
    if len(surfaces) >= 3 and set(surfaces) == {"prose"}:
        notes.append(f"WARN {name}: every item is prose; prefer a check/hook "
                     "for anything that recurs (docs/DISCIPLINES.md)")


def cmd_check(_args) -> int:
    errors: list[str] = []
    notes: list[str] = []
    rule_ids = _check_rules(errors)
    rejected = load_rejected()
    for x in rejected:
        for k in ("rule", "reason", "date"):
            if not x.get(k):
                errors.append(f"rejected.md:{x['_line']} {x['_id']}: "
                              f"missing `{k}`")
    digests = _load_digests()
    for path in sorted(REPORTS.glob("*.md")) if REPORTS.exists() else []:
        _check_report(path, rule_ids, rejected, digests, errors, notes)
    for n in notes:
        print(n)
    if errors:
        print("REJECTED: review state is inconsistent.")
        for e in errors:
            print(f"  - {e}")
        print("  FIX: correct the rule/report fields above; see "
              "review/README.md for the format.")
        return 1
    print(f"review ok: {len(rule_ids)} rule(s), {len(rejected)} rejected")
    return 0


# --------------------------------------------------------------------- hooks
def cmd_snapshot(_args) -> int:
    """SessionEnd: copy the transcript. Any failure is swallowed -- a hook
    must never break the user's session."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        path = Path(payload["transcript_path"])
        dest = LIVE / path.parent.name / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    except Exception as e:  # noqa: BLE001
        print(f"review snapshot skipped: {e}", file=sys.stderr)
    return 0


def cmd_status(args) -> int:
    """SessionStart: one reminder block, or nothing."""
    try:
        today = (dt.date.fromisoformat(args.today) if args.today
                 else dt.date.today())
        lines = []
        for path in sorted(REPORTS.glob("*.md")) if REPORTS.exists() else []:
            pending = [it["_id"] for it in _blocks(path, "##", r"P\d+")
                       if it.get("decision") == "pending"]
            if pending:
                lines.append(f"  review {path.stem}: {len(pending)} item(s) "
                             f"await the user's decision ({', '.join(pending)})"
                             " -> ask accept/reject/modify, then /review-apply")
        week = _prev_week(today)
        if not (REPORTS / f"{week}.md").exists():
            lines.append(f"  /weekly-review for {week} not done -> offer to "
                         "run it (it only proposes; nothing is applied)")
        if lines:
            print("WEEKLY-REVIEW (claude-dev-harness):")
            print("\n".join(lines))
    except Exception as e:  # noqa: BLE001
        print(f"review status skipped: {e}", file=sys.stderr)
    return 0


# ----------------------------------------------------------------------- cli
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="review.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="copy transcripts + build the digest")
    c.add_argument("--week")
    c.add_argument("--source", action="append")
    a = sub.add_parser("audit", help="audit rules against the digests")
    a.add_argument("--week")
    a.add_argument("--json", action="store_true")
    sub.add_parser("check", help="gate rules / rejected / reports")
    sub.add_parser("snapshot", help="SessionEnd hook: copy the transcript")
    st = sub.add_parser("status", help="SessionStart hook: pending reminders")
    st.add_argument("--today")
    args = p.parse_args(argv)
    return {"collect": cmd_collect, "audit": cmd_audit, "check": cmd_check,
            "snapshot": cmd_snapshot, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
