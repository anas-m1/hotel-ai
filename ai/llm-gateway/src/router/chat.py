from typing import Any

import litellm
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..prompts.registry import registry
from ..tracking.usage import record_usage

log = structlog.get_logger()
router = APIRouter()


class Message(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    # If set, prepends the named prompt's system message and inherits its default model
    prompt_name: str | None = None
    prompt_version: str | None = None


def provider_options(model: str) -> dict[str, Any]:
    """Provider credentials/endpoints come only from server configuration."""
    if model.startswith("ollama_chat/"):
        return {"api_base": settings.ollama_api_base}
    if model.startswith("openrouter/"):
        if not settings.openrouter_api_key:
            raise HTTPException(status_code=503, detail="OpenRouter is not configured")
        return {"api_base": "https://openrouter.ai/api/v1", "api_key": settings.openrouter_api_key}
    if model.startswith("hosted_vllm/"):
        if not settings.self_hosted_api_base:
            raise HTTPException(status_code=503, detail="Self-hosted inference is not configured")
        options = {"api_base": settings.self_hosted_api_base}
        if settings.self_hosted_api_key:
            options["api_key"] = settings.self_hosted_api_key
        return options
    return {}


@router.post("/chat/completions")
async def chat_completions(req: ChatRequest) -> dict[str, Any]:
    model = req.model or settings.default_model
    messages: list[dict[str, Any]] = [m.model_dump() for m in req.messages]

    # Inject system prompt from registry when caller specifies a named prompt.
    # The prompt's `model` field overrides the default; the caller can still
    # override further by setting `model` explicitly in the request.
    if req.prompt_name:
        prompt = registry.get(req.prompt_name, req.prompt_version)
        if prompt is None:
            raise HTTPException(
                status_code=404,
                detail=f"Prompt '{req.prompt_name}' version '{req.prompt_version}' not found",
            )
        if "system" in prompt:
            messages = [{"role": "system", "content": prompt["system"]}, *messages]
        if req.model is None:
            model = prompt.get("model", model)

    log.info("llm_request", model=model, messages=len(messages))

    options = provider_options(model)

    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            tools=req.tools,
            tool_choice=req.tool_choice,
            **options,
        )
    except litellm.AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Provider authentication failed") from exc
    except litellm.RateLimitError as exc:
        raise HTTPException(status_code=429, detail="Provider rate limit exceeded") from exc
    except litellm.ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Provider unavailable") from exc
    except litellm.APIConnectionError as exc:
        log.error("llm_provider_connection_error", model=model, error_type=type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not reach provider") from exc
    except Exception as exc:
        log.error("llm_call_failed", model=model, error_type=type(exc).__name__)
        raise HTTPException(status_code=502, detail="LLM provider error") from exc

    record_usage(model=model, response=response)

    return response.model_dump()
