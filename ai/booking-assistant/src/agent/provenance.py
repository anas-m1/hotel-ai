"""Non-secret runtime identity for reproducible evaluations."""

import hashlib
from functools import lru_cache
from pathlib import Path

from config import settings

from .nodes import MAX_STEPS


@lru_cache(maxsize=1)
def eval_info() -> dict:
    source = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*.py")):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(path.read_bytes())
    return {
        "model": settings.agent_model,
        "temperature": settings.agent_temperature,
        "max_steps": MAX_STEPS,
        "read_only_evals_supported": True,
        "source_sha256": digest.hexdigest(),
    }
