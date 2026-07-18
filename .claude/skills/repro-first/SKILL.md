---
name: repro-first
description: Build the failing test or measurement that defines "done" BEFORE writing a fix, and turn a descriptive hunch into a failure-correlated one. Use before any bug fix or performance work, when the user says /repro-first, "fix this bug", "it's slow", "почини", or whenever a ledger row's source is `descriptive` and needs promoting.
---

# Repro-first — no fix without a measured eval

Two failures this prevents, both common and both expensive:

- **Fixing a symptom you cannot observe.** Without a repro you cannot tell a fix
  from a coincidence, and "it seems better now" enters the record as fact.
- **Building on a descriptive gap.** "The docs recommend X and we don't do X" is
  not evidence that the absence of X caused anything
  (`docs/DISCIPLINES.md` rule 1).

The output of this skill is an artifact — a committed failing test, a benchmark
script, a log query — not a paragraph of analysis.

## 1. State the observable

Write down, before touching anything: **what will be different when this is
fixed, and what command shows it?**

If you cannot name the command, that is the task. A bug with no observable is
not ready to fix; it is ready to instrument (`observability` approach-class).

## 2. Reproduce, at the cheapest tier that still fails

Tiers, cheapest first: `local-test` -> `integration` -> `e2e` -> `production`.
Reproduce at the cheapest tier that genuinely exhibits the failure, and record
which tier that was — it becomes the `gate_tier` on the ledger evidence.

Resist reproducing at a tier *below* the real failure: a unit test that passes a
mock the same wrong value the caller passes is not a repro, it is a restatement.

If it only reproduces in production, say so plainly. That is a finding — it
usually means the cause is data or config, not logic, and it redirects the whole
approach.

## 3. Correlate the hypothesis with the failure

This is the step that promotes `descriptive` to `failure-correlated`. Show that
the pattern you want to change is **present in the failures and absent (or
rarer) in the successes**:

- a profile where the suspected call is actually hot;
- a log slice where failing requests share the suspected attribute and passing
  ones do not;
- a git bisect landing on the suspected change;
- a toggle: force the suspected condition, watch the failure rate move.

If you cannot produce any of these, you do not have a licensed build. Say so and
either instrument further or pick a different hypothesis. **Do not proceed
because the fix "seems obviously right"** — that instinct is exactly what rule 1
exists to intercept.

## 4. Make the repro a permanent test

Commit the failing test in the project repo before the fix. It has to fail for
the stated reason — run it and read the failure message. A test that passes
before your fix was never testing your bug.

## 5. Record it on the ledger row

```bash
python scripts/ledger.py set-status <id> testing \
  --why "repro at <tier>: <command> -> <observed failure>; correlation: <artifact>"
```

If this converted a descriptive hunch into a correlated one, say that explicitly
in the `why` — the next session needs to know the build is licensed.

## Done when

- [ ] the observable and its command are written down
- [ ] the failure reproduces at a named tier, and the tier is honest
- [ ] a correlation artifact exists (or the absence is stated and the build is
      not proceeding)
- [ ] the failing test is committed in the project repo and fails for the right
      reason
- [ ] the ledger row carries the repro command and the tier

## Anti-patterns

- Writing the fix first and the test after — the test then encodes the fix's
  assumptions, not the bug's behaviour.
- A repro that needs manual steps: it will not be re-run, so it cannot refute
  anything later.
- Claiming `failure-correlated` because the hypothesis is plausible. Plausible is
  what `descriptive` means.
- Skipping this for "obvious" one-liners. The obvious ones are where an
  unverified fix survives longest before anyone notices it did nothing.
