import importlib
import logging
import pkgutil
import threading
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wrench.core.categories import category_ids
from wrench.sdk import ToolContext, ToolError, ToolManifest, ToolService, ToolStorage

logger = logging.getLogger("wrench.registry")


@dataclass(frozen=True)
class LoadedTool:
    manifest: ToolManifest
    service_cls: type[ToolService]


def _load_tool(package: str, name: str, categories: Collection[str]) -> LoadedTool:
    manifest = importlib.import_module(f"{package}.{name}.manifest").MANIFEST
    service = importlib.import_module(f"{package}.{name}.service").SERVICE
    if not isinstance(manifest, ToolManifest):
        raise TypeError("MANIFEST is not a ToolManifest")
    if manifest.id != name:
        raise ValueError(f"manifest id {manifest.id!r} differs from folder name")
    if manifest.category not in categories:
        raise ValueError(f"unknown category {manifest.category!r}")
    if not (isinstance(service, type) and issubclass(service, ToolService)):
        raise TypeError("SERVICE is not a ToolService subclass")
    return LoadedTool(manifest, service)


def discover_tools(
    package: str = "wrench.tools", known_categories: Collection[str] | None = None
) -> list[LoadedTool]:
    categories = category_ids() if known_categories is None else known_categories
    pkg = importlib.import_module(package)
    tools: list[LoadedTool] = []
    for info in pkgutil.iter_modules(pkg.__path__):
        if not info.ispkg:
            continue
        try:
            tools.append(_load_tool(package, info.name, categories))
        except Exception as exc:
            logger.error("Tool %s rejected: %s", info.name, exc)
    return sorted(tools, key=lambda t: t.manifest.id)


class ToolRegistry:
    def __init__(
        self,
        tools: list[LoadedTool],
        storage_dir: Path,
        get_language: Callable[[], str],
    ) -> None:
        self._tools = {t.manifest.id: t for t in tools}
        self._storage_dir = storage_dir
        self._get_language = get_language
        self._instances: dict[str, ToolService] = {}
        self._lock = threading.Lock()
        # pywebview runs each JS call on its own thread: a tool's actions are serialized.
        self._call_locks = {tool_id: threading.Lock() for tool_id in self._tools}

    def manifests(self) -> list[ToolManifest]:
        return [t.manifest for t in self._tools.values()]

    def _instance(self, tool_id: str) -> ToolService:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolError("unknown_tool", f"Unknown tool: {tool_id}")
        with self._lock:
            if tool_id not in self._instances:
                ctx = ToolContext(
                    tool_id,
                    ToolStorage(self._storage_dir / f"{tool_id}.json"),
                    self._get_language,
                    logging.getLogger(f"wrench.tools.{tool_id}"),
                )
                self._instances[tool_id] = tool.service_cls(ctx)
            return self._instances[tool_id]

    def call(self, tool_id: str, action: str, payload: dict[str, Any]) -> Any:
        service = self._instance(tool_id)
        with self._call_locks[tool_id]:
            return service.invoke(action, payload)
