from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8094

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "hotel-password"

    # Upstream services
    hotel_inventory_url: str = "http://hotel-inventory:8080"
    rag_pipeline_url: str = "http://rag-pipeline:8091"
    llm_gateway_url: str = "http://llm-gateway:8090"

    # GraphRAG tuning
    graph_candidates: int = 30   # how many graph results to fetch before fusion
    vector_candidates: int = 30  # how many vector results to fetch before fusion
    final_limit: int = 10        # results returned to caller

    # Self-RAG
    self_rag_model: str = "claude-haiku-4-5-20251001"
    self_rag_enabled: bool = True

    # Entity extraction
    entity_model: str = "claude-haiku-4-5-20251001"


settings = Settings()
