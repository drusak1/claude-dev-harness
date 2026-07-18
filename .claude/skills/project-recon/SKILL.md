---
name: project-recon
description: Run FIRST on a repo the harness has not mapped yet — find how it is verified, what its real boundaries and invariants are, where it has failed before, and seed the approach-class taxonomy from that. Use when adding a project to projects.json, when the user says /project-recon, "map this repo", "разберись в проекте", or before proposing any change to a codebase you have not read.
---

# Project-recon — map before you move

The highest-ROI first move on an unfamiliar repo, and the one most often
skipped. An agent that starts editing before mapping produces changes that are
locally plausible and globally wrong: it re-implements a helper that exists,
violates an invariant nobody wrote down, and "fixes" a pattern that was
deliberate.

Output: a filled `projects/<name>/brief.md`, a registered entry in
`projects.json`, and seeded rows in `registry/approach-classes.md`.

## 1. Find the verification path

Before anything else, answer: **what one command tells me this repo is
healthy?** Look at CI config, `Makefile`, `package.json` scripts,
`pyproject.toml`, `CONTRIBUTING.md`, and the README in that order.

Run it. Record how long it takes and whether it is green *right now* — a repo
whose baseline is already red changes everything about how you work in it.

Put that command in `projects.json` as `check`. It is the harness's only
structural dependency on the project.

## 2. Map the shape, not the files

Do not enumerate directories. Answer:

- **Entry points** — how does work get into this system (HTTP handler, CLI, cron,
  queue consumer)?
- **Boundaries** — where does untrusted data cross in, and what validates it?
- **State** — what owns persistent state, and what is derived from it?
- **The dependency spine** — which few modules does everything import? Those are
  where a change is expensive.
- **The seams** — where is it already designed to be extended? Changes there are
  cheap; changes elsewhere are not.

## 3. Read the failure history

This is what separates recon from a tour. The repo's own history says where it
actually breaks:

```bash
git log --oneline -50
git log --oneline --grep='fix\|revert\|hotfix' -i -30
```

Look for: files that appear in fix commits repeatedly (fragile), reverts (ideas
that looked right and were not), and long-lived TODO/FIXME comments near
complex code. Also read any `DECISIONS.md`, ADRs, or design docs — a decision
you re-litigate is a session wasted.

**Repeated fix commits on one file are a failure-correlation artifact.** Note
them; they license builds under rule 1 that a style observation would not.

## 4. Write the brief

Fill `projects/<name>/brief.md`: what the project is for, who depends on it,
what "done" means, the check command, the known-fragile areas, and the
invariants you found — especially unwritten ones ("all timestamps are UTC",
"the worker must be idempotent"). An invariant discovered here and written down
is worth more than any code you will write this session.

## 5. Seed approach-classes

Add any project-specific classes to `registry/approach-classes.md` — the axes
along which changes to *this* repo naturally differ. Keep them project-agnostic
where you can: the ledger is cross-project, and the compounding value is
recognising that `retry-at-call-site` already died in another repo.

## Done when

- [ ] the check command is found, run, and registered in `projects.json`
- [ ] `brief.md` names entry points, boundaries, state owners and invariants
- [ ] the failure history is read, and fragile areas are listed
- [ ] any project-specific approach-classes are seeded
- [ ] `python scripts/projects.py validate` is green — output shown

## Anti-patterns

- Producing a directory listing and calling it a map. The question is where
  change is expensive, not where files are.
- Skipping the failure history — it is the only cheap source of
  failure-correlated evidence in the whole repo.
- Proposing improvements during recon. Recon is read-only; hypotheses go to the
  ledger, and they go there **after** you know what "healthy" means here.
