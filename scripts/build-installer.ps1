param([switch]$SkipAppBuild)

$ErrorActionPreference = "Stop"

# Builds installer/Output/Wrench-Setup-<version>.exe (Inno Setup 6).
$root = Split-Path -Parent $PSScriptRoot

# 1. Application (dist/Wrench), unless an existing build is reused
if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot "build.ps1")
}
if (-not (Test-Path (Join-Path $root "dist/Wrench/Wrench.exe"))) {
    throw "dist/Wrench/Wrench.exe not found. Run scripts/build.ps1 first."
}

# 2. Version
$versionFile = Join-Path $root "backend/src/wrench/_version.py"
$match = Select-String -Path $versionFile -Pattern '__version__ = "(.+)"'
if (-not $match) {
    throw "No __version__ found in $versionFile."
}
$version = $match.Matches[0].Groups[1].Value

# 3. iscc
$iscc = $null
$onPath = Get-Command iscc -ErrorAction SilentlyContinue
if ($onPath) {
    $iscc = $onPath.Source
}
else {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $iscc = $candidate
            break
        }
    }
}
if (-not $iscc) {
    throw "Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php"
}

# 4. Compile. Native tools write to stderr: judge them by exit code only.
$ErrorActionPreference = "Continue"
& $iscc "/DAppVersion=$version" (Join-Path $root "installer/wrench.iss")
if ($LASTEXITCODE -ne 0) {
    throw "iscc failed with exit code $LASTEXITCODE."
}
$ErrorActionPreference = "Stop"

# 5. Result
$setup = Join-Path $root "installer/Output/Wrench-Setup-$version.exe"
if (-not (Test-Path $setup)) {
    throw "Build finished but $setup was not found."
}
Write-Host "Built: $setup"
