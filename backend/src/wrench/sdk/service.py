from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter, ValidationError, validate_call

from wrench.sdk.context import ToolContext
from wrench.sdk.errors import ToolError


def action[F: Callable[..., Any]](fn: F) -> F:
    wrapper = validate_call(validate_return=True)(fn)
    wrapper.__wrench_action__ = True  # type: ignore[attr-defined]
    return wrapper


class ToolService:
    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx

    def invoke(self, action: str, payload: dict[str, Any]) -> Any:
        method = None if action.startswith("_") else getattr(type(self), action, None)
        if method is None or not getattr(method, "__wrench_action__", False):
            raise ToolError("unknown_action", f"Unknown action: {action}")
        try:
            result = getattr(self, action)(**payload)
        except ValidationError as exc:
            raise ToolError("invalid_payload", str(exc)) from exc
        return TypeAdapter(Any).dump_python(result, mode="json")
