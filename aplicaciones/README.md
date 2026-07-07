# Aplicaciones BIS-ICCA

Esta carpeta contiene el sistema ejecutable del TFG:

- `portal_bis_icca`: pantalla inicial.
- `organizador_bis_icca`: crea y edita pacientes y sus sesiones.
- `visualizador_bis_icca`: muestra conjuntamente BIS, DSA e ICCA.
- `iniciar_aplicaciones.ps1`: arranca las tres aplicaciones.
- `detener_aplicaciones.ps1`: detiene las tres aplicaciones.
- `preparar_entorno.ps1`: crea el entorno Python local.

Los pacientes se leen desde la variable `TFG_PACIENTES_DIR`. En local se usa
`datos\pacientes`. En HUBU se usaria la ruta compartida que indique el
hospital, por ejemplo `P:\Pacientes`.

## Primer uso

```powershell
cd "C:\Users\usuario\OneDrive - Universidad de Burgos\Documentos\tfg\aplicaciones"
.\preparar_entorno.ps1
```

Esto crea `aplicaciones\.venv`. Esa carpeta no se sube a GitHub.

## Abrir el sistema en local

```powershell
cd "C:\Users\usuario\OneDrive - Universidad de Burgos\Documentos\tfg\aplicaciones"
.\iniciar_aplicaciones.ps1 -PacientesDir "..\datos\pacientes" -RutaPacientesFija
```

- Portal: <http://127.0.0.1:8040/>
- Visualizador: <http://127.0.0.1:8050/>
- Organizador: <http://127.0.0.1:8060/>

## Despliegue tipo HUBU

Ejemplo orientativo para la VM de aplicacion:

```powershell
.\iniciar_aplicaciones.ps1 `
  -PacientesDir "P:\Pacientes" `
  -RutaPacientesFija `
  -AppHost "0.0.0.0" `
  -PublicHost "10.25.14.80"
```

Con ese ejemplo, los equipos de la intranet abririan:

- Portal: `http://10.25.14.80:8040/`
- Visualizador: `http://10.25.14.80:8050/`
- Organizador: `http://10.25.14.80:8060/`

La IP real, los puertos permitidos y la ruta compartida final los debe confirmar
el personal tecnico del HUBU.

## Detener el sistema

```powershell
.\detener_aplicaciones.ps1
```
