"""Application settings.

Values are read from environment variables (or a local `.env` file) but every
setting has a working default, so the app boots with zero configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KPi-Tech Job Board API"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720  # 12 hours - long enough for a demo session
    database_url: str = "sqlite:///./jobboard.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Optional LLM re-ranking layer (Groq) ------------------------------
    # The matcher works fully without any of this. When a key is present the
    # top deterministic results are re-ranked and re-explained by an LLM; if
    # the key is missing, the call fails, or it times out, the deterministic
    # result is returned unchanged.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: float = 8.0
    # How many of the top deterministic results get sent to the LLM.
    llm_rerank_candidates: int = 8
    # Final score = (1 - w) * deterministic + w * LLM relevance.
    llm_blend_weight: float = 0.5

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
