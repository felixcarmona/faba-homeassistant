# MyFaba / FABA+ cloud protocol

Reverse engineered from the MyFaba Android app (`com.maikii.myfaba` 2.14,
React Native + Hermes bytecode, disassembled with `hermes-dec`) and verified
against a FABA+ running firmware `v2.0-3-gd59967c`.

## Authentication

- AWS Cognito user pool `eu-west-3_55n00IVB6`, app client
  `578g34gv9hski7agkj66ecrcup` (no client secret), SRP flow. Any Cognito SRP
  client works (`pycognito` here).
- The **id token** is sent as `Authorization: Bearer <idToken>` to the IoT API.
- The app also has a staging pool (`eu-west-3_0jIY1sAZ7`) and other backends
  (CMS `https://cms.myfaba.com/api/v2|v3/`, an API Gateway, OneSignal,
  Firebase Analytics, AWS Pinpoint) that are not needed for device control.

## IoT API

Base URL: `https://faba-api-production.thingscloud.it/api/faba/`

| Method | Path | Purpose |
|---|---|---|
| GET | `/status` | profile + `data.devices[]` (`id` = moduleId, `mac`, `fwVersion`, `online`, `lastConnection`, `ipAddress`) |
| GET | `/status/{moduleId}?skipBoxShow=true\|false` | `data.device.paramsSettings` (last values known by the cloud) + `data.boxShow` (last content, tracks, progress) |
| POST | `/send-cmd` | `{"cmd": <int>, "moduleId": "...", "dataToSend": {...}, "sync": true}` → `{"result": true}` or `{"result": false, "error": "..."}` |
| GET | `/db-config` | battery thresholds (`statusBatteryHigh` 3650 mV, `statusBatteryMedium` 3440 mV) |
| POST | `/check-fw-update/`, `/run-fw-update/`, `/ota-status/`, `/start-full-box-sync/`, `/factory-reset/`, `/unbind/`, `/check-bind`, `/get-new-bind`, `/update/` | used by the app for OTA, sync and pairing (not used here) |

`/send-cmd` answers in ~0.2 s when the box is on; commands that need a figure on
the box return `MODULE_ERROR`.

### Command codes (`TC_COMMAND` enum)

| Name | Code | Notes |
|---|---|---|
| `FABA_STATUS` | 13006 | live read of `paramsSettings` |
| `FABA_STATUS_WRITE` | 13003 | write one or more parameters (`dataToSend`) |
| `FABA_TRACK_LIST` | 13002 | needs a figure on the box |
| `FABA_GAME_LIST` | 13004 | needs a figure on the box |
| `FABA_PLAYLIST_UPDATE` | 13005 | |
| `WS_RESTART` | 124 | the app's **forced shutdown** |
| `WS_DEL_CONFIG` | 125 | wipes the Wi-Fi config / unbinds the box — **never send** |
| `WS_ACK` 100, `WS_OPEN` 108, `WS_CLOSE` 109, `WS_CONNECT` 110, `WS_INIT_DONE` 111, `WS_PINWRITE` 131, `WS_BIND_V2` 134, `WS_ECHO` 138, `WS_MQTT_IN` 200, `WS_MQTT_SEND` 201, `WS_SWITCH` 500, `EF315_RAW` 999, `WS_READ_REGISTERS` 2001, `WS_WRITE_REGISTERS` 2002, `WS_WRITE_REGISTER` 2009, `WS_JUMP_WRITE` 2012 | | module / BLE pairing internals |

### Parameters (`paramsSettings`)

Writable with `FABA_STATUS_WRITE` (the cloud does **not** validate keys — it
accepts anything with `result: true`, so keep to this list):

| Key | Meaning |
|---|---|
| `led_brightness` | night light brightness 10-100; applied live while the light is on (0 is clamped to 10) |
| `led_preset_id` | night light colour, see table below |
| `led_brightness_status`, `led_status_off` | status LED brightness / off flag |
| `led_brightness_limit` | "limited night light" cap (0 is rejected: the box resets it to 100 and brightness to 50) |
| `volume` | the yellow knob, 0-100 |
| `volume_limit` | "limited volume" setting |
| `power_on_mode` | 0 classic (side button) / 1 easy power-on (any front button) |
| `play_character_lock`, `playlist_end_mode`, `auto_off_timer` | app settings |

Read-only: `status_battery` (mV; `battery_low_th` 340 / `battery_min_th` 330 =
3.40 / 3.30 V), `status_fm`, `lang_id`, `tz`, `wake_cron`, `playlist_day_*`,
`playlist_night_*` (pink-button bedtime routine).

### Night light colour presets

| id | colour | hex |
|---|---|---|
| 0 | white | `#FFFFFF` |
| 1 | red | `#ED1C24` |
| 2 | orange | `#EB683B` |
| 3 | yellow | `#FBD63D` |
| 4 | green | `#35B14C` |
| 5 | blue | `#3188E8` |
| 6 | lavender | `#C8BFE8` |
| 7 | purple | `#A349A4` |

## Known limitations

- The night light on/off state (oval grey button) is neither reported nor
  controllable: pressing the button changes no parameter, and no write turns the
  light off (`led_preset_id: 0` is white, `led_brightness: 0` becomes 10).
- The box cannot be powered on remotely: when off it has no Wi-Fi.
- Playback is started by the NFC figure only.
- The Wi-Fi module talks MQTT with the cloud (`mqttClientId`, `mqttTc32` in the
  device record); the device-side channel is not needed for control.
- `GET /status/{moduleId}` occasionally answers `200` with no `data` section; the client retries once after a short pause (seen in production on 2026-08-30).
