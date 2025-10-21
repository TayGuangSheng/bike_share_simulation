from pathlib import Path

from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ELEN90061 Dockless Bike-Share"
    secret_key: SecretStr = SecretStr("super-secret-key-change-me")
    access_token_expire_minutes: int = 60 * 12
    database_url: str = "sqlite:///./bikeshare.db"
    feature_advanced: bool = False  # enable post-MVP features
    geofence_buffer_m: float = 5.0
    default_graph_name: str = "toy"
    advanced_graph_name: str = "civic"
    default_speed_mps: float = 4.5
    smoothing_alpha: float = 0.35
    telemetry_min_interval_s: int = Field(default=2, ge=1)
    pricing_rounding: str = "bankers"
    service_token: SecretStr = SecretStr("dev-service-token")

    class Config:
        env_file = ".env"

    @property
    def graphs_dir(self) -> str:
        return str(Path(__file__).resolve().parent.parent / "graphs")


settings = Settings()
