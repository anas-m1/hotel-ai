import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/usage")
async def get_usage(last: int = 20) -> dict[str, Any]:
    """
    Return aggregated cost/token stats plus the most recent `last` requests.
    Reads directly from the JSONL cost log written by tracking/usage.py.
    """
    path = Path(settings.cost_log_path)
    if not path.exists():
        return {
            "total_requests": 0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "by_model": {},
            "recent": [],
        }

    entries: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    total_cost = sum(e.get("cost_usd", 0.0) for e in entries)
    total_tokens = sum(e.get("total_tokens", 0) for e in entries)

    # Break down cost and request count per model
    by_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "total_tokens": 0, "cost_usd": 0.0}
    )
    for e in entries:
        model = e.get("model", "unknown")
        by_model[model]["requests"] += 1
        by_model[model]["total_tokens"] += e.get("total_tokens", 0)
        by_model[model]["cost_usd"] = round(
            by_model[model]["cost_usd"] + e.get("cost_usd", 0.0), 6
        )

    return {
        "total_requests": len(entries),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "by_model": dict(by_model),
        "recent": entries[-last:],
    }
