import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")
    LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")

    class Config:
        env_file = ".env"

settings = Settings()
