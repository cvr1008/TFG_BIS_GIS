# TFG BIS-ICCA

Sistema desarrollado en Python/Dash para organizar, consultar y visualizar
datos procedentes de monitorizacion BIS e informacion clinica ICCA en pacientes
neurocriticos.

El proyecto se estructura como una herramienta web local, accesible desde un
navegador, con un portal inicial que permite entrar en los dos flujos principales
de trabajo: organizacion de pacientes y visualizacion de pacientes.

## Descripcion general

La aplicacion permite trabajar con sesiones BIS exportadas desde el monitor y,
cuando existen registros ICCA asociados, integrarlos en el mismo caso clinico.
El objetivo es centralizar la informacion de cada paciente en una estructura de
carpetas reproducible, evitando modificar los archivos originales.

El sistema no utiliza una base de datos relacional. Los datos se almacenan en
carpetas y archivos:

```text
datos/
└── pacientes/
    ├── PACIENTE_001/
    ├── PACIENTE_002/
    └── ...
```

La carpeta `datos/pacientes/` contiene datos de trabajo o datos clinicos y no
debe subirse a GitHub.

## Flujos de trabajo

### 1. Organizacion de pacientes

El modulo `organizador_bis_icca` permite crear y editar carpetas de paciente.
Desde esta aplicacion se pueden:

- seleccionar archivos Excel ICCA ya preparados;
- seleccionar una o varias carpetas BIS;
- analizar los intervalos temporales de las sesiones;
- comprobar solapamientos entre sesiones;
- crear la carpeta final del paciente;
- editar pacientes ya creados;
- asociar cada sesion BIS con su Excel ICCA auxiliar cuando exista coincidencia.

Cada paciente queda organizado en una carpeta `PACIENTE_###`, que contiene sus
sesiones, registros auxiliares y manifiestos JSON.

### 2. Visualizacion de pacientes

El modulo `visualizador_bis_icca` permite seleccionar un paciente ya organizado
y consultar sus sesiones. Desde esta aplicacion se pueden visualizar:

- matriz DSA bilateral;
- indices BIS y EMG;
- asimetria bilateral;
- variables clinicas procedentes de ICCA;
- perfusiones y administracion acumulada;
- tarjetas resumen del intervalo seleccionado;
- informe PDF imprimible del caso visualizado.

El usuario accede a ambos flujos desde el portal principal `portal_bis_icca`.

## Reconstruccion de la DSA

Cuando el registro lo permite, la aplicacion reconstruye la matriz de densidad
espectral bilateral a partir de los datos BIS disponibles. La visualizacion DSA
incluye informacion de ambos hemisferios y permite consultar el intervalo de
registro de forma interactiva.

La reconstruccion y representacion se realiza sin modificar los archivos BIS
originales. Los resultados se calculan en la aplicacion y se muestran en el
visualizador.

## Integracion de datos ICCA

Los registros ICCA se incorporan como archivos Excel preparados. La aplicacion
extrae y representa las variables clinicas relevantes dentro del intervalo de
cada sesion BIS.

La integracion ICCA incluye:

- constantes vitales;
- analisis clinicos;
- perfusiones;
- dosis documentadas;
- volumen o dosis acumulada cuando es posible calcularla;
- resumen del intervalo seleccionado.

La aplicacion evita inventar datos intermedios: en las constantes clinicas se
muestran mediciones reales y tramos que representan el ultimo valor documentado
hasta la siguiente medicion.

## CEIm

La tramitacion del proyecto ante el CEIm se realizo el 30 de junio de 2026. Los
datos clinicos no forman parte del repositorio y deben mantenerse fuera de
GitHub.

## Estructura del repositorio

