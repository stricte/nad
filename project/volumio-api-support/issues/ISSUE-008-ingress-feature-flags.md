# ISSUE-008: Add feature flags for ingress channels

## Tasks
- Add config switches: `ingress.mqtt.enabled`, `ingress.http.enabled`.
- Support shadow mode for HTTP ingress (log-only).

## Acceptance criteria
- HTTP ingress can run without affecting NAD command processing in shadow mode.
