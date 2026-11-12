"""Errors of git operations, with a stable code the interface can translate."""


class GitOpError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
