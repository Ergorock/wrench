// Mirrors of the Pydantic models in backend/src/wrench/tools/script_launcher/service.py.
export interface Command {
  id: string
  name: string
  program: string
  args: string[]
  cwd: string
}

export interface Commands {
  commands: Command[]
}

export interface RunResult {
  exit_code: number | null
  timed_out: boolean
  stdout: string
  stderr: string
}
