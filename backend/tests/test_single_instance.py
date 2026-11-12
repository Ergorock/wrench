import uuid

from wrench.core.single_instance import acquire


def test_second_acquire_fails() -> None:
    name = f"Local\\WrenchTest-{uuid.uuid4()}"
    assert acquire(name) is True
    assert acquire(name) is False
