from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "nfce-processor-api"
    app_version: str = "1.0.0"
    request_timeout_seconds: float = 20.0
    user_agent: str = "Mozilla/5.0 (compatible; NFCEProcessor/1.0)"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
