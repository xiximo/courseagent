<#
.SYNOPSIS
  docker save already-built images (does not pull or build).

  Build yourself first, then:
    .\deploy\build-and-export.ps1 -Target web
    .\deploy\build-and-export.ps1 -Target backend-ml
#>
param(
    [ValidateSet("backend", "backend-ml", "web", "all")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$OutDir = Join-Path $Root "deploy\dist"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Save-Image([string]$Name, [string]$Image) {
    $Tar = Join-Path $OutDir "$Name-$Stamp.tar"
    Write-Host ("==> docker save {0} -> {1}" -f $Image, $Tar)
    docker save -o $Tar $Image
    if ($LASTEXITCODE -ne 0) { throw "save failed: $Image" }
    $Mb = [math]::Round((Get-Item $Tar).Length / 1MB, 1)
    Write-Host ("done: {0} ({1} MB)" -f $Tar, $Mb)
    return $Tar
}

$built = @()
if ($Target -eq "backend" -or $Target -eq "all") {
    $built += Save-Image "courseagent-backend" "courseagent-backend:latest"
}
if ($Target -eq "backend-ml") {
    $built += Save-Image "courseagent-backend-ml" "courseagent-backend:ml"
}
if ($Target -eq "web" -or $Target -eq "all") {
    $built += Save-Image "courseagent-web" "courseagent-web:latest"
}

Write-Host ""
Write-Host "upload example:"
foreach ($t in $built) {
    Write-Host ("  scp `"{0}`" root@YOUR_SERVER:/opt/courseagent/" -f $t)
}
Write-Host "on server: docker load -i <tar>"
