# Plan: decouple event ingestion and add Volumio REST notification support

## 1) Current-state analysis (why it is tightly coupled today)

The current flow is strongly tied to `librespot` script hooks:

1. `sender.py` reads one environment variable (`PLAYER_EVENT`) and only accepts four hard-coded events (`started`, `stopped`, `paused`, `playing`).
2. It publishes those events to MQTT (`config.broker_topic`).
3. `receiver.py` only consumes MQTT and forwards incoming event names into `Processor`.
4. `Processor` and `CommandProcessors` contain the behavior logic for delayed pause and state transitions, then they call NAD serial commands.

This design is clean for one producer (librespot script), but adding other apps currently requires either:

- creating another script that emulates `sender.py`, or
- publishing directly to the same MQTT topic with the exact expected event names.

### Coupling points in code

- Producer coupling: `sender.py` depends on env var + fixed event list.
- Transport coupling: `receiver.py` is MQTT-only.
- Schema coupling: events are plain strings with no source metadata or correlation id.
- Processing entry point: `Processor.process(received_event)` only accepts one normalized event string.

## 2) Target architecture (decoupling first)

Introduce a simple ingestion boundary in front of `Processor`:

- **EventEnvelope** (internal normalized payload), e.g.
  - `event_name` (`playing`, `paused`, etc.)
  - `source` (`librespot_script`, `volumio_rest_notification`, `manual`, ...)
  - `received_at`
  - optional `raw_payload`
- **Ingress adapters** map external payloads into `EventEnvelope`.
- **Event router** validates, normalizes, and forwards only `event_name` to existing `Processor` initially.

This gives backward compatibility while creating a place to add multiple input channels.

### Proposed module split

- `ingress/base.py` – shared adapter interface
- `ingress/mqtt_ingress.py` – wraps existing MQTT callback path
- `ingress/http_ingress.py` – new HTTP listener for Volumio notifications
- `events.py` – envelope + normalization utilities
- `event_router.py` – dedupe, validation, dispatch to `Processor`

> Keep `Processor` and `CommandProcessors` unchanged in phase 1.

## 3) Add Volumio REST notification listener (API-based producer)

Volumio supports notification registration through the REST API (historically via `pushNotificationUrls` endpoint), allowing Volumio to push state updates to a callback URL.

### Listener responsibilities

1. Expose an HTTP endpoint in this service, e.g.:
   - `POST /ingress/volumio/notifications`
2. Accept Volumio notification payload(s) and extract playback status.
3. Map Volumio states to internal events:
   - `play` -> `playing`
   - `pause` -> `paused`
   - `stop` -> `stopped`
4. Submit normalized event via `EventRouter`.
5. Return fast `2xx` response; do heavy work asynchronously in-process queue.

### Registration flow

- New helper command/service registers callback URL on startup:
  - call Volumio REST endpoint to register `http://<nad-host>:<port>/ingress/volumio/notifications`
- Add periodic re-registration (startup + interval) to survive Volumio reboot/network churn.
- Add unregister on shutdown when feasible.

### Security and network controls

- Bind listener to LAN interface only.
- Optional shared secret in query/header.
- Accept-list Volumio IP.
- Request-size limit + JSON parsing guardrails.

## 4) Detailed implementation phases

## Phase A — Refactor without behavior change

- Extract an ingress-agnostic `EventRouter`.
- Route current MQTT messages through router.
- Preserve existing command processing semantics.

**Done criteria**
- Existing librespot->MQTT path functions exactly as before.
- Event logs include source + normalized event.

## Phase B — HTTP listener for Volumio notifications

- Add lightweight HTTP server (Flask/FastAPI or stdlib-based).
- Implement Volumio payload parser + state mapping.
- Emit to router.

**Done criteria**
- Volumio push for play/pause/stop produces same NAD behavior as MQTT events.

## Phase C — Volumio registration lifecycle

- Add startup registration call to Volumio notification API.
- Add periodic refresh + retry with backoff.
- Add health metric/log for registration status.

**Done criteria**
- Restarting Volumio or NAD service restores notifications automatically.

## Phase D — Multi-producer support hardening

- Add source-aware dedupe window (avoid duplicate `playing` bursts).
- Optional priority/precedence rules if multiple producers active.
- Add replay-safe handling for out-of-order notifications.

**Done criteria**
- Stable operation with both MQTT/librespot and Volumio API enabled.

## 5) Data contract and mapping strategy

Define a strict internal event vocabulary:

- supported internal events: `started`, `playing`, `paused`, `stopped`, plus existing manual events (`power_on`, `power_off`, etc.)
- unknown external states -> log + drop (do not crash)

Mapping table should live in one place (`events.py`) to avoid duplicated logic across adapters.

## 6) Operational plan

- New config section:
  - `ingress.mqtt.enabled` (default true)
  - `ingress.http.enabled` (default false initially)
  - `ingress.http.host`, `ingress.http.port`, `ingress.http.secret`
  - `volumio.base_url`, `volumio.notification_callback_url`, `volumio.register_interval_sec`
- Add systemd unit updates if HTTP listener is in same process (port exposure).
- Add log fields: `source`, `raw_status`, `mapped_event`, `deduped`.

## 7) Test strategy

- Unit tests:
  - Volumio payload -> internal event mapping
  - dedupe behavior
  - router validation of unknown events
- Integration tests:
  - MQTT ingress -> router -> processor
  - HTTP notification ingress -> router -> processor
- Smoke test scripts:
  - send sample Volumio notification payloads by `curl`
  - verify serial commands emitted for play/pause/stop

## 8) Rollout approach

1. Deploy Phase A with no external behavior change.
2. Enable HTTP ingress in shadow mode (log-only) and compare with MQTT events.
3. Enable active HTTP ingress for one device.
4. Gradually switch more devices; keep MQTT path as fallback.
5. Once stable, make script-based sender optional/deprecated (not removed immediately).

## 9) Risks and mitigations

- **Duplicate events from multiple sources** -> dedupe window + source tagging.
- **Volumio payload drift** -> tolerant parser + strict mapping fallback.
- **Listener unavailable** -> health checks + restart policy + startup re-registration.
- **Network exposure** -> bind LAN-only + secret + source IP filter.

## 10) Recommended first deliverable in this repo

Implement **Phase A + minimal Phase B skeleton** first:

- keep current MQTT flow untouched for production safety;
- add internal router abstraction;
- add an HTTP endpoint that only logs mapped events initially (feature-flagged), then switch to active dispatch.

That sequence minimizes regression risk while establishing the right architecture for app/API-based event producers.

## 11) Execution project and issue backlog

This plan is now tracked as a project backlog under:

- `project/volumio-api-support/PROJECT.md`
- `project/volumio-api-support/issues/`

The backlog contains 15 issues mapped to phases A-D so implementation can proceed incrementally with clear acceptance criteria.
