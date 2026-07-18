# Architecture

## What this repo is

A state store and a set of gates. It contains **no project source code**. The
repos it drives are named in `projects.json` and live outside it — which is why
this repo can be public while those stay private.

```
claude-dev-harness/
  CLAUDE.md              router the agent reads first (~70 lines, a map not an encyclopedia)
  projects.json          -> the N repos being driven          [gitignored]
  registry/
    approaches.jsonl     the cross-project Approach-Ledger    [the compounding asset]
    queue.jsonl          pending forced scouts / ceiling re-challenges
    approach-classes.md  the taxonomy the N-refute counter aggregates on
  projects/<name>/       per-project brief / PROGRESS / DECISIONS
  scripts/
    ledger.py            the anti-grind gates (add / set-status / check / queue)
    projects.py          the project registry (list / validate / check / path)
    hooks/
      session_start.py   injects queue + WIP + ceilings + dirty trees into context
      pre_change.py      BLOCKS work in a blocked approach-class
  docs/
    DISCIPLINES.md       the hard rules + what enforces each one
    QUALITY.md           grades, benchmarks, simplification log
  .claude/skills/        the six rituals
  .harness/observations/ the improvement backlog
```

## Layering

```
hooks  ->  ledger.py / projects.py  ->  registry/*.jsonl, projects.json
skills ->  (invoke the scripts; never write the jsonl directly)
```

Dependencies point only downward. Two rules follow:

1. **Nothing writes `registry/*.jsonl` except `ledger.py`.** A skill that hand-
   edits the ledger bypasses every gate, which is the one failure the harness
   cannot detect. If a skill needs a write the CLI does not support, add it to
   the CLI.
2. **`ledger.py` never imports `projects.py`.** The ledger's `--project` is a
   free-form string on purpose: a row about a repo you later remove must still
   parse. Coupling them would make the historical record depend on current
   config.

## Golden principles

1. **Prefer a check to a paragraph.** Anything you would write as a rule, ask
   first whether it can exit nonzero instead. This is the entire premise
   (`docs/DISCIPLINES.md`).
2. **Agent-oriented errors.** Every rejection prints what / WHY / FIX, so the
   agent can self-correct from the output alone without reading source. Look at
   the `REJECTED:` strings in `ledger.py` for the house style.
3. **Pure stdlib, offline.** No dependencies, no network, no daemon. The harness
   must work on a fresh machine with Python and git, or it will be skipped on
   exactly the day it is most needed.
4. **The record is append-only.** Verdicts accrete, they do not get rewritten.
   Rewriting is how a record becomes a story.
5. **Correctness, then ergonomics, then features.** A gate that is wrong is
   worse than no gate — it teaches the agent to route around the harness.
