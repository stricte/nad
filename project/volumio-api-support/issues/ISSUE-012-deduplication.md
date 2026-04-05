# ISSUE-012: Add dedupe window and idempotency handling

## Tasks
- Add configurable dedupe window for repeated events.
- Implement source-aware idempotency checks.

## Acceptance criteria
- Duplicate bursts (e.g., repeated `playing`) do not cause repeated NAD side effects.
