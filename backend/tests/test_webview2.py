import socket

import pytest

from wrench.core.webview2 import HKCU_SUBKEY, HKLM_SUBKEY, find_free_port, is_webview2_installed


def reader(values: dict[tuple[str, str], str | None]):
    def read_pv(hive: str, subkey: str) -> str | None:
        return values.get((hive, subkey))

    return read_pv


HKLM = ("HKLM", HKLM_SUBKEY)
HKCU = ("HKCU", HKCU_SUBKEY)


def test_subkeys_match_microsoft_documentation() -> None:
    guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    assert HKLM_SUBKEY == rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"
    assert HKCU_SUBKEY == rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"


def test_installed_per_machine() -> None:
    assert is_webview2_installed(reader({HKLM: "120.0.2210.91"})) is True


def test_installed_per_user_only() -> None:
    assert is_webview2_installed(reader({HKCU: "120.0.2210.91"})) is True


def test_falls_back_to_hkcu_when_hklm_is_zero() -> None:
    assert is_webview2_installed(reader({HKLM: "0.0.0.0", HKCU: "120.0.2210.91"})) is True


@pytest.mark.parametrize("value", ["0.0.0.0", "", None])
def test_not_installed_when_value_is_unusable(value: str | None) -> None:
    assert is_webview2_installed(reader({HKLM: value, HKCU: value})) is False


def test_not_installed_when_keys_are_missing() -> None:
    assert is_webview2_installed(reader({})) is False


def test_default_reader_does_not_raise() -> None:
    assert isinstance(is_webview2_installed(), bool)


def test_find_free_port_returns_a_bindable_port() -> None:
    port = find_free_port()
    assert 1024 <= port <= 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
