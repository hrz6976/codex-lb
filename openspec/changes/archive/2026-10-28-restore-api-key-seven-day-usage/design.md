## Context
The overview consumes list usageSummary, which defaults to lifetime totals. Relabeling those totals would be incorrect.
## Goals / Non-Goals
Provide a bounded seven-day comparison; preserve default API compatibility and existing authorization. Do not change limits or selected-key trends.
## Decisions
Accept usageWindow=7d or lifetime on the existing list route. Aggregate the bounded request-log window in one query for all keys, excluding warmups and future rows. Keep lifetime rollups unchanged. Include the selected window in the React Query key and use matching labels. Default the APIs page to 7d; other callers remain lifetime.
## Risks / Trade-offs
Seven-day data follows retained request-log history, like the existing selected-key usage-7d endpoint. It does not reconstruct deleted history from lifetime rollups. Window changes may show a loading state rather than misleading stale totals.
## Migration Plan
No migration. Deploy the frontend and backend together. Revert the commit to roll back.
## Open Questions
None.
