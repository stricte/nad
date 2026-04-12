import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


STATUS_TO_EVENT = {
    "play": "playing",
    "playing": "playing",
    "pause": "paused",
    "paused": "paused",
    "stop": "stopped",
    "stopped": "stopped",
}

IGNORED_NOTIFICATION_ITEMS = {
    "queue",
    "volume",
}


def map_volumio_status_to_event(payload):
    if not isinstance(payload, dict):
        return None

    raw_status = extract_raw_status(payload)
    if not isinstance(raw_status, str):
        return None

    return STATUS_TO_EVENT.get(raw_status.lower())


def extract_raw_status(payload):
    return payload.get("status") or payload.get("state") or payload.get("playerState")


def should_extract_notification_payload(payload):
    if not isinstance(payload, dict):
        return False

    raw_status = extract_raw_status(payload)
    if not isinstance(raw_status, str):
        return False

    item = payload.get("item")
    if isinstance(item, str) and item.lower() in IGNORED_NOTIFICATION_ITEMS:
        return False

    return True


def should_recurse_into_nested_data(payload):
    item = payload.get("item")
    if not isinstance(item, str):
        return True

    return item.lower() not in IGNORED_NOTIFICATION_ITEMS


def iter_notification_payloads(payload):
    if isinstance(payload, dict):
        if should_extract_notification_payload(payload):
            yield payload

        for key in ("notification", "payload", "data"):
            nested_payload = payload.get(key)
            if key == "data" and not should_recurse_into_nested_data(payload):
                continue
            if isinstance(nested_payload, dict):
                yield from iter_notification_payloads(nested_payload)

        for key in ("notifications", "events", "items"):
            nested_payloads = payload.get(key)
            if key == "items" and not should_recurse_into_nested_data(payload):
                continue
            if isinstance(nested_payloads, list):
                yield from iter_notification_payloads(nested_payloads)
        return

    if isinstance(payload, list):
        for item in payload:
            yield from iter_notification_payloads(item)


def extract_notification_events(payload):
    notification_events = []

    for notification_payload in iter_notification_payloads(payload):
        mapped_event = map_volumio_status_to_event(notification_payload)
        if mapped_event is None:
            continue

        notification_events.append(
            (
                mapped_event,
                extract_raw_status(notification_payload),
                notification_payload,
            )
        )

    return notification_events


class HTTPIngressMetrics:
    def __init__(self) -> None:
        self.accepted_requests = 0
        self.ignored_requests = 0
        self.invalid_requests = 0
        self.oversized_requests = 0
        self.routed_events = 0

    def as_dict(self):
        return {
            "accepted_requests": self.accepted_requests,
            "ignored_requests": self.ignored_requests,
            "invalid_requests": self.invalid_requests,
            "oversized_requests": self.oversized_requests,
            "routed_events": self.routed_events,
        }


def build_status_payload(config, metrics, registration_status=None):
    payload = {
        "http_ingress_enabled": config.http_ingress_enabled,
        "http_ingress_shadow_mode": config.http_ingress_shadow_mode,
        "http_ingress_host": config.http_ingress_host,
        "http_ingress_port": config.http_ingress_port,
        "http_ingress_path": config.http_ingress_path,
        "http_ingress_status_path": config.http_ingress_status_path,
        "http_ingress_max_body_bytes": config.http_ingress_max_body_bytes,
        "metrics": metrics.as_dict(),
    }
    if registration_status is not None:
        payload["volumio_registration"] = registration_status

    return payload


def handle_status_request(path, config, metrics, registration_status=None):
    if path != config.http_ingress_status_path:
        return 404, b"Not Found", "text/plain; charset=utf-8"

    response_body = json.dumps(
        build_status_payload(config, metrics, registration_status=registration_status)
    ).encode("utf-8")
    return 200, response_body, "application/json; charset=utf-8"


def handle_notification_request(path, body, event_router, logger, config, metrics):
    if path != config.http_ingress_path:
        return 404, b"Not Found", "text/plain; charset=utf-8"

    if len(body) > config.http_ingress_max_body_bytes:
        logger.warning(
            "Dropping oversized HTTP ingress payload "
            f"bytes={len(body)} limit={config.http_ingress_max_body_bytes}"
        )
        metrics.oversized_requests += 1
        return 413, b"Payload Too Large", "text/plain; charset=utf-8"

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Dropping invalid HTTP ingress payload")
        metrics.invalid_requests += 1
        return 400, b"Invalid JSON payload", "text/plain; charset=utf-8"

    notification_events = extract_notification_events(payload)
    if len(notification_events) == 0:
        logger.warning(f"Dropping unsupported HTTP ingress payload payload={payload}")
        metrics.ignored_requests += 1
        return 202, b"Ignored", "text/plain; charset=utf-8"

    for mapped_event, raw_status, notification_payload in notification_events:
        logger.info(
            "Accepted HTTP ingress event "
            f"source=volumio_http raw_status={raw_status} "
            f"mapped_event={mapped_event} shadow_mode={config.http_ingress_shadow_mode}"
        )

        if not config.http_ingress_shadow_mode:
            event_router.route_event(
                mapped_event,
                source="volumio_http",
                raw_payload=notification_payload,
            )
            metrics.routed_events += 1

    metrics.accepted_requests += 1
    return 202, b"Accepted", "text/plain; charset=utf-8"


class HTTPIngressHandler(BaseHTTPRequestHandler):
    event_router = None
    logger = None
    app_config = None
    metrics = None
    status_provider = None

    def do_GET(self):
        registration_status = None
        if self.status_provider is not None:
            registration_status = self.status_provider()
        status_code, response_body, content_type = handle_status_request(
            self.path,
            self.app_config,
            self.metrics,
            registration_status=registration_status,
        )
        self.__write_response(status_code, response_body, content_type)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(
            min(content_length, self.app_config.http_ingress_max_body_bytes + 1)
        )
        status_code, response_body, content_type = handle_notification_request(
            self.path,
            body,
            self.event_router,
            self.logger,
            self.app_config,
            self.metrics,
        )
        self.__write_response(status_code, response_body, content_type)

    def __write_response(self, status_code, response_body, content_type):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, _format, *_args):
        return


class HTTPIngressServer:
    def __init__(self, event_router, logger, app_config, status_provider=None) -> None:
        self.event_router = event_router
        self.logger = logger
        self.app_config = app_config
        self.status_provider = status_provider
        self.metrics = HTTPIngressMetrics()
        self.server = None
        self.thread = None

    def start(self):
        if not self.app_config.http_ingress_enabled:
            return

        handler = type("ConfiguredHTTPIngressHandler", (HTTPIngressHandler,), {})
        handler.event_router = self.event_router
        handler.logger = self.logger
        handler.app_config = self.app_config
        handler.metrics = self.metrics
        if self.status_provider is None:
            handler.status_provider = None
        else:
            handler.status_provider = staticmethod(self.status_provider)

        self.server = ThreadingHTTPServer(
            (self.app_config.http_ingress_host, self.app_config.http_ingress_port),
            handler,
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.logger.info(
            "Started HTTP ingress "
            f"host={self.app_config.http_ingress_host} "
            f"port={self.app_config.http_ingress_port} "
            f"path={self.app_config.http_ingress_path} "
            f"status_path={self.app_config.http_ingress_status_path} "
            f"shadow_mode={self.app_config.http_ingress_shadow_mode}"
        )

    def stop(self):
        if self.server is None:
            return

        self.server.shutdown()
        self.server.server_close()
        self.server = None
        self.thread = None

    def address(self):
        if self.server is None:
            return None

        return self.server.server_address
