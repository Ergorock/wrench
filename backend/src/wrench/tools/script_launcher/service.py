import locale
import subprocess
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from wrench.sdk import ToolError, ToolService, action

TIMEOUT_SECONDS = 60
MAX_OUTPUT_CHARS = 20_000
MAX_COMMANDS = 100
MAX_ARGS = 50
# Hides the console window that a child process would otherwise open on Windows.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Command(BaseModel):
    """A command the user defined. Empty `id` means a new command."""

    id: str = ""
    name: str = Field(min_length=1, max_length=60)
    # An executable, given by its full path or by a name found on PATH (must be a .exe).
    program: str = Field(min_length=1, max_length=260)
    args: list[str] = Field(default_factory=list, max_length=MAX_ARGS)
    cwd: str = ""


class Commands(BaseModel):
    commands: list[Command]


class RunResult(BaseModel):
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str


def _text(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        text = data
    else:
        text = data.decode(locale.getpreferredencoding(False), "replace")
    return text[:MAX_OUTPUT_CHARS]


class ScriptLauncherService(ToolService):
    def _commands(self) -> list[Command]:
        """Stored commands. A malformed entry is ignored rather than breaking the list."""
        stored = self.ctx.storage.load().get("commands", [])
        if not isinstance(stored, list):
            return []
        result: list[Command] = []
        for item in stored:
            try:
                result.append(Command.model_validate(item))
            except ValueError:
                continue
        return result

    def _save_commands(self, commands: list[Command]) -> None:
        self.ctx.storage.save({"commands": [c.model_dump() for c in commands]})

    def _find(self, command_id: str) -> Command:
        for command in self._commands():
            if command.id == command_id:
                return command
        raise ToolError("unknown_command", f"Unknown command: {command_id}")

    @action
    def list_commands(self) -> Commands:
        return Commands(commands=self._commands())

    @action
    def save_command(self, command: Command) -> Commands:
        name = command.name.strip()
        program = command.program.strip()
        cwd = command.cwd.strip()
        if not name or not program:
            raise ToolError("invalid_command", "A command needs a name and a program.")
        if cwd and not Path(cwd).is_dir():
            raise ToolError("folder_not_found", f"Folder not found: {cwd}")
        args = [a.strip() for a in command.args if a.strip()]
        commands = self._commands()
        saved = Command(
            id=command.id or uuid.uuid4().hex, name=name, program=program, args=args, cwd=cwd
        )
        if command.id:
            index = next((i for i, c in enumerate(commands) if c.id == command.id), None)
            if index is None:
                raise ToolError("unknown_command", f"Unknown command: {command.id}")
            commands[index] = saved
        else:
            if len(commands) >= MAX_COMMANDS:
                raise ToolError("too_many_commands", "The list is full.")
            commands.append(saved)
        self._save_commands(commands)
        return Commands(commands=commands)

    @action
    def delete_command(self, command_id: str) -> Commands:
        commands = self._commands()
        remaining = [c for c in commands if c.id != command_id]
        if len(remaining) == len(commands):
            raise ToolError("unknown_command", f"Unknown command: {command_id}")
        self._save_commands(remaining)
        return Commands(commands=remaining)

    @action
    def run_command(self, command_id: str) -> RunResult:
        """Run the saved program directly, without a shell, and wait for it to finish."""
        command = self._find(command_id)
        cwd = command.cwd or None
        if cwd is not None and not Path(cwd).is_dir():
            raise ToolError("folder_not_found", f"Folder not found: {cwd}")
        try:
            completed = subprocess.run(
                [command.program, *command.args],
                cwd=cwd,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=TIMEOUT_SECONDS,
                creationflags=NO_WINDOW,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            return RunResult(
                exit_code=None, timed_out=True, stdout=_text(e.stdout), stderr=_text(e.stderr)
            )
        except FileNotFoundError as e:
            raise ToolError("program_not_found", f"Program not found: {command.program}") from e
        except OSError as e:
            raise ToolError("program_failed", f"Cannot start {command.program}: {e}") from e
        return RunResult(
            exit_code=completed.returncode,
            timed_out=False,
            stdout=_text(completed.stdout),
            stderr=_text(completed.stderr),
        )


SERVICE = ScriptLauncherService
