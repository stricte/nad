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


def map_volumio_status_to_event(payload):
    if not isinstance(payload, dict):
        return None

    raw_status = extract_raw_status(payload)
    if not isinstance(raw_status, str):
        return None

    return STATUS_TO_EVENT.get(raw_status.lower())


def extract_raw_status(payload):
    return payload.get("status") or payload.get("state") or payload.get("playerState")


def iter_notification_payloads(payload):
    if isinstance(payload, dict):
        raw_status = extract_raw_status(payload)
        if isinstance(raw_status, str):
            yield payload

        for key in ("notification", "payload", "data"):
            nested_payload = payload.get(key)
            if isinstance(nested_payload, dict):
                yield from iter_notification_payloads(nested_payload)

        for key in ("notifications", "events", "items"):
            nested_payloads = payload.get(key)
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


def handle_notification_request(path, body, event_router, logger, config):
    if path != config.http_ingress_path:
        return 404, b"Not Found"

    if len(body) > config.http_ingress_max_body_bytes:
        logger.warning(
            "Dropping oversized HTTP ingress payload "
            f"bytes={len(body)} limit={config.http_ingress_max_body_bytes}"
        )
        return 413, b"Payload Too Large"

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Dropping invalid HTTP ingress payload")
        return 400, b"Invalid JSON payload"

    notification_events = extract_notification_events(payload)
    if len(notification_events) == 0:
        logger.warning(f"Dropping unsupported HTTP ingress payload payload={payload}")
        return 202, b"Ignored"

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

    return 202, b"Accepted"


class HTTPIngressHandler(BaseHTTPRequestHandler):
    event_router = None
    logger = None
    app_config = None

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(
            min(content_length, self.app_config.http_ingress_max_body_bytes + 1)
        )
        status_code, response_body = handle_notification_request(
            self.path,
            body,
            self.event_router,
            self.logger,
            self.app_config,
        )

        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, _format, *_args):
        return


class HTTPIngressServer:
    def __init__(self, event_router, logger, app_config) -> None:
        self.event_router = event_router
        self.logger = logger
        self.app_config = app_config
        self.server = None
        self.thread = None

    def start(self):
        if not self.app_config.http_ingress_enabled:
            return

        handler = type("ConfiguredHTTPIngressHandler", (HTTPIngressHandler,), {})
        handler.event_router = self.event_router
        handler.logger = self.logger
        handler.app_config = self.app_config

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
            f"shadow_mode={self.app_config.http_ingress_shadow_mode}"
        )

    def stop(self):
        if self.server is None:
            return

        self.server.shutdown()
        self.server.server_close()
        self.server = None
        self.thread = None
