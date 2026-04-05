# ISSUE-002: Build `EventRouter` and route MQTT through it

## Tasks
- Add `EventRouter` that normalizes and dispatches to `Processor`.
- Replace direct `processor.process(received_command)` call path in MQTT handler with router.
- Keep current behavior identical for existing events.

## Acceptance criteria
- Existing MQTT flow continues to drive NAD commands unchanged.
- Logs show source + normalized event.
