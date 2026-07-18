---
name: approach-scout
description: The anti-grind core. When an approach-class is blocked (N same-class refutes) or a line is ceiling-claimed, propose a DIFFERENT objective or representation — not a smaller tweak of the blocked one — and register it as a new ledger row. Use when `ledger.py queue` shows a pending item, when pre_change.py blocks work, when the user says /approach-scout, "switch approach", "застряли, смени угол", or when a ceiling claim must be re-challenged.
---

# Approach-scout — change the objective, don't grind the tweak

This skill exists because the prose version of it gets ignored. Under momentum,
an agent that has tried three caching strategies proposes a fourth caching
strategy — the search collapses to variants of a failing family, and only a
human ever reopens it. The ledger blocks the class mechanically; this skill is
what you do about the block.

> A refutation is never a stop signal. It is the trigger to find a different
> objective or representation. `ceiling / impossible / exhausted / wontfix` are
> banned as closing reasons — `ledger.py check` fails on them.

## When this fires

1. **Forced scout.** `set-status … refuted` counted N (default 3) same-class
   refutes, blocked the class, and queued a `forced-scout` item.
2. **Ceiling re-challenge.** A line was set `ceiling-claimed` (legal only with
   enumerated sub-variants + a null control), which queued a re-challenge that
   `session_start.py` re-surfaces every session.
3. **Pre-change block.** `hooks/pre_change.py` refused to start same-class work.

Always start here:
```bash
python scripts/ledger.py queue
python scripts/ledger.py list --project <name>
```

## 1. Find the shared assumption

Read every `registry/approaches.jsonl` row in the blocked class. Extract:

- the **objective** they all shared — this is the thing to change, not the
  hypotheses inside it;
- the **representation** of the problem they all assumed (this data model, this
  call graph, this boundary);
- each refutation's `why` — what the class structurally cedes.

N refutes in one class point at one shared assumption. Name it in a sentence. If
you cannot, you have not read the rows carefully enough — the scout will produce
another variant instead of a different idea.

## 2. Change the load-bearing axis

Propose an approach that differs along **objective** or **representation**, not
along a parameter:

| axis | blocked | a real change |
|---|---|---|
| objective | "make the query fast" | "make the query unnecessary" (precompute, denormalise, change the screen) |
| objective | "handle the error" | "make the error unrepresentable" (schema, types) |
| representation | "retry the flaky call" | "change who owns the state so the call isn't needed" |
| requirement | "load in 200ms" | "appear loaded in 200ms" (skeleton, optimistic UI) |

`registry/approach-classes.md` lists the seed classes. Two are the usual exits
and are underused: `observability` (we cannot fix what we cannot see — a
measurement is a legitimate approach with a real test) and `requirement-change`
(the strongest move; three refuted classes often mean the requirement is wrong).

**Ground it.** Point at something real — a profile, a log, an upstream issue, a
pattern from another project's ledger rows. An ungrounded jump is a guess, which
is the same failure in a new costume.

## 3. Confirm it is admissible, then register it

The new `(class, objective, hypothesis)` must not match any refuted or
ceiling-claimed row, or `ledger.py add` rejects it. **A rejection means the
proposal was not different enough** — return to step 2 rather than rewording.

```bash
python scripts/ledger.py add --project <name> --class <DIFFERENT class> \
  --objective "<the changed objective>" \
  --hypothesis "<concrete, testable, different along the load-bearing axis>" \
  --source <failure-correlated|descriptive>
```

Prefer `failure-correlated`. If the scout idea is only descriptive, say so on
the row — its first step is `/repro-first`, not an edit.

## 4. Keep one from-first-principles line alive

Alongside the grounded jump, keep ONE live row that is not derived from any
current class or precedent — a restatement of the problem from scratch, as if
the existing code did not exist. If no such row is currently `untested` or
`testing`, add one now.

This is the floor under the mechanism. Without it, the search can still collapse
— just more slowly, into "variants of the families we know".

## 5. Resolve and hand off

The blocked class stays blocked for new admissions. You do not unblock it by
arguing; you proceed in the new class. Print:

- the blocked class and its shared assumption, in one sentence;
- the new class, the changed axis, and what grounds it;
- the new ledger id, and the state of the from-first-principles line.

Close with the next concrete move. Never with a stop-reason.

## Anti-patterns

- **A smaller tweak of the blocked class** (same objective, new constant). This
  is the grind the harness exists to stop. The signature check catches some of
  it; do not rely on it — change the axis deliberately.
- **Arguing the block open.** It is mechanical, not a debate. The block is the
  finding.
- **Letting the from-first-principles line die.** It is the floor; always one.
- **A scout that is really a rename.** If refuting the new row would not surprise
  you given the old ones, it is the same idea.
