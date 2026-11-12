import functools
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import TypeAdapter, ValidationError, validate_call

from wrench.sdk.context import ToolContext
from wrench.sdk.errors import ToolError


class _ActionBug(Exception):
    """Wraps a ValidationError raised by an action body or by its return value, so it is
    not mistaken for an argument validation error."""

    def __init__(self, error: ValidationError) -> None:
        super().__init__(str(error))
        self.error = error


def action[F: Callable[..., Any]](fn: F) -> F:
    @functools.cache
    def return_adapter() -> TypeAdapter[Any] | None:
        # Resolved on first call so that forward references are defined by then.
        returns = get_type_hints(fn).get("return", inspect.Signature.empty)
        return None if returns is inspect.Signature.empty else TypeAdapter(returns)

    @functools.wraps(fn)
    def body(*args: Any, **kwargs: Any) -> Any:
        try:
            result = fn(*args, **kwargs)
            adapter = return_adapter()
            return result if adapter is None else adapter.validate_python(result)
        except ValidationError as exc:
            raise _ActionBug(exc) from exc

    # Only the arguments are validated here: a ValidationError from this wrapper is
    # always the caller's fault.
    wrapper = validate_call(validate_return=False)(body)
    wrapper.__wrench_action__ = True  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


class ToolService:
    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx

    def invoke(self, action: str, payload: dict[str, Any]) -> Any:
        method = None if action.startswith("_") else getattr(type(self), action, None)
        if method is None or not getattr(method, "__wrench_action__", False):
            raise ToolError("unknown_action", f"Unknown action: {action}")
        if not isinstance(payload, dict):
            self.ctx.logger.warning("Invalid payload for %s: not an object", action)
            raise ToolError("invalid_payload", "Payload must be an object")
        try:
            result = getattr(self, action)(**payload)
        except ValidationError as exc:
            self.ctx.logger.warning("Invalid payload for %s: %s", action, exc)
            raise ToolError("invalid_payload", str(exc)) from exc
        except _ActionBug as exc:
            raise exc.error from None
        return TypeAdapter(Any).dump_python(result, mode="json")
