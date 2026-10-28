## Context
The existing usage refresh job already owns cancellation, leader election, and polling. No general notification transport exists.
## Goals / Non-Goals
Notify on observed fleet-wide quota exhaustion. Do not alter routing, send alerts for account authentication failures, or send per-key/model-specific alerts.
## Decisions
Store the optional T2 Bark URL encrypted in dashboard_settings. Manage it with GET/PUT /api/settings/notifications (security:write), returning only a configured boolean. The Settings card accepts a replacement URL and can clear it; plaintext is never returned. Parse it into the V2 /push endpoint and device_key JSON field. Reuse httpx and the quota helper; no secrets enter request URLs or logs. Check after complete refresh cycles, loading account/usage rows sequentially in a background session and closing it before network I/O. Fresh nonexpired standard windows determine exhaustion, including weekly-only and monthly plans and purchased-credit overrides. Missing/stale data is unknown, never recovery. Maintain a process-local notified latch: successful delivery latches, observed available quota rearms, failure retries on the next cycle. Leader election prevents concurrent replica sends but restarts/leader changes may repeat an alert.
## Risks / Trade-offs
Notifications reflect quota observations, not guaranteed request eligibility. Ordinary cooldown, authentication, model-source capacity, and scoped key assignment are outside this alert. No durable outbox: a crash after delivery can repeat; failure is retried once per refresh cycle. Requests time out after ten seconds and are awaited by the existing scheduler.
## Migration Plan
Add one nullable encrypted column on the current Alembic head. Existing rows need no backfill: NULL disables notifications. The settings cache supplies the destination each cycle and changes reset suppression. Configure or clear the URL in Settings without restarting.
## Open Questions
None.
