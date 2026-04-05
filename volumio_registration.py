import json
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
