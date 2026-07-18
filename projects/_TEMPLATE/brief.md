# <project name> — brief

Filled by `/project-recon`. This is what the agent reads to know what "done"
means here. Keep it short enough to actually be read every session.

## What it is

One paragraph: what this project does and who depends on it.

## Definition of done (for any change here)

- behaviour implemented and covered by a test
- `<check command>` green, output shown
- (project-specific gates: migrations, changelog, review, …)

## Verification

- **check command:** `<the one command that says this repo is healthy>`
- **runtime:** `<how long it takes>`
- **baseline as of <date>:** `<green | red because …>`

## Shape

- **Entry points:** how work gets in (HTTP, CLI, cron, queue)
- **Boundaries:** where untrusted data crosses in, and what validates it
- **State owners:** what owns persistent state; what is derived
- **Dependency spine:** the few modules everything imports (changes here are expensive)
- **Seams:** where it is designed to be extended (changes here are cheap)

## Invariants

The unwritten rules — the ones a plausible-looking change silently breaks.

- e.g. all timestamps are stored UTC
- e.g. the worker must be idempotent; messages are redelivered

## Known-fragile

From the failure history (`git log --grep=fix|revert`). Files that appear in fix
commits repeatedly. **These are failure-correlation artifacts** — they license a
build under discipline 1 in a way a style observation does not.

| area | evidence | note |
|---|---|---|
| — | — | — |

## Out of scope

What not to touch, and why.
