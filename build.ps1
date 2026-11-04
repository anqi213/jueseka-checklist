# 角色卡创作清单 — 一键打包脚本
# 在 PowerShell 中运行：.\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$appName = "角色卡创作清单"
$python = "python"
if (Test-Path (Join-Path $root ".venv\Scripts\python.exe")) {
    $python = Join-Path $root ".venv\Scripts\python.exe"
}

$assets = Join-Path $root "assets"
$icon = Join-Path $assets "app.ico"
$versionFile = Join-Path $root "build\version_info.txt"
$entry = Join-Path $root "app.py"
$dist = Join-Path $root "dist"
$appDir = Join-Path $dist $appName

Write-Host "检查 PyInstaller..." -ForegroundColor Cyan
& $python -m PyInstaller --version

Write-Host "开始打包（便携文件夹版）..." -ForegroundColor Cyan
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name $appName `
    --icon $icon `
    --add-data "$assets;assets" `
    --version-file $versionFile `
    --distpath $dist `
    --workpath (Join-Path $root "build\pyinstaller") `
    --specpath (Join-Path $root "build") `
    $entry

$exe = Join-Path $appDir "$appName.exe"
if (-not (Test-Path $exe)) {
    throw "打包失败：没有找到 $exe"
}
Copy-Item (Join-Path $root "README.md") (Join-Path $appDir "README.md") -Force

Write-Host ""
Write-Host "完成：$exe" -ForegroundColor Green
Write-Host "把整个「$appName」文件夹复制到任意位置，双击 exe 即可运行。" -ForegroundColor Yellow
Write-Host "首次运行如遇 SmartScreen，请点「更多信息」→「仍要运行」。" -ForegroundColor Yellow
