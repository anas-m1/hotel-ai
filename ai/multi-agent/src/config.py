from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8093
    llm_gateway_url: str = "http://llm-gateway:8090"
    rag_pipeline_url: str = "http://rag-pipeline:8091"
    booking_ops_url: str = "http://booking-ops:8081"
    hotel_inventory_url: str = "http://hotel-inventory:8080"

    supervisor_model: str = "claude-sonnet-4-6"
    worker_model: str = "claude-haiku-4-5-20251001"
    agent_temperature: float = 0.1

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_group_id: str = "multi-agent"
    kafka_booking_topic: str = "hotel.booking.events"
    kafka_agent_topic: str = "hotel.agent.events"


settings = Settings()
