# si algo falla, el script se para
$ErrorActionPreference = "Stop"

# construye la ruta de la carpeta .runtime. 
# Si el script está en ...\tfg\aplicaciones -> $runtime = ...\tfg\aplicaciones\.runtime y se guardan los archivos:
# portal.pid -> un .pid contiene el número del proceso que se arrancó.
# organizador.pid
# visualizador.pid

$runtime = Join-Path $PSScriptRoot ".runtime"

# lista las tres apps. Cada elemento tiene dos datos:
# - Nombre  = nombre para mostrar en pantalla
# - Archivo = archivo donde está guardado su PID
$aplicaciones = @(
    @{ Nombre = "Portal BIS-ICCA"; Archivo = "portal.pid" },
    @{ Nombre = "Organizador BIS-ICCA"; Archivo = "organizador.pid" },
    @{ Nombre = "Visualizador BIS-ICCA"; Archivo = "visualizador.pid" }
)

# para cada aplicación de la lista:
foreach ($aplicacion in $aplicaciones) {

    # calcula dónde está su archivo PID
    $pidFile = Join-Path $runtime $aplicacion.Archivo
    
    # Si no existe el archivo PID, no sabe qué proceso apagar. Escribe un mensaje y paso a la siguiente app.
    if (-not (Test-Path -LiteralPath $pidFile)) {
        Write-Host "$($aplicacion.Nombre): no hay PID registrado."
        continue
    }

    # lee el PID
    $pidGuardado = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
    
    # Si hay un PID guardado, busca si existe un proceso con ese número.
    $proceso = if ($pidGuardado) {
        Get-Process -Id $pidGuardado -ErrorAction SilentlyContinue
    }

    # las detiene y escribe Portal BIS-ICCA detenido.
    if ($proceso) {
        Stop-Process -Id $proceso.Id
        Write-Host "$($aplicacion.Nombre) detenido."
    } 
    # si no lo encuentra: El archivo PID existía, pero el proceso ya murió antes.
    else {
        Write-Host "$($aplicacion.Nombre) ya no estaba en ejecucion."
    }

    # Borra el archivo .pid.
    # Porque ya no sirve. Si no lo borráramos, el sistema podría creer que la app sigue arrancada cuando no lo está.
    Remove-Item -LiteralPath $pidFile -Force
} 
