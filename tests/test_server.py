import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from faba_bridge.client import FabaClient
from faba_bridge.server import make_handler

from .conftest import FakeSession


@pytest.fixture
def bridge():
    session = FakeSession()
    client = FabaClient(lambda: "tok", session=session)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(client))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, session
    httpd.shutdown()


def call(base, path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data is not None else "GET"))
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def test_health(bridge):
    base, _ = bridge
    status, body = call(base, "/health")
    assert status == 200 and body["ok"] is True


def test_status_is_normalized(bridge):
    base, _ = bridge
    status, body = call(base, "/status")
    assert status == 200
    assert body["online"] is True and body["live"] is True
    assert body["battery_pct"] == 63  # 3870 mV from the live read


def test_raw_passthrough(bridge):
    base, _ = bridge
    status, body = call(base, "/raw")
    assert status == 200 and "device" in body and "boxShow" in body


def test_set_rejects_unknown_keys(bridge):
    base, session = bridge
    status, body = call(base, "/set", {"foo": 1})
    assert status == 400 and "allowed" in body
    assert not [c for c in session.calls if c[0] == "POST"]


def test_set_writes_known_keys(bridge):
    base, session = bridge
    status, body = call(base, "/set", {"led_brightness": 55, "led_preset_id": 5})
    assert status == 200 and body == {"result": True}
    assert session.calls[-1][4]["dataToSend"] == {"led_brightness": 55, "led_preset_id": 5}


def test_off_sends_restart(bridge):
    base, session = bridge
    status, _ = call(base, "/off", {})
    assert status == 200
    assert session.calls[-1][4]["cmd"] == 124


def test_cmd_endpoint_and_bad_json(bridge):
    base, session = bridge
    status, _ = call(base, "/cmd", {"code": 13006, "data": {}})
    assert status == 200
    req = urllib.request.Request(base + "/cmd", data=b"[1,2]", method="POST")
    req.add_header("Content-Type", "application/json")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req, timeout=5)
    assert err.value.code == 400


def test_unknown_paths(bridge):
    base, _ = bridge
    assert call(base, "/nope")[0] == 404
    assert call(base, "/nope", {})[0] == 404
