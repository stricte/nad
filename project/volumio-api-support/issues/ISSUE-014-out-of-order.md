# ISSUE-014: Handle out-of-order events safely

## Tasks
- Add safeguards for stale or out-of-order notifications.
- Use timestamps/sequence heuristics where available.

## Acceptance criteria
- Stale events do not regress amplifier state unexpectedly.
