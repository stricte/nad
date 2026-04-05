import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


STATUS_TO_EVENT = {
    "play": "playing",
    "pause": "paused",
    "stop": "stopped",
}


def map_volumio_status_to_event(payload):
    if not isinstance(payload, dict):
        return None

    raw_status = payload.get("status") or payload.get("state") or payload.get("playerState")
    if not isinstance(raw_status, str):
        return None

    return STATUS_TO_EVENT.get(raw_status.lower())


def handle_notification_request(path, body, event_router, logger, config):
    if path != config.http_ingress_path:
        return 404, b"Not Found"

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Dropping invalid HTTP ingress payload")
        return 400, b"Invalid JSON payload"

    mapped_event = map_volumio_status_to_event(payload)
    if mapped_event is None:
        logger.warning(f"Dropping unsupported HTTP ingress payload payload={payload}")
        return 202, b"Ignored"

    logger.info(
        "Accepted HTTP ingress event "
        f"source=volumio_http raw_status={payload.get('status') or payload.get('state') or payload.get('playerState')} "
        f"mapped_event={mapped_event} shadow_mode={config.http_ingress_shadow_mode}"
    )

    if not config.http_ingress_shadow_mode:
        event_router.route_event(
            mapped_event,
            source="volumio_http",
            raw_payload=payload,
        )

    return 202, b"Accepted"


class HTTPIngressHandler(BaseHTTPRequestHandler):
    event_router = None
    logger = None
    app_config = None

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
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
