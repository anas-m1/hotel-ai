from pathlib import Path
from typing import Any

import structlog
import yaml

from ..config import settings

log = structlog.get_logger()


class PromptRegistry:
    """
    Loads prompt definitions from YAML files at startup.
    Each file must have `name` and optionally `version` fields.
    Prompts are keyed as "name:version" and also as bare "name" (→ latest loaded).
    """

    def __init__(self) -> None:
        self._prompts: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        prompts_dir = Path(settings.prompts_dir)
        if not prompts_dir.exists():
            log.warning("prompts_dir_missing", path=str(prompts_dir))
            return

        for path in sorted(prompts_dir.glob("*.yaml")):
            try:
                data: dict[str, Any] = yaml.safe_load(path.read_text())
                name = data["name"]
                version = str(data.get("version", "latest"))
                self._prompts[f"{name}:{version}"] = data
                # Bare name always points to the last file loaded for that name.
                # Sort order (alphabetical on filename) means higher versions win.
                self._prompts[name] = data
                log.info("prompt_loaded", name=name, version=version)
            except Exception as exc:
                log.warning("prompt_load_failed", file=str(path), error=str(exc))

    def get(self, name: str, version: str | None = None) -> dict[str, Any] | None:
        key = f"{name}:{version}" if version else name
        return self._prompts.get(key)

    def list_all(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out = []
        for p in self._prompts.values():
            uid = f"{p['name']}:{p.get('version', 'latest')}"
            if uid not in seen:
                seen.add(uid)
                out.append(
                    {
                        "name": p["name"],
                        "version": p.get("version", "latest"),
                        "model": p.get("model"),
                        "description": p.get("description", ""),
                    }
                )
        return out


registry = PromptRegistry()
