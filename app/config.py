from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ha_base_url: str = Field(default="http://127.0.0.1:8123", alias="HA_BASE_URL")
    ha_token: str = Field(default="", alias="HA_TOKEN")
    iot_api_key: str = Field(default="", alias="IOT_API_KEY")
    ac_power_threshold_w: float = Field(default=50.0, alias="AC_POWER_THRESHOLD_W")
    pc_power_threshold_w: float = Field(default=50.0, alias="PC_POWER_THRESHOLD_W")
    cors_origins: str = Field(
        default="https://iot.iwhya.kr",
        alias="CORS_ORIGINS",
    )
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8002, alias="PORT")
    ha_timeout_seconds: float = Field(default=10.0, alias="HA_TIMEOUT_SECONDS")

    database_url: str = Field(default="", alias="DATABASE_URL")
    hejhome_base_url: str = Field(default="https://square.hej.so", alias="HEJHOME_BASE_URL")
    hejhome_email: str = Field(default="", alias="HEJHOME_EMAIL")
    hejhome_password: str = Field(default="", alias="HEJHOME_PASSWORD")
    hejhome_strip_id: str = Field(default="", alias="HEJHOME_STRIP_ID")
    hejhome_family_id: int = Field(default=0, alias="HEJHOME_FAMILY_ID")
    hejhome_timeout_seconds: float = Field(default=15.0, alias="HEJHOME_TIMEOUT_SECONDS")
    strip_channel_count: int = Field(default=4, alias="STRIP_CHANNEL_COUNT")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def strip_configured(self) -> bool:
        return bool(
            self.database_url
            and self.hejhome_email
            and self.hejhome_password
            and self.hejhome_strip_id
            and self.hejhome_family_id
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
