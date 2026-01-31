param(
    [switch]$Install,
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendDir = Join-Path $root "frontend"
$backendDir = Join-Path $root "backend"
$backendStaticDir = Join-Path $backendDir "static"
$frontendBuildDir = Join-Path $frontendDir "build"

Push-Location $frontendDir
try {
    if ($Install -or -not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        npm install
    }
    elseif ($Build) {
        npm run build
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $frontendBuildDir)) {
    throw "Frontend build output not found at $frontendBuildDir"
}

New-Item -ItemType Directory -Force -Path $backendStaticDir | Out-Null
Copy-Item -Path (Join-Path $frontendBuildDir "*") -Destination $backendStaticDir -Recurse -Force

Push-Location $backendDir
try {
    ./env/Scripts/activate
    python main.py
} finally {
    Pop-Location
}
