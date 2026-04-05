class AppConfig:
    def __init__(self):
        self.broker_ip = "127.0.0.1"
        self.broker_port = 1883
        self.broker_topic = "nad"
        self.event_dedupe_window_seconds = 0
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
        self.logger_name = "mqtt_receive"
        self.logger_path = "/var/log/nad/mqtt_receive.log"
        self.serial = "/dev/ttyUSB0"
        self.daemon_pid = "/var/run/nad/mqtt_receive.pid"


config = AppConfig()
