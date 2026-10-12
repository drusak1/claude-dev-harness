# Weekly review — instruction self-improvement

The agent **proposes** changes to its own instructions; the user **decides**.
There is no benchmark — "right" depends on the request — so the quality signal is
the user's corrections around each rule, measured week over week.

```
review/
  rules.md        active / questioned / quarantined rules (the editable surface)
  rejected.md     proposals the user declined — never re-proposed (gated)
  reports/        <YYYY>-W<ww>.md — one report per week, <= 5 items
  sessions/       <week>/raw/*.jsonl + digest.jsonl + meta.json   [gitignored]
  archive/        quarantined rules, 30 days before final removal (monthly loop)
```

## Running without remembering to

```bash
python scripts/install_review_hooks.py          # dry run: shows the merged settings
python scripts/install_review_hooks.py --apply  # user-level hooks, every project
```

- `SessionEnd` -> `review.py snapshot`: copies the transcript into
  `review/sessions/_live/` (no LLM). `collect` reads it next to
  `~/.claude/projects`, so cleanup can no longer eat the evidence.
- `SessionStart` -> `review.py status`: one reminder block when a report awaits
  a decision or last week's review is missing; silent otherwise.
- Weekly run: a scheduled task (desktop app) that fires `/weekly-review` —
  added after the first pilot report.

## Who may change what

| part | role | changed by |
|---|---|---|
| `scripts/review.py` | evaluator: collector, audit, gate | a separate harness commit, never during a review run |
| `review/sessions/**` | raw evidence | `review.py collect` only (Edit/Write denied in settings) |
| `review/reports/*.md` | proposal | `/weekly-review` |
| `review/rules.md`, `rejected.md`, instruction files | the surface being improved | `/review-apply`, after the user's decision, one commit per item |

The split is deliberate: a loop that can edit its own evaluator learns to
satisfy the evaluator instead of the user. The report carries the
`collector_sha` of the digest it was built from; `review.py check` rejects a
mismatch.

## Rule format (`rules.md`)

```markdown
### R-001
- rule: paste the test command output before saying tests pass
- scope: when I ask to fix or verify something
- hypothesis: removes my "show me the output" follow-ups
- predicts_re: (покажи|show).{0,20}(вывод|output)
- trigger_re: (почини|fix|verify)
- at_risk: replies get long on trivial edits
- target: CLAUDE.md
- evidence: 2026-W40 proj__abc.jsonl:57, proj__abc.jsonl:112
- added: 2026-10-05
- last_hit: never
- status: active
```

- `hypothesis` — which of the user's corrections the rule exists to remove.
- `predicts_re` — that correction as a regex. `review.py audit` counts it every
  week: still matching after the rule landed = **the rule does not work**.
- `trigger_re` — (optional) when the rule's scope comes up. Corrections inside
  the scope = **possible side effect**; the last trigger is `last_hit`.
- `at_risk` — what the rule might break; checked in the next audit.
- `target` — where the rule text actually lives (CLAUDE.md, a skill, a hook…).
  `rules.md` is the register; the instruction file is where it takes effect.
- Rules are narrow and triggered ("when I ask Y, do X"), never "always do X".

## Report item format (`reports/<week>.md`)

````markdown
# Review 2026-W41
collector_sha: <from review/sessions/2026-W41/meta.json>

## P1: show test output before claiming green
- kind: new                     # new | questioned | remove
- rule: ...                     # new only
- scope: ...                    # new only
- hypothesis: ...               # new only
- predicts_re: ...              # new only
- at_risk: ...                  # new only
- surface: check                # prose | skill | hook | check
- rule_id: R-003                # questioned / remove only
- mechanism: why the corrections happen, not just that they do
- evidence: proj__abc.jsonl:57, proj__abc.jsonl:112
- decision: pending             # pending | accepted | rejected | modified

```diff
+ the exact change to the target file
```
````

`python scripts/review.py check` (part of `make check`) enforces: <= 5 items,
required fields, evidence refs that resolve to a digest line, no match against
`rejected.md`, `questioned`/`remove` pointing at a real rule id, and the
collector hash. All-prose reports get a warning.

## Known limits (stated, not solved)

- It sees only what the user noticed and corrected. Unnoticed regressions are
  invisible — the monthly loop asks the user to re-read 2 old sessions by hand.
- The correction regex is a pointer, tuned on a handful of real sessions. The
  review reads every `user-msg`, not only the flagged ones.
- Optimise for "proposals the user accepted and that held up in the audit",
  not "the user is pleased right now".
- A scheduled run cannot wait for an answer: it writes the report and notifies;
  applying is a separate step after the user decides.
