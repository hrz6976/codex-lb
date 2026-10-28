## Why
Guests on this deployment need to compare API-key usage over the recent seven days without administering keys.

## What Changes
- Grant guests API-key reads and retain write protection.
- Mask account emails in usage details for principals without account write permission.

## Capabilities
### Modified Capabilities
- `admin-auth`: Guest API-key read access.

## Impact
Guest permissions, API usage responses, dashboard integration tests and authentication documentation.
