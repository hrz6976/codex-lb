## MODIFIED Requirements

### Requirement: Dashboard guest access is read-only

The system SHALL support a dashboard `guest` role with read permission and without write permission. The system SHALL continue to treat password-authenticated, trusted-header, disabled-auth, and local bootstrap users as `admin` principals with read and write permissions. Guest read permission SHALL include API-key inventory, trends and recent seven-day usage, without exposing plaintext keys. Usage account emails SHALL be masked for principals without account write permission. Guest read permission covers only guest-safe dashboard data: full conversation archives and request-log filtering by a dedicated conversation identifier MUST require an `admin` principal.

#### Scenario: Guest can read dashboard APIs
- **WHEN** guest access is enabled and a guest principal requests a guest-safe dashboard GET endpoint
- **THEN** the request succeeds using read-only dashboard access
- **AND** the session response identifies the principal as `guest`
- **AND** the session response includes `read` and `api_keys:read:all` without write permissions

#### Scenario: Guest cannot mutate dashboard state
- **WHEN** guest access is enabled and a guest principal requests a dashboard mutating endpoint
- **THEN** the system returns HTTP 403 with error code `read_only_access`
- **AND** no dashboard state is changed

#### Scenario: Guest cannot read conversation archives
- **WHEN** a guest principal requests any conversation-archive endpoint
- **THEN** the system returns HTTP 403 with error code `admin_access_required`
- **AND** no archive file metadata, payload, headers, or other archive record data is returned

#### Scenario: Guest cannot filter request logs by conversation identifier
- **WHEN** a guest principal requests request logs with the dedicated `conversation_id` filter
- **THEN** the system returns HTTP 403 with error code `admin_access_required`
- **AND** no filtered rows, request count, or aggregated conversation cost is returned

#### Scenario: Guest inspects API-key usage
- **WHEN** a guest opens the APIs page
- **THEN** the default comparison shows `7 days` usage and allows switching to Lifetime
- **AND** key creation, editing, regeneration and deletion controls are unavailable
- **AND** the API rejects key mutations with HTTP 403

