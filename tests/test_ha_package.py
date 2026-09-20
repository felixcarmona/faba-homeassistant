import re
from pathlib import Path

import yaml

from faba_bridge.client import normalize

PACKAGE = Path(__file__).resolve().parent.parent / "homeassistant" / "packages" / "faba.yaml"
FIELD = re.compile(r"value_json\.(\w+)")
SENSOR = re.compile(r"states\('(sensor\.\w+)'\)")


def guard(field):
    # Covers null (box off), a missing field (bridge answers 502 {"error": ...}) and a non-JSON body.
    # A plain "value_json.x is not none" is true for a missing field.
    return f"value_json is mapping and value_json.get('{field}') is not none"


def load_package():
    return yaml.safe_load(PACKAGE.read_text(encoding="utf-8"))


def rest_sensors():
    return [sensor for block in load_package()["rest"] for sensor in block.get("sensor", [])]


def template_entities():
    return [
        entity
        for block in load_package()["template"]
        for domain in ("number", "select")
        for entity in block.get(domain, [])
    ]


def test_rest_sensors_go_unavailable_instead_of_reporting_none_while_the_box_is_off():
    # A powered-off box makes the bridge return null for these fields. A sensor with a unit that
    # renders 'None' raises a ValueError in Home Assistant on every single poll.
    null_while_off = {key for key, value in normalize({"device": {"online": False}}).items() if value is None}
    assert {"battery_pct", "volume", "led_brightness", "led_preset"} <= null_while_off

    for sensor in rest_sensors():
        template = sensor["value_template"]
        if " or " in template:  # "{{ value_json.x or 'fallback' }}" never renders None
            continue
        for field in set(FIELD.findall(template)) & null_while_off:
            assert guard(field) in sensor.get("availability", ""), sensor["name"]


def test_online_binary_sensor_is_guarded_against_an_error_payload():
    (online,) = [entity for block in load_package()["rest"] for entity in block.get("binary_sensor", [])]
    assert guard("online") in online["availability"]


def test_every_rest_entity_survives_an_error_payload_or_a_non_json_body():
    # Without a guard the value template itself fails ("'value_json' is undefined") on every poll.
    entities = [
        entity
        for block in load_package()["rest"]
        for kind in ("sensor", "binary_sensor")
        for entity in block.get(kind, [])
    ]
    assert len(entities) >= 6
    for entity in entities:
        assert entity.get("availability", "").startswith("{{ value_json is mapping and "), entity["name"]


def test_template_controls_follow_the_availability_of_the_sensor_they_mirror():
    entities = template_entities()
    assert entities
    for entity in entities:
        (source,) = SENSOR.findall(entity["state"])
        assert f"has_value('{source}')" in entity.get("availability", ""), entity["name"]
