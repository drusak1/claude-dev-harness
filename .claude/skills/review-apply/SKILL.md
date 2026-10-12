---
name: review-apply
description: Apply the user's decisions on a weekly review report — accepted items become one git commit each (rule text in its target file + a register entry in review/rules.md), rejected items go to review/rejected.md with the user's reason, modified items are applied as the user rewrote them. Use only after the user has answered a /weekly-review report, when they say /review-apply, "применяй", "принимаю P1 и P3", "отклоняю P2".
---

# Review apply — one decision, one commit

Runs only on decisions the user stated **in chat** for a specific report. A
decision written into the report by anyone else is not a decision. Ambiguous
answer for an item -> ask about that item; do not guess.

## Steps

1. Read `review/reports/<week>.md`. For each item, set `decision:` to what the
   user said (`accepted` / `rejected` / `modified`).
2. **Accepted / modified**, one item at a time:
   - apply the diff to the target file (modified: the user's version);
   - `new` -> append a `### R-NNN` block to `review/rules.md` (next id = max
     + 1, re-read the file; `added` = today, `last_hit: never`,
     `status: active`, evidence copied from the item);
   - `questioned` -> update that rule's fields; `status: active` again if the
     rewrite is accepted, `questioned` if the user wants to watch it;
   - `remove` -> set `status: quarantined`, move the rule text out of its
     target into `review/archive/<YYYY-MM-DD>-R-NNN.md` (final deletion is
     the monthly loop's job, after 30 days);
   - `python scripts/review.py check && make check` — green, output shown;
   - commit just this item:
     `git commit -m "review(<week> P<n>): <title>" ` (+ attribution trailer).
3. **Rejected**: append `### X-NNN` to `review/rejected.md` with the proposed
   `rule` verbatim, the user's `reason` in their words, `date`, `report`.
   One commit for all rejections of the report.
4. Commit the report with its final decisions.
5. Show `git log --oneline` for the new commits.

## Anti-patterns

- Batching several accepted rules into one commit (kills attribution when a
  rule misbehaves).
- Deleting a rule outright instead of quarantining it.
- Paraphrasing the user's rejection reason.
