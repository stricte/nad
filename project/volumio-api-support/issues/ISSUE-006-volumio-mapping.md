# ISSUE-006: Implement Volumio payload to internal event mapping

## Tasks
- Parse Volumio notification payload.
- Map `play -> playing`, `pause -> paused`, `stop -> stopped`.
- Send mapped event through `EventRouter`.

## Acceptance criteria
- Simulated Volumio payloads produce expected internal events.
