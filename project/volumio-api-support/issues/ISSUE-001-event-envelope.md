# ISSUE-001: Create normalized event contract (`EventEnvelope`)

## Background
Current processing accepts only raw event strings.

## Tasks
- Create an event envelope object with `event_name`, `source`, `received_at`, `raw_payload`.
- Add validation for supported event names.
- Keep compatibility with existing string events.

## Acceptance criteria
- Router and ingress code can create and consume envelopes.
- Unknown events are rejected safely with logs.
