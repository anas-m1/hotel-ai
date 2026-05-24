from typing import Any

from fastapi import APIRouter, HTTPException

from ..prompts.registry import registry

router = APIRouter()

# Curated list of models this gateway is configured to route.
# Extend as you add provider keys.
_SUPPORTED_MODELS = [
    {"id": "claude-sonnet-4-6", "provider": "anthropic"},
    {"id": "claude-opus-4-7", "provider": "anthropic"},
    {"id": "claude-haiku-4-5-20251001", "provider": "anthropic"},
    {"id": "gpt-4o", "provider": "openai"},
    {"id": "gpt-4o-mini", "provider": "openai"},
    {"id": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0", "provider": "aws_bedrock"},
]


@router.get("/models")
async def list_models() -> dict[str, Any]:
    return {"object": "list", "data": _SUPPORTED_MODELS}


@router.get("/prompts")
async def list_prompts() -> dict[str, Any]:
    return {"prompts": registry.list_all()}


@router.get("/prompts/{name}")
async def get_prompt(name: str, version: str | None = None) -> dict[str, Any]:
    prompt = registry.get(name, version)
    if prompt is None:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return prompt
