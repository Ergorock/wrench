import uuid

import pytest

from wrench.core.single_instance import acquire, is_wrench_window

CURRENT = r"C:\Apps\Wrench\Wrench.exe"


def test_second_acquire_fails() -> None:
    name = f"Local\\WrenchTest-{uuid.uuid4()}"
    assert acquire(name) is True
    assert acquire(name) is False


def test_matches_title_and_same_executable() -> None:
    assert is_wrench_window("Wrench", CURRENT, CURRENT) is True


def test_matches_same_executable_name_in_another_folder() -> None:
    assert is_wrench_window("Wrench", r"D:\Copy\Wrench.exe", CURRENT) is True


def test_ignores_explorer_window_named_wrench() -> None:
    assert is_wrench_window("Wrench", r"C:\Windows\explorer.exe", CURRENT) is False


def test_ignores_other_title_with_same_executable() -> None:
    assert is_wrench_window("Wrench - Settings", CURRENT, CURRENT) is False


def test_ignores_unknown_executable() -> None:
    assert is_wrench_window("Wrench", None, CURRENT) is False


def test_executable_name_comparison_ignores_case() -> None:
    assert is_wrench_window("Wrench", r"c:\apps\wrench\WRENCH.EXE", CURRENT) is True


@pytest.mark.parametrize("title", ["wrench", "Wrench ", ""])
def test_title_must_match_exactly(title: str) -> None:
    assert is_wrench_window(title, CURRENT, CURRENT) is False
