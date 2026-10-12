# Rejected proposals

Proposals the user declined. `review.py check` rejects a report item whose
`rule` matches one of these — a rejection is not re-proposed with new wording.
If the situation really changed, the user removes the entry, not the agent.

Format:

```markdown
### X-001
- rule: <the proposed rule text, verbatim>
- reason: <the user's reason, in their words>
- date: YYYY-MM-DD
- report: 2026-W41 P2
```

<!-- No rejections yet. /review-apply appends `### X-NNN` blocks here. -->
