## Why
Operators need a phone notification when every enabled account has exhausted usable quota. There is no notification adapter in this repository.
## What Changes
- Add an optional encrypted, dashboard-managed Bark destination secret and send an exhaustion notification from the existing usage refresh job.
- Suppress repeats until observed recovery, retry failed sends, and bound network time.
## Capabilities
### New Capabilities
- `pool-notifications`: optional pool exhaustion alerts.
### Modified Capabilities
None.
## Impact
Usage scheduler, configuration secret/tier inventory, Bark sender, tests, and operator docs. A nullable encrypted dashboard-settings column, a security-gated settings endpoint and a Settings card manage the T2 secret. No environment setting or new dependency. Existing installations remain disabled.
