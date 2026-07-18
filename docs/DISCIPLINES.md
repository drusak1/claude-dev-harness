# Disciplines — the hard rules

These are load-bearing. Each one is mechanically enforced — a `ledger.py`
admission/transition rule, a `ledger.py check` assertion, or a hook — not a
prose request. Enforcement is named per rule.

**Why mechanical.** These rules started life as prose in an agent's instruction
file, in two long-running projects. They were *ignored* under momentum: the
agent kept producing variants of a failing idea, and only a human ever reopened
the line. The same rules, expressed as a CLI that exits nonzero, worked. That is
the entire thesis of this repo. If you find yourself wanting to add a rule here,
ask first whether it can be a check instead.

---

## 1. Failure-correlation before build

A **descriptive** gap — "the docs recommend X", "the popular library does X",
"our code doesn't have X and good code has X" — is NOT sufficient to license an
implementation. Every approach carries
`source ∈ {failure-correlated, descriptive}`. A `descriptive` row may not be
promoted to a build without a failure-correlation artifact: a repro, a log
slice, a profile, or a metric showing that this pattern is present in **our own
failures** more than in our successes.

A best-practice diff may *suggest* where to look. Only a failure-correlation
licenses a build.

The trap this closes: an agent reads a style guide or a competitor's code, finds
17 differences, and "fixes" all 17 — none of which caused the bug it was asked
to fix.

*Enforced:* `ledger.py add` records `source` and prints the promotion
constraint; a `descriptive` row with no artifact is not admissible to a build.

## 2. Approach-class on every entry

Every ledger row has an `approach_class` (from `registry/approach-classes.md`).
It is load-bearing: without it, many distinct failures hide inside one class and
the grind is invisible — five "different" fixes that were all *"add another
guard at the call site"* read as five attempts, not as one exhausted idea.

The approach-class is what the N-refute counter aggregates on.

*Enforced:* `ledger.py add` requires `--class`; `ledger.py check` rejects a row
without one.

## 3. Append-only `why`

A verdict already written is NOT silently rewritten. New data means a new dated
line; the old line stays, even if it turned out wrong, so the record cannot
self-contradict. This exists because an agent was observed flipping a verdict on
the *same* evidence several times within one hour, each time sounding confident.

*Enforced:* `set-status` appends to `why`; it never overwrites prior text.

## 4. Banned stop-reasons

`ceiling`, `impossible`, `exhausted`, `-ev`, `rational-stop`,
`works-on-my-machine`, `environment-issue`, `wontfix` are FORBIDDEN as a closing
`why`. They are not verdicts. The first group is generic defeatism; the second
is its development-specific form — closing a line by relocating the cause
outside the code instead of explaining the failed mechanism.

A refute must say **what mechanism failed and how you measured it**. "Caching
the resolver did not help because the resolver is 2% of p99; the hot path is the
TLS handshake" is a verdict. "Wontfix" is a shrug.

The only legal stuck state is `ceiling-claimed` (rule 7).

*Enforced:* `ledger.py check` exits nonzero if a banned word is the closing
`why` of a `refuted` row; `make check` runs it.

## 5. WIP = 1

Exactly one approach is `testing` at a time. Breadth comes from the scout queue,
not from juggling half-tested ideas. Two open threads means neither gets a clean
verdict, and the ledger fills with rows nobody can close.

*Enforced:* `set-status … testing` rejects a second concurrent `testing` row;
`ledger.py check` fails a ledger with more than one.

## 6. N-refute → forced scout

When an approach-class accumulates `N` (default 3, override `CDH_REFUTE_N`)
`refuted` rows, that class is BLOCKED for new admissions and a `forced-scout`
item is appended to `registry/queue.jsonl`. You cannot start same-class work
until the scout is addressed.

This is the mechanical replacement for the prose rule "step back and question
the approach", which does not survive momentum.

**When a class refutes, the first question is whether the OBJECTIVE is wrong** —
not which variant to try next. Three failed caching strategies usually mean the
latency budget is not in the cache; occasionally they mean the feature did not
need to be fast.

*Enforced:* `set-status … refuted` counts, blocks the class, and writes the
queue item; `hooks/pre_change.py` enforces the block.

## 7. Ceiling = gated + auto-reopen

`ceiling-claimed` is the only legal stuck state, and it is a gated artifact. To
set it, the entry MUST already carry:

- `sub_variants` — the orthogonal variants actually tried, enumerated; and
- `control` — a null/oracle result showing the limit is real and not ours (a
  minimal repro outside our code that hits the same wall, an upstream issue
  link, a benchmark of the dependency in isolation).

Setting it does NOT end work. It auto-emits a scout item, and `session_start.py`
re-challenges every ceiling line at the start of every session.

*Enforced:* `set-status … ceiling-claimed` rejects the transition without
sub-variants + control; `ledger.py check` rejects such a row; the scout item is
auto-queued.

## 8. No silent re-try of a dead signature

`ledger.py add` REJECTS any new row whose `(approach_class, objective,
hypothesis)` signature matches an existing `refuted`/`ceiling-claimed` entry —
across all projects. A rejection means "pick a different angle", not "retry".

The cross-project scope matters: the same dead idea tends to resurface in the
next repo three weeks later, and nobody remembers it died.

*Enforced:* `ledger.py add` signature check against `registry/approaches.jsonl`.

## 9. Every refute carries an evidence tier

A `refuted` row must have `evidence` with a
`gate_tier ∈ {local-test, integration, e2e, production}`. A refutation with no
measured tier is not a refutation — it is an impression.

The tier also calibrates trust: "it failed locally" and "it failed in
production" are different claims, and mixing them is how an agent talks itself
out of a working approach.

*Enforced:* `set-status … refuted` requires `--evidence` with a `gate_tier`;
`ledger.py check` rejects a `refuted` row missing it.

---

## What is NOT enforced (deliberately)

The harness does not check code quality, style, or architecture — your project's
own `check` command owns that. The harness only governs **how the agent decides
what to try next**. Keeping that boundary is what keeps it usable on any stack.
