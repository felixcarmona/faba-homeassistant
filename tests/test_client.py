import pytest

from faba_bridge import const
from faba_bridge.client import battery_level, battery_percent, led_preset_name, normalize


def test_battery_percent_is_clamped_and_linear():
    assert battery_percent(None) is None
    assert battery_percent(3300) == 0
    assert battery_percent(4200) == 100
    assert battery_percent(3750) == 50
    assert battery_percent(5000) == 100
    assert battery_percent(1000) == 0


def test_battery_level_uses_cloud_thresholds():
    assert battery_level(None) is None
    assert battery_level(3700) == "high"
    assert battery_level(3500) == "medium"
    assert battery_level(3400) == "low"


def test_led_preset_name():
    assert led_preset_name(1) == "red"
    assert led_preset_name("5") == "blue"
    assert led_preset_name(42) is None
    assert led_preset_name(None) is None


def test_normalize_uses_cached_params_when_no_live_data(raw_status):
    out = normalize(raw_status)
    assert out["online"] is True
    assert out["live"] is False
    assert out["module_id"] == "583ab329005542029e7b76abdcf844a8"
    assert out["battery_mv"] == 3865
    assert out["battery_pct"] == 63
    assert out["volume"] == 19
    assert out["led_preset"] == "red"
    assert out["now_title"] == "FABA•ME White"
    assert out["now_tracks"] == 5
    assert out["now_status"] == 4


def test_normalize_prefers_live_params(raw_status):
    out = normalize(raw_status, {"volume": 8, "led_brightness": 40})
    assert out["live"] is True
    assert out["volume"] == 8
    assert out["led_brightness"] == 40
    assert out["volume_limit"] == 19  # untouched cached value


def test_normalize_tolerates_missing_sections():
    out = normalize({"device": {"online": False}})
    assert out["online"] is False
    assert out["battery_pct"] is None
    assert out["now_title"] is None


def test_module_id_is_discovered_once(client, session):
    assert client.resolve_module_id() == "583ab329005542029e7b76abdcf844a8"
    assert client.resolve_module_id() == "583ab329005542029e7b76abdcf844a8"
    assert len([c for c in session.calls if c[1].endswith("/status")]) == 1


def test_requests_carry_bearer_token(client, session):
    client.raw_status()
    method, url, headers, params, _ = session.calls[-1]
    assert headers["authorization"] == "Bearer id-token-123"
    assert url.endswith("/status/583ab329005542029e7b76abdcf844a8")
    assert params == {"skipBoxShow": "false"}


def test_send_cmd_payload_shape(client, session):
    client.send_cmd(const.CMD_FABA_STATUS_WRITE, {"led_brightness": 60})
    _, url, _, _, body = session.calls[-1]
    assert url.endswith("/send-cmd")
    assert body == {
        "cmd": 13003,
        "moduleId": "583ab329005542029e7b76abdcf844a8",
        "dataToSend": {"led_brightness": 60},
        "sync": True,
    }


def test_write_params_enforces_whitelist(client):
    with pytest.raises(ValueError):
        client.write_params({"foo_bar": 1})
    with pytest.raises(ValueError):
        client.write_params({})
    assert client.write_params({"volume": 10}) == {"result": True}


def test_del_config_is_refused(client):
    with pytest.raises(ValueError):
        client.send_cmd(const.CMD_WS_DEL_CONFIG)


def test_power_off_sends_ws_restart(client, session):
    client.power_off()
    assert session.calls[-1][4]["cmd"] == const.CMD_WS_RESTART


def test_status_merges_live_values_when_online(client):
    out = client.status()
    assert out["live"] is True
    assert out["volume"] == 8
    assert out["battery_mv"] == 3870


def test_status_falls_back_when_live_read_fails(client, session):
    session.live_params = "not a dict"
    out = client.status()
    assert out["live"] is False
    assert out["volume"] == 19
