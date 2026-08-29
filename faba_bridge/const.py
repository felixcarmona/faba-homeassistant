"""Constants for the FABA+ (MyFaba) cloud API.

Everything here was obtained by reverse engineering the MyFaba Android app
(``com.maikii.myfaba`` 2.14). See PROTOCOL.md for details.
"""

# AWS Cognito user pool used by the production app (no client secret).
COGNITO_POOL_ID = "eu-west-3_55n00IVB6"
COGNITO_CLIENT_ID = "578g34gv9hski7agkj66ecrcup"
COGNITO_REGION = "eu-west-3"

# IoT backend that manages the Wi-Fi module of the box.
IOT_API_URL = "https://faba-api-production.thingscloud.it/api/faba"

# ``cmd`` codes accepted by POST /send-cmd (the app's ``TC_COMMAND`` enum).
CMD_FABA_STATUS = 13006  # live read of the box parameters
CMD_FABA_STATUS_WRITE = 13003  # write one or more parameters
CMD_FABA_TRACK_LIST = 13002  # needs a character on the box
CMD_FABA_GAME_LIST = 13004
CMD_FABA_PLAYLIST_UPDATE = 13005
CMD_WS_RESTART = 124  # what the app calls "forced shutdown"
CMD_WS_DEL_CONFIG = 125  # wipes the Wi-Fi config / unbinds the box - never send this

# Parameters that may be written with CMD_FABA_STATUS_WRITE. The cloud does not
# validate keys (it happily accepts anything), so the bridge enforces this list.
WRITABLE_PARAMS = frozenset(
    {
        "led_brightness",  # night light brightness 10-100 (only while the light is on)
        "led_preset_id",  # night light colour, see LED_PRESETS
        "led_brightness_status",  # status LED brightness
        "led_status_off",  # status LED off flag (0/1)
        "led_brightness_limit",
        "volume",  # the yellow knob, 0-100
        "volume_limit",
        "power_on_mode",  # 0 classic (side button) / 1 any front button
        "play_character_lock",
        "playlist_end_mode",
        "auto_off_timer",  # minutes
    }
)

# Night light colour presets (``paramLedPresetColorsData`` in the app).
LED_PRESETS = {
    0: ("white", "#FFFFFF"),
    1: ("red", "#ED1C24"),
    2: ("orange", "#EB683B"),
    3: ("yellow", "#FBD63D"),
    4: ("green", "#35B14C"),
    5: ("blue", "#3188E8"),
    6: ("lavender", "#C8BFE8"),
    7: ("purple", "#A349A4"),
}

# Battery thresholds reported by GET /db-config (millivolts).
BATTERY_MV_EMPTY = 3300
BATTERY_MV_FULL = 4200
BATTERY_MV_MEDIUM = 3440
BATTERY_MV_HIGH = 3650

DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 8090
