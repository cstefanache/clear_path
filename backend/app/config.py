from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://clearroute:clearroute_dev@db:5432/clearroute"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


settings = Settings()
