# Prepara aplicaciones\.venv.
# Si existe aplicaciones\wheelhouse, instala desde ahi sin internet.
# Si no existe, intenta instalar desde internet como preparar_entorno.ps1.

param(
    [switch]$Reinstalar
)

$ErrorActionPreference = "Stop"

$raiz = $PSScriptRoot
$venv = Join-Path $raiz ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$requirements = Join-Path $raiz "requirements.txt"
$wheelhouse = Join-Path $raiz "wheelhouse"

if ($Reinstalar -and (Test-Path -LiteralPath $venv)) {
    throw "Para reinstalar desde cero, elimina manualmente aplicaciones\.venv y vuelve a ejecutar este script."
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creando el entorno virtual..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv $venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv $venv
    } else {
        throw "No se encontro Python. Instala Python 3.9-3.12 o incluyelo en el pendrive."
    }
}

$ruedas = @()
if (Test-Path -LiteralPath $wheelhouse) {
    $ruedas = Get-ChildItem -LiteralPath $wheelhouse -Filter "*.whl" -ErrorAction SilentlyContinue
}

if ($ruedas.Count -gt 0) {
    Write-Host "Instalando dependencias desde wheelhouse, sin internet..."
    & $python -m pip install --no-index --find-links $wheelhouse -r $requirements
} else {
    Write-Host "No hay wheelhouse. Instalando dependencias desde internet..."
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo actualizar pip."
    }
    & $python -m pip install -r $requirements
}

if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron instalar las dependencias."
}

Write-Host "Entorno preparado en $python"
