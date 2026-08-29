"""Client for the MyFaba cloud (FABA+ storytelling box).

The client authenticates against the app's Cognito user pool with the owner's
MyFaba credentials and talks to the IoT backend exactly like the official app
does. Only endpoints and commands that the app itself uses are implemented.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import requests

from . import const

log = logging.getLogger("faba_bridge")


def battery_percent(millivolts: int | None) -> int | None:
    """Rough state of charge from the reported battery voltage (Li-ion, 3.30-4.20 V)."""
    if millivolts is None:
        return None
    span = const.BATTERY_MV_FULL - const.BATTERY_MV_EMPTY
    return max(0, min(100, round((millivolts - const.BATTERY_MV_EMPTY) / span * 100)))


def battery_level(millivolts: int | None) -> str | None:
    """Coarse level using the thresholds the cloud publishes in /db-config."""
    if millivolts is None:
        return None
    if millivolts >= const.BATTERY_MV_HIGH:
        return "high"
    if millivolts >= const.BATTERY_MV_MEDIUM:
        return "medium"
    return "low"


def led_preset_name(preset_id: Any) -> str | None:
    try:
        return const.LED_PRESETS[int(preset_id)][0]
    except (KeyError, TypeError, ValueError):
        return None


def normalize(raw: dict, live_params: dict | None = None) -> dict:
    """Turn the raw ``GET /status/{moduleId}`` payload into a flat, HA-friendly dict.

    ``live_params`` (from ``FABA_STATUS``) override the cloud-cached parameters.
    """
    dev = raw.get("device") or {}
    params = dict(dev.get("paramsSettings") or {})
    live = False
    if live_params:
        params.update(live_params)
        live = True
    show = raw.get("boxShow") or {}
    last_msg = show.get("lastMessageData") or {}
    mv = params.get("status_battery")
    return {
        "online": bool(dev.get("online")),
        "live": live,
        "last_connection": dev.get("lastConnection"),
        "fw": dev.get("fwVersion"),
        "ip": dev.get("ipAddress"),
        "module_id": dev.get("id"),
        "mac": dev.get("mac"),
        "battery_mv": mv,
        "battery_pct": battery_percent(mv),
        "battery_level": battery_level(mv),
        "volume": params.get("volume"),
        "volume_limit": params.get("volume_limit"),
        "led_brightness": params.get("led_brightness"),
        "led_preset_id": params.get("led_preset_id"),
        "led_preset": led_preset_name(params.get("led_preset_id")),
        "led_brightness_status": params.get("led_brightness_status"),
        "led_status_off": params.get("led_status_off"),
        "power_on_mode": params.get("power_on_mode"),
        "play_character_lock": params.get("play_character_lock"),
        "playlist_end_mode": params.get("playlist_end_mode"),
        "auto_off_timer": params.get("auto_off_timer"),
        "now_title": show.get("currentContentTitle"),
        "now_tracks": show.get("currentTotalTracks"),
        "now_status": last_msg.get("status"),
        "now_track_idx": last_msg.get("trackIdx"),
        "now_progress": last_msg.get("progress"),
        "now_image": show.get("currentCharacterImage"),
        "sync_status": show.get("status"),
        "last_message": show.get("lastMessageDt"),
        "ts": time.time(),
    }


class CognitoAuth:
    """Small wrapper around pycognito that keeps a valid id token."""

    def __init__(self, username: str, password: str):
        from pycognito import Cognito  # imported lazily so tests do not need it

        self._password = password
        self._user = Cognito(
            const.COGNITO_POOL_ID,
            const.COGNITO_CLIENT_ID,
            user_pool_region=const.COGNITO_REGION,
            username=username,
        )

    def id_token(self) -> str:
        if not self._user.id_token:
            self._user.authenticate(password=self._password)
            log.info("Cognito login OK")
        else:
            try:
                self._user.check_token(renew=True)
            except Exception as err:  # noqa: BLE001 - any auth failure -> full login
                log.warning("token renewal failed (%s), logging in again", err)
                self._user.authenticate(password=self._password)
        return self._user.id_token


class FabaClient:
    """Talks to the IoT backend for one box (the first box of the account by default)."""

    def __init__(
        self,
        token_provider: Callable[[], str],
        module_id: str | None = None,
        session: requests.Session | None = None,
        api_url: str = const.IOT_API_URL,
        timeout: int = 30,
    ):
        self._token = token_provider
        self.module_id = module_id
        self._session = session or requests.Session()
        self._api = api_url.rstrip("/")
        self._timeout = timeout
        self._lock = threading.Lock()

    def _headers(self) -> dict:
        return {
            "authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, **kw) -> dict:
        r = self._session.get(f"{self._api}{path}", headers=self._headers(), timeout=self._timeout, **kw)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict, timeout: int | None = None) -> dict:
        r = self._session.post(
            f"{self._api}{path}", headers=self._headers(), json=body, timeout=timeout or self._timeout
        )
        r.raise_for_status()
        return r.json()

    # -- API -------------------------------------------------------------
    def devices(self) -> list[dict]:
        return self._get("/status")["data"]["devices"]

    def resolve_module_id(self) -> str:
        with self._lock:
            if not self.module_id:
                devs = self.devices()
                if not devs:
                    raise RuntimeError("the MyFaba account has no boxes")
                self.module_id = devs[0]["id"]
                log.info("using box %s (%s)", self.module_id, devs[0].get("mac"))
            return self.module_id

    def raw_status(self, skip_box_show: bool = False) -> dict:
        mid = self.resolve_module_id()
        return self._get(f"/status/{mid}", params={"skipBoxShow": "true" if skip_box_show else "false"})["data"]

    def send_cmd(self, code: int, data: dict | None = None, sync: bool = True) -> dict:
        if code == const.CMD_WS_DEL_CONFIG:
            raise ValueError("refusing to send WS_DEL_CONFIG (it unbinds the box)")
        mid = self.resolve_module_id()
        body = {"cmd": int(code), "moduleId": mid, "dataToSend": data or {}, "sync": sync}
        return self._post("/send-cmd", body, timeout=60)

    def live_params(self) -> dict | None:
        res = self.send_cmd(const.CMD_FABA_STATUS, {})
        if res.get("result") and isinstance(res.get("data"), dict):
            return res["data"]
        return None

    def write_params(self, params: dict) -> dict:
        bad = set(params) - const.WRITABLE_PARAMS
        if bad or not params:
            raise ValueError(f"unsupported parameter(s): {sorted(bad) or 'empty'}")
        return self.send_cmd(const.CMD_FABA_STATUS_WRITE, params)

    def power_off(self) -> dict:
        return self.send_cmd(const.CMD_WS_RESTART, {})

    def status(self) -> dict:
        raw = self.raw_status()
        live = None
        if (raw.get("device") or {}).get("online"):
            try:
                live = self.live_params()
            except Exception as err:  # noqa: BLE001 - fall back to cached values
                log.warning("live FABA_STATUS failed: %s", err)
        return normalize(raw, live)
