# NAD Automation Bridge

This project connects playback events from Volumio or librespot to a NAD amplifier over RS232.

The runtime has three ingress paths:

- `mqtt`: legacy event flow from `sender.py`
- `http_ingress`: Volumio callback endpoint with optional self-registration
- `event_router`: shared normalization, dedupe, source precedence, and stale-event handling

The preferred deployment on a Raspberry Pi running Volumio is:

1. Run `receiver.py` as a systemd service.
2. Enable the HTTP ingress.
3. Enable Volumio callback registration.
4. Keep MQTT/librespot disabled unless you explicitly want the legacy path.

**Files**
- `receiver.py`: main daemon, starts MQTT ingress, HTTP ingress, registration refresh loop, and NAD command processing
- `sender.py`: legacy librespot event hook that publishes MQTT events
- `http_ingress.py`: Volumio notification endpoint and status endpoint
- `volumio_registration.py`: Volumio callback registration and refresh logic
- `nad_receive.service`: systemd unit template for the receiver service
- `scripts/install_raspberry_pi.sh`: installation/bootstrap script for Volumio or Debian on Raspberry Pi
- `docs/raspberry-pi-volumio.md`: full deployment and operations guide

**Quick Start**

On the Raspberry Pi:

```bash
sudo ./scripts/install_raspberry_pi.sh
sudo nano /opt/nad/config.py
sudo systemctl restart nad-receive.service
sudo systemctl status nad-receive.service
```

Then follow the deployment guide in [docs/raspberry-pi-volumio.md](/home/stricte/nad/docs/raspberry-pi-volumio.md).

**Recommended Config For Volumio**

Set these values in `/opt/nad/config.py`:

```python
self.mqtt_ingress_enabled = False
self.http_ingress_enabled = True
self.http_ingress_shadow_mode = True
self.http_ingress_host = "127.0.0.1"
self.http_ingress_port = 8080
self.volumio_registration_enabled = True
self.volumio_base_url = "http://127.0.0.1"
self.volumio_notification_callback_url = "http://127.0.0.1:8080/ingress/volumio/notifications"
```

Start in shadow mode first. After you confirm the mapped events look correct in the service logs, set:

```python
self.http_ingress_shadow_mode = False
```

**Legacy MQTT/librespot Mode**

If you still want the old librespot `onevent` path:

1. Set `mqtt_ingress_enabled = True`.
2. Configure librespot with:

```bash
LIBRESPOT_ONEVENT="/opt/nad/venv/bin/python /opt/nad/sender.py"
```

3. Keep a broker available at `broker_ip:broker_port`.

**Verification**

Useful commands after installation:

```bash
sudo systemctl status nad-receive.service
journalctl -u nad-receive.service -f
curl http://127.0.0.1:8080/ingress/status
python3 -m unittest discover -s tests -v
```
