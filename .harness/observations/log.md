# Observation log

The improvement backlog. Frictions, corrections and verification gaps are
appended here **in the turn they happen** — a mental note is not an observation.
`/reflect` processes this file.

Format (copy this shape; the entry below the `---` separator is a live example):

```markdown
### OBS-NNN: short title
- Date: YYYY-MM-DD
- Status: OPEN | DONE -- what changed | DECLINED -- why
- Context: what was being worked on (project + approach-class)
- Issue: what happened -- specific enough to reproduce from this description
- Proposed fix: ONE concrete change, named file/section. Prefer a mechanical
  check (test, gate, hook, make target) over a prose rule.
```

Numbering: next number = max in this file + 1. Always re-read before numbering;
never number from memory.

---

### OBS-001: harness bootstrapped
- Date: 2026-07-18
- Status: DONE -- initial commit
- Context: repo creation
- Issue: none; this entry exists so the format above has a real example and the
  OPEN-counter starts from a known state.
- Proposed fix: n/a

### OBS-002: correction heuristic missed real corrections on first contact
- Date: 2026-10-11
- Status: DONE -- CORRECTION_RE widened (frustration, "то есть ты", "N раз"), hint limited to the first 300 chars, prefix re-ask = repeat, RETRY_RE; each case pinned in tests/test_review.py
- Context: harness / observability (ledger id 1), scripts/review.py collect on 2026-W29..W34 (real transcripts, not quoted here)
- Issue: first regex flagged a pasted log and a pasted writeup as corrections and missed three explicit ones (frustration with profanity and no "нет", a "то есть ты ... N раз?" rhetorical question, a "ты сначала ..." reproach); a re-ask after an interrupt was not seen as a repeat.
- Proposed fix: done. Residual risk: regex tuned on the same ~60 messages -- /weekly-review must read every user-msg, the hint is only a pointer.

### OBS-003: transcript retention is not what the 30-day default suggests
- Date: 2026-10-11
- Status: OPEN
- Context: recon for the weekly review
- Issue: cleanupPeriodDays is unset (default 30) yet transcripts with records from 2026-06-24 are still on disk; their mtime is 2026-10-03..05. Retention appears mtime-based, so it is unpredictable -- a raw copy into review/sessions/ is the only reliable record.
- Proposed fix: none yet; if a week's raw ever goes missing, add a `collect` warning when a source file's earliest record is older than cleanupPeriodDays.

### OBS-004: CLAUDE.md router at 82 lines, over the ~80 cap
- Date: 2026-10-11
- Status: OPEN
- Context: adding /weekly-review to the skills table and review/ to State
- Issue: router grew past the cap /reflect sets.
- Proposed fix: next /reflect weekly -- move the "Hard constraints" detail into docs/DISCIPLINES.md pointers.
