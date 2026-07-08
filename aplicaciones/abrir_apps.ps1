# Arranca las aplicaciones desde la carpeta del proyecto.
# Usa siempre la carpeta relativa ..\datos\pacientes.


$ErrorActionPreference = "Stop"

$raiz = $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$preparar = Join-Path $raiz "preparar_entorno_offline.ps1"
$iniciar = Join-Path $raiz "iniciar_aplicaciones.ps1"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "No existe todavia aplicaciones\.venv. Preparando entorno..."
    & $preparar
}

& $iniciar `
    -PacientesDir "..\datos\pacientes" `
    -RutaPacientesFija `
    -AppHost "127.0.0.1" `
    -PublicHost "127.0.0.1"
