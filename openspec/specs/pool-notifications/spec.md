# pool-notifications Specification

## Purpose
TBD - created by archiving change add-bark-pool-exhaustion-alerts. Update Purpose after archive.

## Requirements

### Requirement: Optional Bark exhaustion notifications
The system MUST support an optional secret Bark URL and MUST send a Bark V2 notification when a nonempty enabled account pool is observed to have exhausted usable quota. With no destination configured it MUST perform no quota reads or notification network calls. The destination secret MUST NOT appear in logs or outgoing request URLs.

#### Scenario: All enabled accounts exhaust quota
- **GIVEN** fresh, nonexpired applicable quota windows prove every enabled account exhausted
- **WHEN** a leader completes a usage-refresh cycle with a configured Bark destination
- **THEN** it sends a notification containing the number of exhausted accounts
- **AND** paused, deactivated, reauthentication-required, and deletion-pending accounts are excluded

#### Scenario: Missing evidence does not trigger an alert
- **WHEN** the pool is empty or any account has insufficient fresh quota data
- **THEN** no exhaustion notification is sent
- **AND** stale or expired windows are not treated as zero remaining quota

#### Scenario: Purchased credits remain usable
- **WHEN** long-window quota is exhausted but usable purchased credits remain and the short window is not exhausted
- **THEN** that account prevents an all-accounts-exhausted alert

### Requirement: Bounded notification delivery and repeat suppression
Notification delivery MUST run under the existing usage scheduler's leadership and task ownership. Network I/O MUST occur after database-session cleanup, time out within ten seconds, and propagate cancellation. A successful send MUST suppress repeats until observed recovery in the same process. Failed delivery MUST remain retryable on later cycles without failing usage refresh.

#### Scenario: Repeated exhaustion and recovery
- **WHEN** consecutive cycles observe an exhausted pool after successful notification
- **THEN** no additional notification is sent
- **AND** observing usable quota rearms notification for a later exhaustion episode

#### Scenario: Delivery fails
- **WHEN** Bark returns an HTTP error, unsuccessful application code, malformed response, or times out
- **THEN** usage refresh continues and the next exhausted cycle can retry

#### Scenario: Unknown data after delivery
- **WHEN** usage becomes stale or the pool becomes empty after a notification
- **THEN** repeat suppression remains set until usable quota is observed

### Requirement: Dashboard management of the Bark secret
The system MUST store the optional destination encrypted in the database. Only principals with security:write MUST be allowed to read its configured status or replace/clear it. Reads MUST return only a boolean. Writes MUST validate an HTTP(S) server plus device-key URL without userinfo, query, or fragment. Clearing the destination MUST disable delivery on subsequent refresh cycles without restart.

#### Scenario: Configure and clear notifications
- **WHEN** an authorized administrator saves a valid Bark URL in Settings
- **THEN** the database stores ciphertext and the response reports configured without returning the URL
- **AND** clearing the destination stores NULL and reports disabled

#### Scenario: Existing deployment upgrades
- **WHEN** the migration adds the nullable secret column
- **THEN** existing settings rows retain their values and notifications remain disabled
- **AND** downgrade removes only the added column

#### Scenario: Unauthorized configuration
- **WHEN** a principal without security:write reads or modifies notification settings
- **THEN** the server denies the request and the UI does not mount the notification card
