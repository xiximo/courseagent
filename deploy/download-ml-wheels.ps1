# Download Linux ML wheels into backend/wheels via a temp container.
# Usage: .\deploy\download-ml-wheels.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$WheelDir = Join-Path $Root "backend\wheels"
$ScriptSh = Join-Path $PSScriptRoot "download-ml-wheels.sh"
New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null

$PyImage = "docker.1ms.run/library/python:3.12-slim-bookworm"

Write-Host "==> docker pull $PyImage"
docker pull $PyImage
if ($LASTEXITCODE -ne 0) { throw "docker pull failed" }

Write-Host "==> download wheels into backend\wheels (this can take a long time)"
docker run --rm `
  -v "${WheelDir}:/wheels" `
  -v "${Root}\backend\requirements-api.txt:/req/requirements-api.txt:ro" `
  -v "${Root}\backend\requirements-ml.txt:/req/requirements-ml.txt:ro" `
  -v "${ScriptSh}:/download.sh:ro" `
  $PyImage `
  bash /download.sh

if ($LASTEXITCODE -ne 0) { throw "download failed" }

$count = (Get-ChildItem $WheelDir -Filter *.whl -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "Done: $WheelDir ($count whl files)"
Write-Host "Next: .\deploy\build-and-export.ps1 -Target backend-ml"
