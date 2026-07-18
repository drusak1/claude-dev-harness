---
name: reflect
description: Self-improvement loop for the dev harness — turn session frictions and the observation log into fixes for CLAUDE.md, the skills, the hooks, and the mechanical gates in ledger.py. Modes: session (default) captures observations and applies small fixes; weekly processes the OPEN backlog, promotes recurring frictions to mechanical checks, and runs the simplification pass. Use when the user says /reflect, after repeated corrections, or when the weekly review is overdue.
---

# Reflect — self-improvement loop

The harness improves only through this loop: capture -> reflect -> promote ->
simplify. When the agent fails, fix the harness, not the prompt.

The load-bearing target is the **mechanical gate**. A friction that a prose rule
failed to prevent must become a check in `ledger.py`, a hook, or a test — never
another paragraph in `CLAUDE.md`. That is the whole premise of this repo
(`docs/DISCIPLINES.md`).

## Mode: session (default)

1. Scan the session for: user corrections, repeated friction, CLAUDE.md
   assumptions that proved wrong, and **verification gaps** — something went
   wrong that no check caught (a dead signature got retried, a build proceeded on
   a descriptive gap, a refute landed with no tier, two rows sat `testing`).
2. Append each as an observation to `.harness/observations/log.md` in the format
   at the top of that file. Next number = max in the file + 1 — **re-read the
   file, never number from memory.**
3. For each, propose exactly ONE fix. Not a menu of alternatives.
4. Apply approved fixes:
   - additive and small (a clarified line, a new anti-pattern bullet) -> edit
     directly;
   - behaviour-changing (a new gate, a changed threshold, a restructured skill)
     -> show the diff first, apply after approval.

## Mode: weekly

1. Read all OPEN observations.
2. Group by target: `CLAUDE.md` | skill | hook | **mechanical gate**.
3. **Promotion rule (non-negotiable):** a friction observed 2+ times MUST become
   a mechanical check — a new assertion in `ledger.py check`, a new
   admission/transition rule, a hook, a test, or a make target. More prose is
   NOT a fix for a recurring problem. Record it in the Promotion ledger in
   `docs/QUALITY.md`.
4. Apply fixes; mark each observation `DONE -- <what changed>` or
   `DECLINED -- <why>`. Never DONE without naming the change.
5. Log over ~150 lines -> move DONE/DECLINED entries to
   `.harness/observations/archive-YYYY-MM.md`.
6. **Simplification pass.** Every harness component encodes an assumption about
   what the model cannot do alone, and those assumptions go stale as models
   improve. Pick one component that has not mattered in a month, disable it, run
   a normal session, and remove it permanently if nothing degrades. Record the
   experiment in the Simplification Log in `docs/QUALITY.md`.
   A harness that only grows is a harness that gets abandoned.
7. Update the grades and benchmark snapshot in `docs/QUALITY.md`.
8. Write today's date to `.harness/last-review.txt`.

## Anti-patterns

- Adding a CLAUDE.md rule after a one-off failure. Log it; wait for recurrence.
- Fixing the prompt when the harness lacks a tool, gate or doc.
- "Be more disciplined about X" as a fix — the entire lesson is that prose
  discipline gets ignored under momentum. Encode it.
- Growing `CLAUDE.md` past ~80 lines. It is a router; detail belongs in `docs/`.
- Numbering observations from memory instead of re-reading the log.
- Marking an observation DONE without naming what changed.
- Never removing anything. If the Simplification Log has no entries after two
  months, the loop is only half running.
