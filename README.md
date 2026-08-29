# faba-homeassistant

Home Assistant integration for the **FABA+** storytelling box (MyFaba, by Maikii),
built on a small local bridge that talks to the MyFaba cloud the same way the
official app does.

> **Unofficial project.** Not affiliated with Maikii/MyFaba. The box has no
> local API, so everything goes through the MyFaba cloud with *your own*
> account. Only the commands the official app itself sends are used, but use
> it at your own risk.

## What you get

| Entity | What it is |
|---|---|
| `binary_sensor.faba_online` | box is on and connected to the cloud |
| `sensor.faba_battery` | approximate state of charge (mV in attributes) |
| `sensor.faba_volume` / `number.faba_volume` | the yellow volume knob, 0-100 |
| `sensor.faba_brightness` / `number.faba_night_light_brightness` | night light brightness, 10-100 |
| `sensor.faba_night_light_color` / `select.faba_night_light_color` | night light colour (8 presets) |
| `sensor.faba_now_playing` | last content played (title, tracks, progress in attributes) |
| `switch.faba` | reflects *online*; turning it **off** sends the app's "forced shutdown" |
| `button.faba_power_off` | forced shutdown |

Things that are **not** possible (verified against a real box, firmware
`v2.0-3`):

- **Powering the box on remotely.** When it is off it is not on Wi-Fi at all.
- **Switching the night light on/off.** The oval button is purely local: the
  cloud neither reports nor controls that state. Brightness and colour are
  applied live *while the light is on*.
- **Starting playback.** Playback is triggered by the NFC figure.

## How it works

```
Home Assistant  --rest / rest_command-->  faba-bridge (127.0.0.1:8090)  --HTTPS-->  MyFaba cloud  --MQTT-->  FABA+
```

`faba_bridge` logs in to the app's Cognito user pool with your MyFaba
credentials, discovers your box and exposes a tiny JSON API:

| Method | Path | Description |
|---|---|---|
| GET | `/status` | normalized status (live values when the box is online) |
| GET | `/raw` | raw cloud payload |
| POST | `/set` | write parameters, e.g. `{"led_brightness": 60}` (whitelisted keys only) |
| POST | `/off` | forced shutdown |
| POST | `/cmd` | `{"code": 13006, "data": {}}` for experiments |

The protocol (endpoints, command codes, parameters, colour table) is
documented in [PROTOCOL.md](PROTOCOL.md).

## Setup

### 1. Run the bridge

```sh
cp .env.example .env        # fill in MYFABA_USER / MYFABA_PASS
docker compose up -d --build
curl http://127.0.0.1:8090/status
```

The container uses `network_mode: host` and only listens on `127.0.0.1`. Run it
on the same machine as Home Assistant (or change `FABA_BRIDGE_HOST` and point
the package at it). A dedicated MyFaba account is a good idea: create one in
the app and share the box with it, so a lockout never affects your phone.

Without Docker: `pip install .` then `MYFABA_USER=... MYFABA_PASS=... faba-bridge`.

### 2. Add the Home Assistant package

Copy `homeassistant/packages/faba.yaml` to `<config>/packages/faba.yaml` and
make sure packages are enabled in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant. The package polls the bridge every 30 s (`rest`) and
uses `rest_command` + template entities for the controls. To expose something to
HomeKit/Siri, add e.g. `switch.faba` to your HomeKit Bridge filter ("Hey Siri,
turn off FABA").

## Development

```sh
pip install -e ".[dev]"
ruff check .
pytest -q
```

Tests use a fake HTTP session; nothing talks to the cloud.

## Reverse engineering notes

The MyFaba Android app is React Native with a Hermes bundle. Decompiling it with
`hermes-dec` yields the Cognito pool, the IoT endpoint, the `TC_COMMAND` enum
(`FABA_STATUS = 13006`, `FABA_STATUS_WRITE = 13003`, `WS_RESTART = 124`, ...)
and the parameter names. See [PROTOCOL.md](PROTOCOL.md).

## License

MIT
