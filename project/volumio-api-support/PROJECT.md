# Project: Volumio API Event Ingestion Migration

This project converts the architecture plan in `docs/volumio-api-support-plan.md` into executable work items.

## Goal
Decouple ingestion from processing so events can come from multiple producers (starting with Volumio REST notifications) without requiring script-based event senders.

## Milestones

### M1 — Decoupling foundation (Phase A)
- [ ] ISSUE-001 Create normalized event contract (`EventEnvelope`)
- [ ] ISSUE-002 Build `EventRouter` and route MQTT through it
- [ ] ISSUE-003 Add source-aware structured logging
- [ ] ISSUE-004 Add router unit tests

### M2 — Volumio HTTP listener (Phase B)
- [ ] ISSUE-005 Add HTTP ingress service skeleton
- [ ] ISSUE-006 Implement Volumio payload mapping
- [ ] ISSUE-007 Add HTTP ingress integration tests
- [ ] ISSUE-008 Add feature flags for ingress channels

### M3 — Registration lifecycle (Phase C)
- [ ] ISSUE-009 Implement Volumio callback registration client
- [ ] ISSUE-010 Add retry/backoff and periodic refresh
- [ ] ISSUE-011 Add health/diagnostics for registration state

### M4 — Multi-producer hardening (Phase D)
- [ ] ISSUE-012 Add dedupe window and idempotency handling
- [ ] ISSUE-013 Add precedence policy for multiple active producers
- [ ] ISSUE-014 Add out-of-order event handling
- [ ] ISSUE-015 Add rollout/runbook documentation and smoke scripts

## Prioritization
1. Complete all M1 items before enabling HTTP ingress.
2. Deliver M2 in shadow mode first (log-only), then activate routing.
3. Keep MQTT/librespot path as fallback until M4 is stable.

## Definition of done
- All issues in M1–M4 closed.
- End-to-end test passes for MQTT and Volumio HTTP sources.
- Operational docs include deployment, rollback, and incident checks.


## GitHub import
Use `project/volumio-api-support/GITHUB_IMPORT.md` and `scripts/create_github_project_and_issues.py` to create the project and issues directly in GitHub.
