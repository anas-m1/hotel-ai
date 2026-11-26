from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8092
    log_level: str = "INFO"

    # Internal services
    llm_gateway_url: str = "http://llm-gateway:8090"
    rag_pipeline_url: str = "http://rag-pipeline:8091"
    booking_ops_url: str = "http://booking-ops:8081"
    hotel_inventory_url: str = "http://hotel-inventory:8080"

    # Model routed through the LLM gateway
    agent_model: str = "claude-sonnet-4-6"
    agent_temperature: float = 0.3

    # Redis — agent state persistence across sessions
    redis_url: str = "redis://redis:6379"

    # Langfuse — leave empty to disable tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse-web:3000"


settings = Settings()
