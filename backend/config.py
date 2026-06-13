import secrets
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/lexicon.db"
    lexicon_json_path: str = str(Path(__file__).parent / "data" / "lexicon.json")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    admin_token: str = ""
    jwt_secret: str = ""

    cors_allow_origins: str = ""

    cache_ttl: int = 300
    cache_max_items: int = 10000
    rate_limit_daily: int = 5
    rate_limit_member: int = 100

    class Config:
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.admin_token:
            self.admin_token = secrets.token_urlsafe(24)
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_urlsafe(32)


settings = Settings()
