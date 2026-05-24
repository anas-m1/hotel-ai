import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import litellm
import structlog

from ..config import settings

log = structlog.get_logger()


def record_usage(model: str, response: Any) -> None:
    usage = getattr(response, "usage", None)

    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
        "cost_usd": round(cost, 6),
    }

    log.info("llm_usage", **entry)

    try:
        Path(settings.cost_log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(settings.cost_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        log.warning("cost_log_write_failed", error=str(exc))
