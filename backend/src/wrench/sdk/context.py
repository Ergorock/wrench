import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class ToolStorage:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _log.warning("Corrupt tool data file %s: %s", self.path, exc)
            return {}
        if not isinstance(data, dict):
            _log.warning("Tool data file %s is not a JSON object", self.path)
            return {}
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


class ToolContext:
    def __init__(
        self,
        tool_id: str,
        storage: ToolStorage,
        get_language: Callable[[], str],
        logger: logging.Logger,
    ) -> None:
        self.tool_id = tool_id
        self.storage = storage
        self.logger = logger
        self._get_language = get_language

    @property
    def language(self) -> str:
        return self._get_language()
