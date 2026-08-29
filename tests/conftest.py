import copy

import pytest

RAW_STATUS = {
    "device": {
        "id": "583ab329005542029e7b76abdcf844a8",
        "mac": "8c:4f:00:a3:68:08",
        "fwVersion": "v2.0-3-gd59967c",
        "ipAddress": "203.0.113.10",
        "online": True,
        "lastConnection": "2026-08-29T08:38:08.000Z",
        "paramsSettings": {
            "led_preset_id": 1,
            "led_brightness": 70,
            "led_brightness_status": 70,
            "led_status_off": 0,
            "volume": 19,
            "volume_limit": 19,
            "auto_off_timer": 10,
            "status_battery": 3865,
            "power_on_mode": 0,
            "play_character_lock": 0,
            "playlist_end_mode": 0,
        },
    },
    "boxShow": {
        "status": "completed",
        "lastMessageData": {"syncId": 1, "status": 4, "trackIdx": 0, "progress": 0},
        "lastMessageDt": "2026-08-21T16:49:14.000Z",
        "currentTotalTracks": 5,
        "currentCharacterImage": "https://example.invalid/main-image.png",
        "currentContentTitle": "FABA•ME White",
    },
}

DEVICES = [{"id": RAW_STATUS["device"]["id"], "mac": RAW_STATUS["device"]["mac"], "online": True}]


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return copy.deepcopy(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Records requests and answers like the real IoT backend."""

    def __init__(self, live_params=None, cmd_result=None):
        self.calls = []
        self.live_params = live_params if live_params is not None else {"volume": 8, "status_battery": 3870}
        self.cmd_result = cmd_result or {"result": True}

    def get(self, url, headers=None, timeout=None, params=None):
        self.calls.append(("GET", url, headers, params, None))
        if url.endswith("/status"):
            return FakeResponse({"result": True, "data": {"devices": DEVICES}})
        if "/status/" in url:
            return FakeResponse({"result": True, "data": copy.deepcopy(RAW_STATUS)})
        return FakeResponse({"error": "not found"}, 404)

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", url, headers, None, json))
        if url.endswith("/send-cmd"):
            if json["cmd"] == 13006:
                return FakeResponse({"result": True, "data": self.live_params})
            return FakeResponse(self.cmd_result)
        return FakeResponse({"error": "not found"}, 404)


@pytest.fixture
def raw_status():
    return copy.deepcopy(RAW_STATUS)


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    from faba_bridge.client import FabaClient

    return FabaClient(lambda: "id-token-123", session=session)
