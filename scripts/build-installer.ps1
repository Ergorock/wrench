param([switch]$SkipAppBuild)

$ErrorActionPreference = "Stop"

# Builds installer/Output/Wrench-Setup-<version>.exe (NSIS 3).
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
# VIProductVersion needs X.Y.Z.0: drop any -suffix (e.g. -beta.1).
$numeric = ($version -replace '-.*$', '') + ".0"

# 3. makensis: PATH, NSIS install folders, then the electron-builder cache
#    (newest nsis-* folder, Bin\makensis.exe preferred).
$makensis = $null
$onPath = Get-Command makensis -ErrorAction SilentlyContinue
if ($onPath) {
    $makensis = $onPath.Source
}
else {
    $candidates = @(
        "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
        "$env:ProgramFiles\NSIS\makensis.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $makensis = $candidate
            break
        }
    }
}
$cache = "$env:LOCALAPPDATA\electron-builder\Cache"
if (-not $makensis -and (Test-Path $cache)) {
    $nsisDir = '^.*\\nsis-(\d+(\.\d+)+)\\.*$'
    $found = Get-ChildItem $cache -Recurse -Filter makensis.exe |
        Where-Object { $_.FullName -match $nsisDir } |
        Sort-Object @{ Expression = { [version]($_.FullName -replace $nsisDir, '$1') }; Descending = $true },
                    @{ Expression = { $_.Directory.Name -eq "Bin" }; Descending = $true } |
        Select-Object -First 1
    if ($found) {
        $makensis = $found.FullName
    }
}
if (-not $makensis) {
    throw @"
makensis (NSIS 3) not found. Searched:
  - PATH
  - ${env:ProgramFiles(x86)}\NSIS\makensis.exe
  - $env:ProgramFiles\NSIS\makensis.exe
  - $cache\nsis-*\...\makensis.exe
Install it with: winget install NSIS.NSIS
"@
}

# 4. Compile. Native tools write to stderr: judge them by exit code only.
$ErrorActionPreference = "Continue"
& $makensis "/DAPP_VERSION=$version" "/DAPP_VERSION_NUMERIC=$numeric" (Join-Path $root "installer/wrench.nsi")
if ($LASTEXITCODE -ne 0) {
    throw "makensis failed with exit code $LASTEXITCODE."
}
$ErrorActionPreference = "Stop"

# 5. Result
$setup = Join-Path $root "installer/Output/Wrench-Setup-$version.exe"
if (-not (Test-Path $setup)) {
    throw "Build finished but $setup was not found."
}
Write-Host "Built: $setup"
