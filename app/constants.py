"""Home Assistant entity IDs — rename here only."""

ENTITY_PLUG_SWITCH = "switch.hwiya_home"
ENTITY_PLUG_POWER = "sensor.hwiya_home_power"
ENTITY_PLUG_ENERGY = "sensor.hwiya_home_energy"

ENTITY_PC_SWITCH = "switch.hwiya_pc"
ENTITY_PC_POWER = "sensor.hwiya_pc_current_consumption"
ENTITY_PC_ENERGY_TODAY = "sensor.hwiya_pc_today_s_consumption"
ENTITY_PC_ENERGY_MONTH = "sensor.hwiya_pc_this_month_s_consumption"
ENTITY_PC_CLOUD = "binary_sensor.hwiya_pc_cloud_connection"
ENTITY_PC_SIGNAL = "sensor.hwiya_pc_signal_level"
ENTITY_PC_OVERLOAD = "binary_sensor.hwiya_pc_overloaded"
ENTITY_INDOOR_TEMP = "sensor.hwiya_sensor_temperature"
ENTITY_INDOOR_HUMIDITY = "sensor.hwiya_sensor_humidity"
ENTITY_WEATHER = "weather.forecast_jib"

# 실외 날씨 (공공데이터·기상청) — 서울 금천구 가산동
WEATHER_LOCAL_LAT = 37.4780
WEATHER_LOCAL_LON = 126.8875
WEATHER_LOCAL_NX = 58
WEATHER_LOCAL_NY = 125
WEATHER_LOCAL_LABEL = "서울 금천구 가산동"
WEATHER_LOCAL_SHORT_LABEL = "가산동"
ENTITY_AC_REMOTE = "remote.hwiya_sensor"
ENTITY_AC_AUTO_ENABLED = "input_boolean.hwiya_ac_auto_enabled"
ENTITY_AC_AUTO_STATE = "sensor.hwiya_ac_auto_state"
ENTITY_AC_LAST_ON = "input_datetime.hwiya_ac_last_on"
ENTITY_AC_LAST_OFF = "input_datetime.hwiya_ac_last_off"
ENTITY_AC_PLUG_ACTIVE = "binary_sensor.hwiya_ac_plug_active"
ENTITY_AC_MODE = "input_select.hwiya_ac_mode"
ENTITY_AC_AWAY_ENABLED = "input_boolean.hwiya_ac_away_enabled"
ENTITY_AC_LAST_RUN_MODE = "input_text.hwiya_ac_last_run_mode"
AC_REMOTE_DEVICE = "ac"
AC_COMMAND_COOL_PRESET_17 = "ac_preset_cool_17"
AC_COMMAND_DRY_PRESET_17 = "ac_preset_dry_17"
AC_COMMAND_OFF = "ac_off"

STATUS_ENTITY_IDS = (
    ENTITY_PLUG_SWITCH,
    ENTITY_PLUG_POWER,
    ENTITY_PLUG_ENERGY,
    ENTITY_PC_SWITCH,
    ENTITY_PC_POWER,
    ENTITY_PC_ENERGY_TODAY,
    ENTITY_PC_ENERGY_MONTH,
    ENTITY_PC_CLOUD,
    ENTITY_PC_SIGNAL,
    ENTITY_PC_OVERLOAD,
    ENTITY_INDOOR_TEMP,
    ENTITY_INDOOR_HUMIDITY,
    ENTITY_WEATHER,
    ENTITY_AC_AUTO_ENABLED,
    ENTITY_AC_AUTO_STATE,
    ENTITY_AC_LAST_ON,
    ENTITY_AC_LAST_OFF,
    ENTITY_AC_PLUG_ACTIVE,
    ENTITY_AC_MODE,
    ENTITY_AC_AWAY_ENABLED,
    ENTITY_AC_LAST_RUN_MODE,
)

# Hejhome OAuth (square.hej.so shop client — same as official app / homebridge-hejhome)
HEJHOME_CLIENT_ID = "62f4020744ca4510827d3b4a4d2c7e7f"
HEJHOME_CLIENT_SECRET = "fcd4302cece447a9ab009296f649d2c0"
HEJHOME_OAUTH_REDIRECT_URI = "https://square.hej.so/list"
HEJHOME_DEVICE_TYPE_STRIP = "PowerStrip2"
STRIP_CHANNEL_POWER_KEYS = ("power1", "power2", "power3", "power4")
