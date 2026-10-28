## Why
Admins need to compare recent consumption across API keys. The overview currently exposes only lifetime totals.

## What Changes
- Add a 7 days / Lifetime selector to the API key overview, defaulting to 7 days.
- Add an optional bounded usage window to the existing key-list API without changing its default.
- Preserve API-key read permissions and the selected-key detail chart.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `frontend-architecture`: seven-day API-key overview.

## Impact
API-key list repository/service/route, APIs page, translations, and regression tests. No schema migration or new settings.
