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
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    # If set, prepends the named prompt's system message and inherits its default model
    prompt_name: str | None = None
    prompt_version: str | None = None


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

    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except litellm.AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=f"Provider authentication failed: {exc}") from exc
    except litellm.RateLimitError as exc:
        raise HTTPException(status_code=429, detail="Provider rate limit exceeded") from exc
    except litellm.ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Provider unavailable") from exc
    except litellm.APIConnectionError as exc:
        raise HTTPException(status_code=502, detail="Could not reach provider") from exc
    except Exception as exc:
        log.error("llm_call_failed", model=model, error=str(exc))
        raise HTTPException(status_code=502, detail="LLM provider error") from exc

    record_usage(model=model, response=response)

    return response.model_dump()
