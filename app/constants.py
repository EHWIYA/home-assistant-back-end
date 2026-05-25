"""Home Assistant entity IDs — rename here only."""

ENTITY_PLUG_SWITCH = "switch.hwiya_home"
ENTITY_PLUG_POWER = "sensor.hwiya_home_power"
ENTITY_PLUG_ENERGY = "sensor.hwiya_home_energy"
ENTITY_INDOOR_TEMP = "sensor.hwiya_sensor_temperature"
ENTITY_INDOOR_HUMIDITY = "sensor.hwiya_sensor_humidity"
ENTITY_PERSON = "person.hwiya_ha"
ENTITY_WEATHER = "weather.forecast_jib"
ENTITY_AC_REMOTE = "remote.hwiya_sensor"
AC_REMOTE_DEVICE = "ac"
AC_COMMAND_ON = "ac_on"
AC_COMMAND_OFF = "ac_off"

STATUS_ENTITY_IDS = (
    ENTITY_PLUG_SWITCH,
    ENTITY_PLUG_POWER,
    ENTITY_PLUG_ENERGY,
    ENTITY_INDOOR_TEMP,
    ENTITY_INDOOR_HUMIDITY,
    ENTITY_PERSON,
    ENTITY_WEATHER,
)

# Hejhome OAuth (square.hej.so shop client — same as official app / homebridge-hejhome)
HEJHOME_CLIENT_ID = "62f4020744ca4510827d3b4a4d2c7e7f"
HEJHOME_CLIENT_SECRET = "fcd4302cece447a9ab009296f649d2c0"
HEJHOME_OAUTH_REDIRECT_URI = "https://square.hej.so/list"
HEJHOME_DEVICE_TYPE_STRIP = "PowerStrip2"
STRIP_CHANNEL_POWER_KEYS = ("power1", "power2", "power3", "power4")
