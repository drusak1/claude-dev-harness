---
name: handoff
description: End-of-session clock-out for the dev harness — verify, close the WIP ledger row with evidence, update the project's PROGRESS.md and DECISIONS.md, log observations, remove debris, commit. Use when the user says /handoff, "wrap up", "заканчиваем", "закругляемся", or before ending any session that changed code or the ledger.
---

# Handoff — clean-state exit

Run in order. Show command output as evidence — never claim, show.

1. **Verify.** `make check` (harness) and the project's own check:
   `python scripts/projects.py check --name <name>`.
   Failing and quickly fixable -> fix and rerun. Not quickly fixable -> record it
   as `blocked` in `projects/<name>/PROGRESS.md` with the actual failure output.
   **Do not hide a red baseline** — the next session will burn an hour on it.

2. **Close the WIP row.** Never leave it dangling at `testing`:
   ```bash
   python scripts/ledger.py set-status <id> <works|refuted|ceiling-claimed> \
     --evidence '<json>' --why '<what happened, mechanistically>'
   ```
   - `refuted` requires `evidence` carrying a `gate_tier` (local-test /
     integration / e2e / production). It increments the same-class refute count;
     at the threshold the ledger blocks the class and queues a scout — note that
     in PROGRESS so the next clock-in sees it.
   - `ceiling-claimed` is gated: the row must list the orthogonal sub-variants
     tried plus a null control, or the transition is rejected. It auto-queues a
     re-challenge; it never ends work.
   - `why` is append-only. New data means a new dated line; the old verdict stays
     even if it turned out wrong.
   - The `why` must explain the **mechanism** — "caching the resolver did not
     help because the resolver is 2% of p99" — not a shrug. Banned stop-reasons
     fail `ledger.py check`.

3. **Scout check.** `python scripts/ledger.py queue`. If this session tripped a
   forced scout, or one is still pending, surface it explicitly in PROGRESS.

4. **Progress.** Add an entry to `projects/<name>/PROGRESS.md`, newest first:
   done / in progress / blocked / **NEXT STEP** / baseline status, with the
   commit ref. The test: **could the next session continue from this alone?**

5. **Decisions.** Non-obvious choices made this session go to
   `projects/<name>/DECISIONS.md`: decision / why / rejected alternative /
   constraint it creates. This is the "why" that context compaction loses, and
   the reason the next session does not re-litigate a settled trade-off.

6. **Observations.** Any unlogged friction or user correction ->
   `.harness/observations/log.md`. This is `/reflect`'s input.

7. **Debris.** Remove what this session introduced and nothing needs: scratch
   scripts, debug prints, commented-out experiments, stray files.

8. **Commit.** In the **project repo** for code, and in the **harness repo** for
   ledger/progress state — they are separate repos, and forgetting the second
   loses the session's record. Branch first if on the default branch. Push only
   if the user asked.

## Clean-state checklist

- [ ] harness `make check` green — output shown
- [ ] project check green, or its failure recorded in PROGRESS
- [ ] WIP row closed with a real status + evidence (not left `testing`)
- [ ] scout queue surfaced in PROGRESS if tripped
- [ ] PROGRESS has an explicit NEXT STEP
- [ ] `ledger.py check` green (no banned stop-reasons)
- [ ] both repos committed; next session continues from PROGRESS.md alone
