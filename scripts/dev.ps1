# Lance Wrench en mode dev : serveur Vite en arrière-plan + fenêtre pywebview.
# Compatible Windows PowerShell 5.1 et PowerShell 7, depuis n'importe quel dossier.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'frontend'
$backend = Join-Path $root 'backend'
$url = 'http://localhost:5173'

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    throw "node_modules est absent : lancez 'npm ci' dans frontend/ avant ce script."
}

$env:WRENCH_DEV = '1'
if (-not $env:WRENCH_DATA_DIR) {
    $env:WRENCH_DATA_DIR = Join-Path $env:TEMP 'wrench-dev'
}

$vite = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
    -WorkingDirectory $frontend -WindowStyle Hidden -PassThru
try {
    $deadline = (Get-Date).AddSeconds(30)
    $ready = $false
    while (-not $ready) {
        if ($vite.HasExited) { throw "Vite s'est arrêté (code $($vite.ExitCode))." }
        if ((Get-Date) -gt $deadline) { throw "Vite ne répond pas sur $url après 30 s." }
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
            $ready = $true
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    Push-Location $backend
    try { uv run python -m wrench } finally { Pop-Location }
} finally {
    # npm.cmd lance node en enfant : on arrête tout l'arbre de processus.
    if (-not $vite.HasExited) { taskkill /PID $vite.Id /T /F | Out-Null }
}
