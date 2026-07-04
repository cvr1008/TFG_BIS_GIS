# Se llama normalmente: preparar_entorno.ps1
# Y se ejecuta asi: .\preparar_entorno.ps1

# Define una opcion llamada -Reinstalar.
param(
    [switch]$Reinstalar
)

# Si algo falla, para el script.
$ErrorActionPreference = "Stop"

# Guarda la carpeta donde esta este script: ...\tfg\aplicaciones
$raiz = $PSScriptRoot

# Construye la ruta del Python que queremos usar: ...\tfg\aplicaciones\.venv\Scripts\python.exe
# El entorno virtual estara dentro de: aplicaciones\.venv
$python = Join-Path $raiz ".venv\Scripts\python.exe"

# Si hemos querido reinstalar y ya existe .venv, no lo borra automaticamente.
# Dice que lo borres manualmente para evitar eliminar un entorno por accidente.
if ($Reinstalar -and (Test-Path -LiteralPath (Join-Path $raiz ".venv"))) {
    throw "Para reinstalar desde cero, elimina manualmente aplicaciones\.venv y vuelve a ejecutar este script."
}

# Si no existe el Python del entorno virtual, crea un entorno virtual nuevo en aplicaciones\.venv.
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creando el entorno virtual compartido..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv (Join-Path $raiz ".venv")
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv (Join-Path $raiz ".venv")
    } else {
        throw "No se encontro Python para crear el entorno virtual."
    }
}

# Escribe el mensaje de instalacion de las dependencias.
Write-Host "Instalando las dependencias de ambas aplicaciones..."
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo actualizar pip."
}

# Instala las dependencias listadas en aplicaciones\requirements.txt.
& $python -m pip install -r (Join-Path $raiz "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron instalar las dependencias."
}

# Donde ha quedado preparado el Python.
Write-Host "Entorno preparado en $python"
