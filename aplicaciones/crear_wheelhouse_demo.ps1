# Descarga las dependencias a aplicaciones\wheelhouse para poder instalar la demo
# sin internet en el ordenador de la defensa.

$ErrorActionPreference = "Stop"

$raiz = $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$requirements = Join-Path $raiz "requirements.txt"
$wheelhouse = Join-Path $raiz "wheelhouse"

if (-not (Test-Path -LiteralPath $python)) {
    & (Join-Path $raiz "preparar_entorno.ps1")
}

New-Item -ItemType Directory -Path $wheelhouse -Force | Out-Null

& $python -m pip download -r $requirements -d $wheelhouse
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron descargar las dependencias."
}

Write-Host "Dependencias descargadas en $wheelhouse"