```text
TFG_BIS_GIS/
├── aplicaciones/
│   ├── portal_bis_icca/
│   ├── organizador_bis_icca/
│   ├── visualizador_bis_icca/
│   ├── requirements.txt
│   ├── preparar_entorno.ps1
│   ├── preparar_entorno_offline.ps1
│   ├── iniciar_aplicaciones.ps1
│   └── detener_aplicaciones.ps1
├── datos/
│   └── pacientes/
├── TFG/
│   ├── img/
│   ├── qmd/
│   ├── memoria.qmd
│   └── anexos.qmd
├── PREPARAR_DEMO_DEFENSA.bat
├── ABRIR_DEMO_DEFENSA.bat
├── CERRAR_DEMO_DEFENSA.bat
├── README.md
└── .gitignore
```

## Requisitos

- Windows 10 o superior.
- Python 3.10-3.12. Se recomienda Python 3.12.10 en Windows.
- Navegador web: Chrome, Edge o Firefox.
- Conexion a internet durante la primera instalacion de dependencias, salvo que
  se utilice una carpeta `wheelhouse` preparada previamente.

Durante la instalacion de Python en Windows, marcar la opcion:

```text
Add python.exe to PATH
```

Para comprobar que Python esta disponible:

```cmd
python --version
```

## Puesta en marcha rapida

Desde la carpeta principal del repositorio:

```cmd
PREPARAR_DEMO_DEFENSA.bat
```

Este paso crea el entorno virtual:

```text
aplicaciones/.venv/
```

e instala las dependencias necesarias.

Despues, para abrir la aplicacion:

```cmd
ABRIR_DEMO_DEFENSA.bat
```

El portal principal se abrira en:

```text
http://127.0.0.1:8040/
```

Para cerrar las aplicaciones:

```cmd
CERRAR_DEMO_DEFENSA.bat
```

## Puesta en marcha manual

Tambien se puede preparar y arrancar el sistema desde PowerShell:

```powershell
cd aplicaciones
.\preparar_entorno.ps1
.\iniciar_aplicaciones.ps1 -RutaPacientesFija
```

Direcciones locales:

```text
Portal:        http://127.0.0.1:8040/
Visualizador:  http://127.0.0.1:8050/
Organizador:   http://127.0.0.1:8060/
```

Para detener las aplicaciones:

```powershell
.\detener_aplicaciones.ps1
```

## Ubicacion de pacientes

Por defecto, la aplicacion guarda y busca pacientes en:

```text
datos/pacientes/
```

Si otra persona descarga el repositorio en otra ruta, sus pacientes se guardaran
en la carpeta `datos/pacientes/` de su propia copia del proyecto.

Ejemplo:

```text
C:\Users\NombreUsuario\Downloads\TFG_BIS_GIS\datos\pacientes
```

En un despliegue tipo hospitalario, esta ruta puede sustituirse por una unidad
de red compartida, por ejemplo:

```text
P:\Pacientes
```

## Notas para GitHub

Subir al repositorio:

- codigo de `aplicaciones/`;
- scripts `.bat` y `.ps1`;
- documentacion del TFG;
- `README.md`;
- `.gitignore`;
- estructura vacia o documentada de `datos/`.

No subir:

- `aplicaciones/.venv/`;
- `aplicaciones/.runtime/`;
- `datos/pacientes/` con datos reales;
- archivos temporales;
- salidas generadas que no sean necesarias;
- documentos clinicos o administrativos sensibles.

## Arquitectura HUBU

La aplicacion puede ejecutarse en local para pruebas y demostracion. Ademas, se
ha planteado una arquitectura con maquinas virtuales para simular un posible
despliegue en intranet hospitalaria:

- una VM Windows para ejecutar la aplicacion Dash/Python;
- una VM Ubuntu Server para almacenar la carpeta comun de pacientes;
- comparticion Samba/SMB para montar la carpeta de pacientes como unidad de red;
- ruta fija de trabajo, por ejemplo `P:\Pacientes`.

El codigo de la aplicacion no cambia entre local y despliegue tipo HUBU. Cambia
la ruta de pacientes configurada al arrancar.
