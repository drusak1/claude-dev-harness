# claude-dev-harness

An **anti-grind harness for Claude Code**, across several repos at once.

A harness is everything outside the model weights: instructions, state,
verification, scope control, session lifecycle. Most harnesses stop at "give the
agent good instructions". This one starts where that fails.

## The problem it solves

Coding agents do not usually fail by being wrong once. They fail by being wrong
*persistently*: an idea does not work, so the agent tries a variant, then another
variant, then a third — each locally reasonable, all sharing the assumption that
was actually broken. Under momentum, an agent that has tried three caching
strategies proposes a fourth.

The obvious fix is to write "step back and question the approach" in the
instructions. **That was tried, in two long-running projects, and it was
ignored.** The rule was read every session and had no effect; only a human ever
reopened the line.

The same rules, expressed as a CLI that exits nonzero, worked. That is what this
repo is: those rules as code.

## What it actually does

Every approach gets logged before it gets built, tagged with an **approach-class**
— *what kind of move it is*, not which file it touches:

```bash
python scripts/ledger.py add --project api --class caching \
  --objective "cut p99 latency" \
  --hypothesis "memoize the resolver" \
  --source failure-correlated
```

From there the gates apply:

| gate | what it does |
|---|---|
| **dead signature** | re-adding a `(class, objective, hypothesis)` that already died is **rejected**, across all projects |
| **N-refute → forced scout** | 3 refutes in one class **blocks** that class and queues a scout; you cannot start same-class work until you propose a different *objective* |
| **WIP = 1** | a second concurrent `testing` row is rejected |
| **evidence tier** | a refute without a measured `gate_tier` is rejected — an unmeasured refutation is an impression |
| **banned stop-reasons** | `impossible / exhausted / wontfix / works-on-my-machine` as a closing verdict fail the check |
| **gated ceiling** | the only legal stuck state requires enumerated sub-variants + a null control — and it **auto-reopens** every session |
| **append-only verdicts** | a `why` is never rewritten; new data means a new dated line |

The point of the N-refute gate is the question it forces: **when a class
refutes, is the OBJECTIVE wrong?** Three failed caching strategies usually mean
the latency is not in the cache. Occasionally they mean the feature did not need
to be fast.

Full rules and what enforces each: [`docs/DISCIPLINES.md`](docs/DISCIPLINES.md).

## Multi-repo by design

The harness holds **state, not source**. `projects.json` points at the repos it
drives; they live outside it and keep their own git history:

```
~/code/
  claude-dev-harness/     <- this repo: ledger, gates, rituals   (public)
  my-api/                 <- driven                              (private)
  my-web/                 <- driven                              (private)
  my-worker/              <- driven                              (private)
```

Two consequences: the ledger **compounds across projects** (the same dead idea
resurfacing in the next repo three weeks later gets caught), and this repo is
safe to publish while the code it drives stays private — `projects.json` is
gitignored.

The only structural dependency on a project is one command: `check`, exit 0 =
green. Python, TypeScript, Go, anything.

## Session loop

```
/clock-in         read state, honour the scout queue, open ONE approach
  /project-recon  (new repo only) map it before touching it
  /repro-first    the failing test or measurement, BEFORE the fix
  ...implement, run the project's check...
  /approach-scout (if a class got blocked) change the objective, not the constant
/handoff          verify, close the row with evidence, record, commit
/reflect          turn frictions into gates -- never into more prose
```

## Requirements

Python 3.9+, git, make, bash, and [Claude Code](https://code.claude.com/docs).
No dependencies, no network, no daemon — the harness has to work on a fresh
machine, or it gets skipped on the day it is most needed.

## Quick start

```bash
git clone https://github.com/<you>/claude-dev-harness && cd claude-dev-harness
./init.sh                       # creates projects.json, runs the baseline
$EDITOR projects.json           # point it at your repos
make check                      # ledger + config + 16 tests
```

Then open Claude Code in this directory and say `/clock-in`.

## Self-improvement

Frictions go to `.harness/observations/log.md` as they happen. `/reflect` turns
them into fixes, under one rule: **anything corrected twice becomes a mechanical
check, never more prose.**

`/reflect weekly` also runs a *simplification* pass — disable one component, work
a normal session, delete it permanently if nothing degrades. Every harness
component encodes an assumption about what the model cannot do alone, and those
assumptions go stale as models improve. A harness that only grows is a harness
that gets abandoned.

## Provenance

The disciplines come from post-mortems on two long-running agent projects where
the prose versions demonstrably failed. The structure owes to
[learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering)
and OpenAI's [harness engineering](https://openai.com/index/harness-engineering/)
write-up; the anti-grind gates are what got added after watching prose lose.

## License

MIT — see [LICENSE](LICENSE).
