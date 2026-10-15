"""Motion/object-triggered Reolink floodlight automation, driven by Frigate's
MQTT events.

For each camera in config.yaml: when Frigate reports a tracked object whose
label is in that camera's trigger_labels, and (if night_only) it's currently
between sunset and sunrise at the configured location, turn the camera's
white LED on. Turn it back off after off_delay_seconds with no further
matching detections (the timer resets on each new matching detection, so
continuous motion keeps the light on).

Night gating is clock/sun-based (via astral), not the camera's own ambient
day/night sensor — that sensor answers "is it dark enough for IR mode",
which can stay "Color" well into the night if there's any ambient light
(a streetlight, etc.), silently defeating a motion-light automation.

Reolink's own SetWhiteLed `mode` is left at 0 (manual) so this script has
exclusive control over `state` — see the accompanying README for why.
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
import requests
import urllib3
import yaml
from astral import LocationInfo
from astral.sun import sun

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("light-automation")

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")


def resolve_env_placeholders(value):
    """Replace {ENV_VAR} placeholders in strings, recursively through dicts/lists."""
    if isinstance(value, str):
        def sub(m):
            name = m.group(1)
            if name not in os.environ:
                raise ValueError(f"Missing required env var: {name}")
            return os.environ[name]

        return re.sub(r"\{([A-Z0-9_]+)\}", sub, value)
    if isinstance(value, dict):
        return {k: resolve_env_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env_placeholders(v) for v in value]
    return value


class ReolinkLight:
    """Minimal Reolink API client for a single camera's white LED control."""

    def __init__(self, host, user, password):
        self.host = host
        self.user = user
        self.password = password
        self._token = None
        self._token_expiry = 0

    def _login(self):
        if self._token and time.time() < self._token_expiry:
            return self._token
        resp = requests.post(
            f"https://{self.host}/cgi-bin/api.cgi?cmd=Login",
            json=[
                {
                    "cmd": "Login",
                    "action": 0,
                    "param": {
                        "User": {"userName": self.user, "password": self.password}
                    },
                }
            ],
            verify=False,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()[0]
        if data.get("code") != 0:
            raise RuntimeError(f"Reolink login failed for {self.host}: {data}")
        self._token = data["value"]["Token"]["name"]
        # Refresh a bit before the token's own lease time to be safe.
        self._token_expiry = time.time() + data["value"]["Token"].get(
            "leaseTime", 3600
        ) - 60
        return self._token

    def set_light(self, on: bool):
        token = self._login()
        resp = requests.post(
            f"https://{self.host}/cgi-bin/api.cgi?cmd=SetWhiteLed&token={token}",
            json=[
                {
                    "cmd": "SetWhiteLed",
                    "action": 0,
                    "param": {
                        "WhiteLed": {
                            "channel": 0,
                            "mode": 0,
                            "bright": 100,
                            "state": 1 if on else 0,
                        }
                    },
                }
            ],
            verify=False,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()[0]
        if data.get("code") != 0:
            raise RuntimeError(f"Reolink SetWhiteLed failed for {self.host}: {data}")
        log.info("%s: light -> %s", self.host, "ON" if on else "OFF")


def is_night(location_cfg) -> bool:
    """True if it's currently between sunset and sunrise at the configured
    location. Pure local computation, no network call — safe to call as
    often as needed."""
    tz = ZoneInfo(location_cfg["timezone"])
    now = datetime.now(tz)
    city = LocationInfo(
        latitude=location_cfg["latitude"],
        longitude=location_cfg["longitude"],
        timezone=location_cfg["timezone"],
    )
    s = sun(city.observer, date=now.date(), tzinfo=tz)
    return now < s["sunrise"] or now > s["sunset"]


class CameraAutomation:
    def __init__(self, name, cfg, location_cfg):
        self.name = name
        self.trigger_labels = set(cfg["trigger_labels"])
        self.night_only = cfg.get("night_only", True)
        self.off_delay = cfg.get("off_delay_seconds", 120)
        self.location_cfg = location_cfg
        self.light = ReolinkLight(
            cfg["reolink_host"], cfg["reolink_user"], cfg["reolink_password"]
        )

        # Reolink cameras apply their own ~1 minute auto-off to a manually
        # (API) triggered light, independent of our own off_delay logic. So
        # rather than sending the ON command once and trusting it stays on,
        # we re-assert it periodically during continued matching activity —
        # cheap, idempotent, and defeats whatever auto-off timer the camera
        # applies on its end.
        REASSERT_INTERVAL = 30

        self._lock = threading.Lock()
        self._light_on = False
        self._last_match_time = 0.0
        self._last_on_call_time = 0.0
        self._reassert_interval = REASSERT_INTERVAL

    def handle_event(self, label: str):
        if label not in self.trigger_labels:
            return

        if self.night_only and not is_night(self.location_cfg):
            log.debug(
                "%s: %s detected but it's daytime, ignoring", self.name, label
            )
            return

        with self._lock:
            now = time.time()
            self._last_match_time = now
            needs_call = (
                not self._light_on
                or now - self._last_on_call_time >= self._reassert_interval
            )
            if needs_call:
                try:
                    self.light.set_light(True)
                    self._light_on = True
                    self._last_on_call_time = now
                except Exception:
                    log.exception("%s: failed to turn light on", self.name)

    def check_off(self):
        with self._lock:
            if not self._light_on:
                return
            if time.time() - self._last_match_time < self.off_delay:
                return
            try:
                self.light.set_light(False)
                self._light_on = False
            except Exception:
                log.exception("%s: failed to turn light off", self.name)


def load_config():
    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    return resolve_env_placeholders(raw)


def main():
    config = load_config()
    location_cfg = config["location"]
    automations = {
        name: CameraAutomation(name, cfg, location_cfg)
        for name, cfg in config["cameras"].items()
    }
    log.info("Configured cameras: %s", list(automations.keys()))

    def off_checker_loop():
        while True:
            for automation in automations.values():
                automation.check_off()
            time.sleep(5)

    threading.Thread(target=off_checker_loop, daemon=True).start()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        log.info("Connected to MQTT broker (reason_code=%s)", reason_code)
        client.subscribe("frigate/events")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            return
        after = payload.get("after") or {}
        camera = after.get("camera")
        label = after.get("label")
        if camera in automations:
            automations[camera].handle_event(label)

    mqtt_cfg = config["mqtt"]
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(mqtt_cfg["user"], mqtt_cfg["password"])
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(mqtt_cfg["host"], mqtt_cfg["port"], keepalive=60)
            client.loop_forever()
        except Exception:
            log.exception("MQTT connection lost, retrying in 10s")
            time.sleep(10)


if __name__ == "__main__":
    main()
