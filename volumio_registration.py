import json
from datetime import datetime, timedelta
import urllib.error
import urllib.request


class VolumioRegistrationClient:
    def __init__(self, logger, config, urlopen=urllib.request.urlopen) -> None:
        self.logger = logger
        self.config = config
        self.urlopen = urlopen

    def register_callback(self) -> bool:
        if not self.config.volumio_registration_enabled:
            return False

        payload = {
            "url": self.config.volumio_notification_callback_url,
        }
        request = urllib.request.Request(
            f"{self.config.volumio_base_url}{self.config.volumio_registration_path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with self.urlopen(
                request,
                timeout=self.config.volumio_registration_timeout_seconds,
            ) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            self.logger.warning(
                "Volumio callback registration failed "
                f"base_url={self.config.volumio_base_url} "
                f"callback_url={self.config.volumio_notification_callback_url} "
                f"error={exc}"
            )
            return False

        if status_code < 200 or status_code >= 300:
            self.logger.warning(
                "Volumio callback registration returned non-success "
                f"status_code={status_code} response_body={response_body}"
            )
            return False

        self.logger.info(
            "Registered Volumio callback "
            f"base_url={self.config.volumio_base_url} "
            f"callback_url={self.config.volumio_notification_callback_url} "
            f"status_code={status_code}"
        )
        return True


class VolumioRegistrationManager:
    def __init__(self, client, logger, config) -> None:
        self.client = client
        self.logger = logger
        self.config = config
        self.last_success_at = None
        self.last_failure_at = None
        self.next_attempt_at = None
        self.failure_count = 0

    def ensure_registration(self, now=None) -> bool:
        if not self.config.volumio_registration_enabled:
            return False

        now = now or datetime.now()
        if self.next_attempt_at is not None and now < self.next_attempt_at:
            return False

        registered = self.client.register_callback()
        if registered:
            self.last_success_at = now
            self.failure_count = 0
            self.next_attempt_at = now + timedelta(
                seconds=self.config.volumio_registration_refresh_interval_seconds
            )
            self.logger.info(
                "Scheduled next Volumio registration refresh "
                f"next_attempt_at={self.next_attempt_at.isoformat()}"
            )
            return True

        self.last_failure_at = now
        self.failure_count += 1
        retry_delay_seconds = min(
            self.config.volumio_registration_retry_initial_delay_seconds
            * (2 ** (self.failure_count - 1)),
            self.config.volumio_registration_retry_max_delay_seconds,
        )
        self.next_attempt_at = now + timedelta(seconds=retry_delay_seconds)
        self.logger.warning(
            "Scheduled Volumio registration retry "
            f"failure_count={self.failure_count} "
            f"next_attempt_at={self.next_attempt_at.isoformat()}"
        )
        return False
