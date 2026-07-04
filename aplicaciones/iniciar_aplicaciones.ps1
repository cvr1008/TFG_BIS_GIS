# Script de PowerShell.
# Sirve para:
# - no tener que arrancar a mano las tres aplicaciones una por una;
# - configurar rutas, puertos y variables de entorno;
# - arrancar portal, organizador y visualizador;
# - mostrar las URLs;
# - abrir Chrome si no se indica lo contrario.

param(
    [string]$PacientesDir = "", # carpeta de pacientes a usar
    [string]$AppHost = "127.0.0.1", # desde que direcciones la app acepta visitas
    [string]$PublicHost = "", # IP publica/interna que vera el usuario
    [int]$PortalPort = 8040, # puerto del portal
    [int]$VisualizadorPort = 8050, # puerto del visualizador
    [int]$OrganizadorPort = 8060, # puerto del organizador
    [switch]$RutaPacientesFija, # activa modo "no elegir carpeta"
    [switch]$NoAbrirNavegador # arranca todo sin abrir Chrome
)

# [switch]: interruptor true/false segun se ponga o no.

# Si algo falla, para el script.
$ErrorActionPreference = "Stop"

# $PSScriptRoot: carpeta donde esta este .ps1 (tfg\aplicaciones)
$raiz = $PSScriptRoot

# Entorno Python propio del proyecto.
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encontro aplicaciones\.venv. Ejecuta primero .\preparar_entorno.ps1"
}

# Carpeta final de pacientes.
$raizProyecto = Split-Path $raiz -Parent
$pacientesNuevo = Join-Path $raizProyecto "datos\pacientes"

# Si has indicado una carpeta, usa esa.
# Si no, usa datos\pacientes. Si no existe, la crea.
if ($PacientesDir) {
    New-Item -ItemType Directory -Path $PacientesDir -Force | Out-Null
    $directorioPacientes = (Resolve-Path -LiteralPath $PacientesDir).Path
} elseif (Test-Path -LiteralPath $pacientesNuevo) {
    $directorioPacientes = (Resolve-Path -LiteralPath $pacientesNuevo).Path
} else {
    New-Item -ItemType Directory -Path $pacientesNuevo -Force | Out-Null
    $directorioPacientes = (Resolve-Path -LiteralPath $pacientesNuevo).Path
}

# $AppHost es donde escucha Dash.
# En local: 127.0.0.1.
# En HUBU: 0.0.0.0 para aceptar visitas desde otros equipos de la intranet.
$urlHost = if ($PublicHost) {
    $PublicHost
} elseif ($AppHost -eq "0.0.0.0") {
    "127.0.0.1"
} else {
    $AppHost
}

# Variables de entorno que leen las tres aplicaciones Dash.
$env:TFG_PACIENTES_DIR = $directorioPacientes
$env:TFG_DASH_HOST = $AppHost
$env:TFG_PORTAL_PORT = "$PortalPort"
$env:TFG_VISUALIZADOR_PORT = "$VisualizadorPort"
$env:TFG_ORGANIZADOR_PORT = "$OrganizadorPort"
$env:TFG_RUTA_PACIENTES_FIJA = if ($RutaPacientesFija) { "1" } else { "0" }

# URLs que usara el portal para enlazar al organizador y al visualizador.
$env:TFG_PORTAL_URL = "http://${urlHost}:$PortalPort/"
$env:TFG_VISUALIZADOR_URL = "http://${urlHost}:$VisualizadorPort/"
$env:TFG_ORGANIZADOR_URL = "http://${urlHost}:$OrganizadorPort/"

# Carpeta interna que guarda los PID.
# Un PID es el numero del proceso arrancado.
$runtime = Join-Path $raiz ".runtime"
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

function Start-DashApp {
    param(
        [string]$Nombre, # nombre visible de la app
        [string]$Directorio, # carpeta donde esta app.py
        [string]$PidFile # archivo donde se guarda el PID
    )

    # Si ya hay un PID vivo, no arranca la app dos veces.
    if (Test-Path -LiteralPath $PidFile) {
        $pidGuardado = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
        if ($pidGuardado -and (Get-Process -Id $pidGuardado -ErrorAction SilentlyContinue)) {
            Write-Host "$Nombre ya esta en ejecucion (PID $pidGuardado)."
            return
        }
    }

    # Ejecuta python app.py dentro de la carpeta de esa app sin abrir ventana.
    $proceso = Start-Process `
        -FilePath $python `
        -ArgumentList "app.py" `
        -WorkingDirectory $Directorio `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -LiteralPath $PidFile -Value $proceso.Id -Encoding ascii
    Write-Host "$Nombre iniciado (PID $($proceso.Id))."
}

# Arrancar las tres apps. Cada una queda en su puerto.
Start-DashApp `
    -Nombre "Portal BIS-ICCA" `
    -Directorio (Join-Path $raiz "portal_bis_icca") `
    -PidFile (Join-Path $runtime "portal.pid")

Start-DashApp `
    -Nombre "Organizador BIS-ICCA" `
    -Directorio (Join-Path $raiz "organizador_bis_icca") `
    -PidFile (Join-Path $runtime "organizador.pid")

Start-DashApp `
    -Nombre "Visualizador BIS-ICCA" `
    -Directorio (Join-Path $raiz "visualizador_bis_icca") `
    -PidFile (Join-Path $runtime "visualizador.pid")

Write-Host "Pacientes: $directorioPacientes"
Write-Host "Portal: $env:TFG_PORTAL_URL"
Write-Host "Organizador: $env:TFG_ORGANIZADOR_URL"
Write-Host "Visualizador: $env:TFG_VISUALIZADOR_URL"

# Sin -NoAbrirNavegador: arranca las apps y abre el portal.
# Con -NoAbrirNavegador: arranca las apps pero no abre Chrome.
if (-not $NoAbrirNavegador) {
    Start-Process $env:TFG_PORTAL_URL
}
