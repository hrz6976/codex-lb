## Context
The APIs page already separates read and write permissions.

## Goals / Non-Goals
Enable guest usage inspection; preserve mutation restrictions.

## Decisions
Add API_KEYS_READ at ALL scope only to the guest preset. Keep the viewer preset unchanged. Reuse the existing APIs page, queries and masking helper.

## Risks / Trade-offs
Guests can see key names, prefixes, limits and assignments, but never plaintext keys. Anonymous access exposes this inventory when guest access is enabled.
