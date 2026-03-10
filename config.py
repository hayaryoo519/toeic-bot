from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LINE_CHANNEL_SECRET: str
    LINE_CHANNEL_ACCESS_TOKEN: str
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./toeic_bot.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"  # 他の環境変数があっても無視するように設定
    )

settings = Settings()
