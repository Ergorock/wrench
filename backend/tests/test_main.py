from wrench.api import Api
from wrench.main import _exposed


def test_only_the_four_bridge_methods_are_exposed(api: Api) -> None:
    exposed = _exposed(api)
    assert [f.__name__ for f in exposed] == [
        "get_bootstrap",
        "save_settings",
        "set_autostart",
        "tool_call",
    ]
    assert all(getattr(f, "__self__", None) is api for f in exposed)
