from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    deepgram_api_key: str
    deepgram_project_id: str

    twilio_account_sid: str
    twilio_auth_token: str

    ollama_cloud_api_key: str
    ollama_cloud_endpoint: str = "https://api.ollama.com/v1"

    host: str = "0.0.0.0"
    port: int = 8001

    internal_api_key: str = ""

    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/ai_reception"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    domain: str = "reception.monizhealth.com"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    twilio_phone_number_sid: str = ""


settings = Settings()
