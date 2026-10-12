---
name: weekly-review
description: Weekly review of the user's Claude Code sessions — collect the week's transcripts, audit existing instruction rules against their own predictions, mine new recurring corrections, and write ONE report of at most 5 proposals (each with mechanism, evidence refs and a ready diff), then STOP for the user's decision. Use when the user says /weekly-review, "недельное ревью", "разбери мои сессии", on Monday mornings, or when a scheduled run fires it. Never applies anything — that is /review-apply.
---

# Weekly review — propose, do not apply

The agent proposes; the user decides. This skill ends with a report file and a
stop. It writes **only** `review/reports/<week>.md`. It never edits
`scripts/review.py`, `review/sessions/**`, `rules.md`, `rejected.md` or any
instruction file — the evaluator stays outside the loop it evaluates.

Format of every file: `review/README.md`. Show command output; never claim.

## 1. Collect (deterministic)

```bash
python scripts/review.py collect            # default: the previous ISO week
python scripts/review.py collect --week 2026-W41
```

Zero transcripts is a valid week: write a report saying so, with no items.

## 2. Audit existing rules

```bash
python scripts/review.py audit --week <week>
```

For each active rule, read the referenced lines and decide — on evidence:

- `predicted_hits > 0` after the rule was added -> **not working**. Open the
  refs: is the rule not being followed, or is its hypothesis wrong?
- `scope_correction_refs` -> **possible side effect** of the rule (its own
  `at_risk` first).
- no `trigger_hits` for weeks -> note it; removal is the monthly loop's call.

A rule under question becomes a `kind: questioned` item (fix the wording, narrow
the scope, or change the hypothesis) — not a silent edit.

## 3. Mine new patterns — mechanism, not surface

Read `review/sessions/<week>/digest.jsonl` with grep/Read. Read **every**
`user-msg`, not only `correction_hint` ones — the hint regex is a pointer with
known misses. Also: `interrupt`, `tool-denied`, `repeat_of`, `retry_hint`,
`tool-error` clusters. For a candidate, open the raw line
(`review/sessions/<week>/raw/<file>`, line N) and the turns before it.

A cluster is admissible only if it states the **mechanism**: *why* the user had
to correct ("the agent ran the command from the wrong cwd because the skill
never says which dir"), not *that* they did ("user was annoyed"). One incident is
an observation for `.harness/observations/log.md`, not a rule — a proposal needs
recurrence (2+ refs) or one correction the user marked as serious.

## 4. Filter

Drop anything already covered by `rules.md`, by the target instruction files,
or matching `rejected.md` (the gate will reject it anyway).

## 5. Write the report — at most 5 items, ranked

`review/reports/<week>.md`, header `collector_sha:` copied from
`review/sessions/<week>/meta.json`. Sections in this order: new rules / rules
under question / removal candidates. Each item:

- narrow and triggered: "when I ask Y, do X", never "always X";
- a falsifiable `hypothesis` + `predicts_re` (the correction it should remove)
  + `at_risk` (what it might break) — next week's audit checks both;
- `surface`: prefer `check` or `hook` over `prose` for anything that recurs
  (`docs/DISCIPLINES.md`: prose is ignored under momentum);
- a ready ```diff against the real target file;
- `decision: pending`.

Optimise for proposals that will hold up in next week's audit, not for the
report that sounds best. Fewer, sharper items beat five weak ones.

## 6. Gate and stop

```bash
python scripts/review.py check
```

Green -> tell the user the path and the item titles, ask for a decision per
item (accept / reject + reason / modify), and **stop**. In a scheduled run, send
a notification instead of asking, and stop.

## Anti-patterns

- Editing a rule or instruction file "since it's obviously right".
- Rewording a rejected proposal to slip past `rejected.md`.
- A proposal whose evidence is one session, or whose mechanism is a guess.
- "Always…" rules; rules with no `predicts_re`.
- Tuning the collector regex in the same run that uses it.
