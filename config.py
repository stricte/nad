class AppConfig:
    def __init__(self):
        self.broker_ip = "127.0.0.1"
        self.broker_port = 1883
        self.broker_topic = "nad"
        self.event_dedupe_window_seconds = 0
        self.stale_event_window_seconds = 0
        self.source_precedence_window_seconds = 0
        self.source_priorities = {
            "mqtt": 100,
            "volumio_http": 200,
        }
        self.mqtt_ingress_enabled = True
        self.http_ingress_enabled = False
        self.http_ingress_shadow_mode = True
        self.http_ingress_host = "127.0.0.1"
        self.http_ingress_port = 8080
        self.http_ingress_path = "/ingress/volumio/notifications"
        self.http_ingress_status_path = "/ingress/status"
        self.http_ingress_max_body_bytes = 16384
        self.volumio_registration_enabled = False
        self.volumio_base_url = "http://127.0.0.1"
        self.volumio_registration_path = "/api/v1/pushNotificationUrls"
        self.volumio_notification_callback_url = (
            "http://127.0.0.1:8080/ingress/volumio/notifications"
        )
        self.volumio_registration_timeout_seconds = 5
        self.volumio_registration_refresh_interval_seconds = 3600
        self.volumio_registration_retry_initial_delay_seconds = 5
        self.volumio_registration_retry_max_delay_seconds = 300
        self.receiver_loop_idle_sleep_seconds = 0.1
        self.serial = "/dev/ttyUSB0"


config = AppConfig()
