$ErrorActionPreference = "Stop"

# Builds dist/Wrench/Wrench.exe (PyInstaller --onedir, no console).
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Step {
    param([string]$Directory, [scriptblock]$Command)
    Push-Location $Directory
    # Native tools (uv, npm) write progress to stderr: judge them by exit code only.
    $ErrorActionPreference = "Continue"
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE (in $Directory)."
        }
    }
    finally {
        $ErrorActionPreference = "Stop"
        Pop-Location
    }
}

# 1. Frontend
Invoke-Step (Join-Path $root "frontend") { npm ci }
Invoke-Step (Join-Path $root "frontend") { npm run build }

# 2. Backend dependencies
Invoke-Step (Join-Path $root "backend") { uv sync }

# 3. PyInstaller, run from backend/
Invoke-Step (Join-Path $root "backend") {
    uv run pyinstaller --noconfirm --clean --windowed --onedir --name Wrench `
        --icon assets/wrench.ico --distpath ../dist --workpath ../build `
        --add-data "../frontend/dist;frontend/dist" `
        --collect-submodules wrench.tools --collect-data wrench.tools launcher.py
}

# 4. Result
$exe = Join-Path $root "dist/Wrench/Wrench.exe"
if (-not (Test-Path $exe)) {
    throw "Build finished but $exe was not found."
}
Write-Host "Built: $exe"
