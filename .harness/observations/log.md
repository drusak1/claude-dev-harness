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
