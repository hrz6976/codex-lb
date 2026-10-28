## ADDED Requirements

### Requirement: API key overview supports a seven-day usage window
The APIs page MUST offer `7 days` (default) and `Lifetime` usage windows with matching aggregate labels and separate query caches. The key-list API MUST accept `usageWindow=7d` and `usageWindow=lifetime`, default to lifetime, and reject other values. Seven-day summaries MUST aggregate non-warmup requests per key in [now minus seven days, now) UTC. Existing API-key read permissions MUST apply to both windows.

#### Scenario: Recent usage differs from lifetime
- **GIVEN** a key has requests both within and before the last seven days
- **WHEN** an administrator selects 7 days
- **THEN** only requests within the bounded window contribute to the overview
- **AND** selecting Lifetime restores lifetime totals

#### Scenario: Existing clients retain lifetime totals
- **WHEN** a client lists API keys without usageWindow
- **THEN** usageSummary retains its lifetime meaning

#### Scenario: Restricted users cannot read recent usage
- **WHEN** a principal without api_keys:read opens the APIs page
- **THEN** no key list or usage queries run and no cached overview is rendered
