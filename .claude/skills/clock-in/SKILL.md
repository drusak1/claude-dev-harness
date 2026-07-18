---
name: clock-in
description: Session-start ritual for the dev harness — read the router and the active project's PROGRESS.md, surface the forced-scout queue and any ceiling-claimed lines, confirm a green baseline, then open exactly ONE WIP approach (class-tagged, signature-checked). Use at the start of every session, when the user says /clock-in, "let's go", "начинаем", "поехали", or "continue", before touching any code.
---

# Clock-in — session-start ritual

The SessionStart hook already injected the banner (scout queue, WIP, ceiling
re-challenges, dirty trees). This ritual is its human-readable counterpart: read
the state, honour the queue, and leave with exactly ONE approach open.

Show command output as evidence. Never claim, show.

## Steps (in order)

1. **Read the router:** `CLAUDE.md`. Its constraints override default behaviour.
2. **Identify the active project.** If the user did not name one, run
   `make projects-list` and ask which. If it has no `projects/<name>/` directory,
   it is new — go to step 6.
3. **Read the project state:** `projects/<name>/PROGRESS.md` (where we are, what
   is next), then `DECISIONS.md` (non-obvious past choices — do not re-litigate
   them) and `brief.md` (what this project is for, and what "done" means).
4. **Surface the scout queue:** `python scripts/ledger.py queue`.
   - A pending `forced-scout` is **WIP-blocking**. You may not start same-class
     work until it is addressed (`hooks/pre_change.py` enforces this). Take the
     scout as today's WIP — run `/approach-scout`.
   - A `ceiling-rechallenge` means a line claimed a ceiling. Re-challenge it: was
     the next orthogonal sub-variant tried? Is there a different objective?
5. **Baseline:** `make check` (harness) and the active project's own check
   command (`python scripts/projects.py check --name <name>`). Red baseline or
   dirty tree? Fix that first. **No new scope on a broken baseline** — you will
   spend the session unable to tell your breakage from the pre-existing one.
6. **NEW project?** Register it in `projects.json`, copy `projects/_TEMPLATE/`
   to `projects/<name>/`, fill `brief.md`, then run **`/project-recon` FIRST**.
   Mapping the codebase before proposing changes is the highest-ROI first move.
7. **Open ONE approach (WIP=1).** Class-tagged and signature-checked:
   ```bash
   python scripts/ledger.py add --project <name> --class <class> \
     --objective "<the outcome being optimised>" \
     --hypothesis "<concrete, testable claim>" \
     --source <failure-correlated|descriptive>
   python scripts/ledger.py set-status <id> testing
   ```
   - `add` REJECTS a `(class, objective, hypothesis)` signature that already
     died. A rejection is a signal to change the angle, not to rephrase.
   - Pick the class from `registry/approach-classes.md`. The test: *if this
     attempt fails, which other attempts should I be less optimistic about?*
     Those share its class.
   - `--source descriptive` may NOT be promoted to a build without a
     failure-correlation artifact. If all you have is "the docs recommend it",
     your first move is `/repro-first`, not an edit.

## Leave clock-in with

- [ ] active project named; its PROGRESS.md / brief.md read
- [ ] scout queue surfaced and honoured (scout taken if pending)
- [ ] `python scripts/ledger.py check` green — output shown
- [ ] baseline green or its failure explicitly noted as pre-existing
- [ ] exactly ONE approach `testing`, class-tagged
- [ ] (new project only) `/project-recon` run, brief.md filled
