import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wrench.shared.editors import Editor

_log = logging.getLogger(__name__)


class ToolStorage:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            _log.warning("Corrupt tool data file %s: %s", self.path, exc)
            return {}
        if not isinstance(data, dict):
            _log.warning("Tool data file %s is not a JSON object", self.path)
            return {}
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, suffix=".tmp", delete=False
        ) as tmp:
            tmp.write(text)
        try:
            os.replace(tmp.name, self.path)
        except BaseException:
            os.unlink(tmp.name)
            raise


class ToolContext:
    def __init__(
        self,
        tool_id: str,
        storage: ToolStorage,
        get_language: Callable[[], str],
        logger: logging.Logger,
        get_editors: Callable[[], list[Editor]] = lambda: [],
    ) -> None:
        self.tool_id = tool_id
        self.storage = storage
        self.logger = logger
        self._get_language = get_language
        self._get_editors = get_editors

    @property
    def language(self) -> str:
        return self._get_language()

    def editors(self) -> list[Editor]:
        return self._get_editors()
