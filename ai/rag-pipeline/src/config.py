from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8091
    log_level: str = "INFO"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""  # empty = unauthenticated (local dev default)
    hotels_collection: str = "hotels"

    # hotel-inventory service — source of truth for hotel data
    hotel_inventory_url: str = "http://hotel-inventory:8080"

    # Local embedding models (fastembed downloads on first use, ~100 MB total)
    dense_model: str = "BAAI/bge-small-en-v1.5"  # 384 dims
    sparse_model: str = "Qdrant/bm42-all-minilm-l6-v2-attentions"

    # Search tuning
    prefetch_limit: int = 50  # candidates fetched per vector type before RRF fusion
    search_limit: int = 10  # final results returned to caller


settings = Settings()
