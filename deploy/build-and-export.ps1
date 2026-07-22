<#
.SYNOPSIS
  单独构建并导出 backend / web 镜像（不依赖 compose）。

.PARAMETER Target
  backend      = 轻量后端（无 torch）
  backend-ml   = 全量后端（含 embedding，需先下 wheel 更稳）
  web          = 前端
  all          = 轻量后端 + 前端

.EXAMPLE
  .\deploy\build-and-export.ps1 -Target web
  .\deploy\build-and-export.ps1 -Target backend
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

function Build-And-Save([string]$Name, [string]$Context, [string]$Image, [string]$Dockerfile = "Dockerfile") {
    Write-Host "==> docker build $Name ($Dockerfile)"
    docker build -f (Join-Path $Context $Dockerfile) -t $Image $Context
    if ($LASTEXITCODE -ne 0) { throw "build failed: $Name" }

    $Tar = Join-Path $OutDir "$Name-$Stamp.tar"
    Write-Host "==> docker save $Image -> $Tar"
    docker save -o $Tar $Image
    if ($LASTEXITCODE -ne 0) { throw "save failed: $Name" }

    $Mb = [math]::Round((Get-Item $Tar).Length / 1MB, 1)
    Write-Host "完成: $Tar ($Mb MB)"
    return $Tar
}

$built = @()
if ($Target -eq "backend" -or $Target -eq "all") {
    $built += Build-And-Save "courseagent-backend" ".\backend" "courseagent-backend:latest" "Dockerfile"
}
if ($Target -eq "backend-ml") {
    $wheelDir = Join-Path $Root "backend\wheels"
    $hasWheel = (Get-ChildItem $wheelDir -Filter *.whl -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
    if (-not $hasWheel) {
        Write-Host "未检测到 backend\wheels\*.whl，建议先运行: .\deploy\download-ml-wheels.ps1"
        Write-Host "将继续在线构建（可能很慢或超时）..."
    }
    $built += Build-And-Save "courseagent-backend-ml" ".\backend" "courseagent-backend:ml" "Dockerfile.ml"
}
if ($Target -eq "web" -or $Target -eq "all") {
    $built += Build-And-Save "courseagent-web" ".\webadmin" "courseagent-web:latest"
}

Write-Host ""
Write-Host "上传示例:"
foreach ($t in $built) {
    Write-Host "  scp `"$t`" root@YOUR_SERVER:/opt/courseagent/"
}
Write-Host ""
Write-Host "服务器加载: docker load -i <tar文件>"
Write-Host "运行说明见 deploy/README.md"
