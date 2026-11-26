from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8090
    log_level: str = "INFO"

    # Provider keys — set at least one
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    self_hosted_api_base: str = ""
    self_hosted_api_key: str = ""
    # For AWS Bedrock: set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION in env
    aws_region: str = "us-east-1"

    # Default model when the caller doesn't specify one
    default_model: str = "claude-sonnet-4-6"
    # Ollama is optional; Docker Compose resolves this host on its internal network.
    ollama_api_base: str = "http://ollama:11434"

    # Append cost records here as JSONL (one line per request)
    cost_log_path: str = "/tmp/llm-usage.jsonl"

    # Where to find prompt YAML files (relative to the project root)
    prompts_dir: str = "prompts"

    # Langfuse — leave empty to disable tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse-web:3000"


settings = Settings()
