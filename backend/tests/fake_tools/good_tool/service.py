from wrench.sdk import ToolContext, ToolService, action


class FakeService(ToolService):
    def __init__(self, ctx: ToolContext) -> None:
        super().__init__(ctx)
        self._count = 0

    @action
    def ping(self) -> str:
        return "pong"

    @action
    def count(self) -> int:
        self._count += 1
        return self._count


SERVICE = FakeService
