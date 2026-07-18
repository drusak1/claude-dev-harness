# Dev harness — agent router

You are working inside a **multi-project development harness**. It exists to make
you verify before you claim, log every approach before you build it, and **never
grind one idea into the ground**. When you fail, fix the harness, not the prompt.

The code you work on lives in the repos listed in `projects.json` — **not here**.
This repo holds the state and the gates.

> Read `docs/DISCIPLINES.md` (the hard rules) and the active
> `projects/<name>/PROGRESS.md` before starting work.

## The loop (every session)

```
clock-in  ->  (new project? run /project-recon FIRST)  ->  pick ONE approach (WIP=1)
  ->  /repro-first (a failing test or a measurement, before any fix)
  ->  implement  ->  project's own `check`  ->  ledger status + evidence
  ->  /handoff (PROGRESS, commit)  ->  /reflect (frictions -> harness fixes)
  ->  scout-check (N-refute trigger)
```

## Hard constraints

1. **Log every approach in the ledger before building it**, tagged with an
   `approach_class`: `python scripts/ledger.py add --project P --class C
   --objective O --hypothesis H --source {failure-correlated|descriptive}`.
   The ledger REJECTS a re-try of a refuted `(class, objective, hypothesis)`.
2. **Failure-correlation before any build.** A descriptive gap ("the docs say X,
   we do Y") is NOT a license. It needs a repro/log/profile showing the pattern
   in OUR failures. `source` records which you have.
3. **WIP = 1.** One approach `testing` at a time — mechanically enforced.
4. **No status without a measured eval.** A `refuted` row needs `--evidence`
   carrying a `gate_tier` (local-test / integration / e2e / production).
5. **N-refute → forced scout.** After N (=3) refutes in one approach-class, that
   class is BLOCKED and a scout item is queued. You cannot start same-class work
   until you address it (`hooks/pre_change.py` enforces this).
6. **Banned stop-reasons.** `ceiling / impossible / exhausted / -ev /
   rational-stop / works-on-my-machine / environment-issue / wontfix` are
   rejected as a closing `why`. The only legal stuck state is `ceiling-claimed`,
   which is GATED (enumerated sub-variants + a null control) and **auto-reopens**
   every session. There is always a next move.
7. **When a class refutes, first ask: is the OBJECTIVE wrong?** Three failed
   caching strategies usually mean the latency is not in the cache. Change the
   objective before grinding the mechanism.
8. **Show, never claim.** Paste command output as evidence. "Tests pass" without
   the output is not a verification.
9. **Log frictions to `.harness/observations/log.md`** in the same turn they
   happen. Mental notes are not observations.
10. **Do not add a rule after a one-off failure** — log an observation. Promotion
    to a rule (better: a check) happens in `/reflect` after recurrence.

## Verification

- `make check` — verifies **the harness**: ledger consistency + projects.json
  validity + the harness's own tests.
- `make projects-check` — runs each registered project's own `check` command.
- A project's Definition of Done: behavior implemented, covered by a test, its
  `check` green with output shown, ledger row closed with evidence, and the next
  session able to continue from `projects/<name>/PROGRESS.md` alone.

## Skills

| skill | when |
|---|---|
| `/clock-in` | start of every session |
| `/project-recon` | FIRST on a project you have not mapped yet |
| `/repro-first` | before any fix — build the failing test / measurement that defines done |
| `/approach-scout` | on a blocked class or a ceiling claim — propose a DIFFERENT objective |
| `/handoff` | end of session — verify, record, commit |
| `/reflect` | turn frictions into harness fixes |

## State

- `projects.json` — the repos this harness drives (paths, stacks, check commands).
- `registry/approaches.jsonl` — the cross-project Approach-Ledger (compounds).
- `registry/approach-classes.md` — the approach-class taxonomy (tag against this).
- `registry/queue.jsonl` — pending forced scouts / ceiling re-challenges.
- `projects/<name>/` — per-project `brief.md`, `PROGRESS.md`, `DECISIONS.md`.
- `.harness/observations/log.md` — the improvement backlog.
