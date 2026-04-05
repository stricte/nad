# ISSUE-003: Add source-aware structured logging

## Tasks
- Include `source`, `raw_status`, `mapped_event`, and `deduped` fields in logs.
- Ensure both MQTT and future HTTP ingress paths use same logging format.

## Acceptance criteria
- Operators can trace event lifecycle from ingress to processing.
