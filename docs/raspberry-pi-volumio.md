# Raspberry Pi Installation On Volumio

This guide installs the NAD automation bridge on a Raspberry Pi running Volumio OS or another Debian-based system.

## Goal

The recommended topology on Volumio is:

- Volumio runs on the Raspberry Pi
- this project runs on the same Raspberry Pi as a systemd service
- the receiver listens on `127.0.0.1:8080`
- Volumio sends playback notifications to the local HTTP ingress
- the receiver translates those notifications into NAD RS232 commands

This avoids depending on the older librespot `PLAYER_EVENT` hook and keeps Volumio as the primary event producer.

## Hardware Assumptions

- Raspberry Pi running Volumio or Debian
- NAD amplifier connected over RS232
- working USB-to-RS232 adapter, usually exposed as `/dev/ttyUSB0`
- network access from the Pi to itself and, if needed, to an MQTT broker

## Before Installing

Confirm the serial adapter path:

```bash
ls -l /dev/ttyUSB*
```

If the adapter is not `/dev/ttyUSB0`, update `self.serial` in `/opt/nad/config.py` after installation.

If you want to use the legacy MQTT/librespot path instead of Volumio HTTP ingress, keep a reachable MQTT broker ready and do not enable Volumio registration.

## Install

From the checked-out repository:

```bash
sudo ./scripts/install_raspberry_pi.sh
```

The installer:

- creates a dedicated system user `nad`
- adds `nad` to the `dialout` group for serial access
- installs OS packages required for Python and serial/MQTT operation
- deploys the app into `/opt/nad`
- creates a virtual environment in `/opt/nad/venv`
- installs Python dependencies into that virtual environment
- installs `nad-receive.service`
- enables the service in systemd

The installer does not overwrite your runtime configuration if `/opt/nad/config.py` already exists.

## Configure For Volumio

Copy the Volumio example config:

```bash
sudo cp /opt/nad/examples/config.volumio_localhost.py /opt/nad/config.py
sudo nano /opt/nad/config.py
```

If you want the legacy MQTT/librespot setup instead, use:

```bash
sudo cp /opt/nad/examples/config.legacy_mqtt.py /opt/nad/config.py
```

For the Volumio example, the main value you will usually need to adjust is:

```python
self.serial = "/dev/ttyUSB0"
```

The Volumio example already sets:

- `mqtt_ingress_enabled = False`
- `http_ingress_enabled = True`
- `http_ingress_shadow_mode = True`
- `volumio_registration_enabled = True`
- `volumio_base_url = "http://127.0.0.1:3000"`
- `volumio_notification_callback_url = "http://127.0.0.1:8080/ingress/volumio/notifications"`

Volumio commonly exposes its local API on port `3000`. Verify the API before restarting the service:

```bash
curl -i http://127.0.0.1:3000/api/v1/pushNotificationUrls
```

If your Volumio installation listens on a different port, update `self.volumio_base_url` in `/opt/nad/config.py`.

## Start And Inspect

Restart the service after config changes:

```bash
sudo systemctl restart nad-receive.service
sudo systemctl status nad-receive.service
```

Follow logs:

```bash
journalctl -u nad-receive.service -f
```

Check the ingress status endpoint:

```bash
curl http://127.0.0.1:8080/ingress/status
```

You should see:

- HTTP ingress enabled
- the configured paths and port
- request counters
- Volumio registration health when registration is enabled

## Shadow Mode Rollout

Start with:

```python
self.http_ingress_shadow_mode = True
```

In shadow mode the service:

- accepts Volumio notifications
- parses and logs mapped events
- does not forward them to the NAD command processor

Use this to validate that the notification stream looks correct before allowing the service to control the amplifier.

When the logs look correct, disable shadow mode:

```python
self.http_ingress_shadow_mode = False
```

Then restart the service:

```bash
sudo systemctl restart nad-receive.service
```

## Smoke Tests

### 1. Service health

```bash
sudo systemctl is-active nad-receive.service
curl http://127.0.0.1:8080/ingress/status
```

### 2. Manual HTTP notification

With shadow mode disabled:

```bash
curl -i \
  -H 'Content-Type: application/json' \
  -d '{"status":"play"}' \
  http://127.0.0.1:8080/ingress/volumio/notifications
```

Expected result:

- HTTP `202 Accepted`
- service log shows an accepted Volumio event
- NAD command processing follows according to the existing command logic

### 3. Serial access

Check that the service user can see the serial device:

```bash
id nad
ls -l /dev/ttyUSB0
```

The `nad` user should be in the `dialout` group.

### 4. Registration health

If `volumio_registration_enabled = True`, inspect:

```bash
curl http://127.0.0.1:8080/ingress/status
```

Look for:

- `enabled: true`
- `last_success_at`
- `next_attempt_at`
- low or zero `failure_count`

## Legacy MQTT/librespot Mode

If you need the old event flow instead:

1. Set `self.mqtt_ingress_enabled = True`
2. Set `self.http_ingress_enabled = False`
3. Ensure `mosquitto` or another broker is available
4. Configure librespot:

```bash
LIBRESPOT_ONEVENT="/opt/nad/venv/bin/python /opt/nad/sender.py"
```

The sender publishes only:

- `started`
- `playing`
- `paused`
- `stopped`

## Service Management

Useful commands:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nad-receive.service
sudo systemctl restart nad-receive.service
sudo systemctl stop nad-receive.service
sudo systemctl status nad-receive.service
journalctl -u nad-receive.service -n 200
```

## Updating The Deployment

From a newer checkout of the repository:

```bash
sudo ./scripts/install_raspberry_pi.sh
sudo systemctl restart nad-receive.service
```

The installer will redeploy the code and refresh the virtual environment. Existing `/opt/nad/config.py` is preserved.

## Troubleshooting

### HTTP ingress status endpoint is unreachable

- confirm `self.http_ingress_enabled = True`
- check `sudo systemctl status nad-receive.service`
- check logs with `journalctl -u nad-receive.service -f`
- confirm the bind address and port in `/opt/nad/config.py`

### Volumio registration does not succeed

- verify `self.volumio_base_url`
- check the local Volumio API with `curl -i http://127.0.0.1:3000/api/v1/pushNotificationUrls`
- verify `self.volumio_notification_callback_url`
- use the status endpoint to inspect `failure_count` and `last_failure_at`
- if the callback URL is `127.0.0.1`, this only works when Volumio and this service are on the same device

### Serial device permission denied

- confirm the device path
- confirm `nad` is in `dialout`
- reconnect the USB serial adapter if the path changed

### No NAD reaction after notifications arrive

- verify `http_ingress_shadow_mode = False`
- check logs for accepted events
- test the translator path manually with `cli.py` if needed
