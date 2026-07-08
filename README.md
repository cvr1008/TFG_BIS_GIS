<p align="center">
  <img src="TFG/img/CabeceraEPS.png" alt="Cabecera EPS" width="420">
  &nbsp;&nbsp;&nbsp;
  <img src="TFG/img/Logo_GIS.png" alt="Logo GIS" width="120">
</p>

# Sistema BIS-ICCA para organización y visualización de pacientes críticos

Este proyecto ha sido posible gracias a una asociación entre la Universidad de Burgos (UBU) y la Unidad de Cuidados Intensivos (UCI) del Hospital Universitario de Burgos (HUBU). Parte de un contexto clínico en el que se trabaja con dos fuentes principales de información: los registros BIS, asociados a la monitorización cerebral mediante índice biespectral, y los registros ICCA, exportados en formato Excel desde el sistema de información clínica. El objetivo general es facilitar la revisión conjunta de estos datos, evitando una exploración manual dispersa en múltiples carpetas y archivos.

La herramienta no sustituye la valoración clínica ni los sistemas hospitalarios originales. Su finalidad es organizar los datos exportados, facilitar su consulta y permitir una visualización integrada del caso.

En este proyecto se han utilizado datos reales de pacientes. El uso de los datos del proyecto fue tramitado y cuenta con la aprobación del CEIm con fecha 2 de julio de 2026.

Este repositorio contiene una aplicación desarrollada en Python/Dash para organizar, integrar y visualizar información clínica procedente de pacientes ingresados en UCI.

## Flujos principales de trabajo

El sistema se organiza en dos flujos principales:

1. Organización de pacientes.
2. Visualización de pacientes.

Ambos flujos comparten una misma ubicación de pacientes, de forma que los datos creados desde el organizador pueden consultarse después desde el visualizador.

## Organización de pacientes

El organizador permite crear una estructura homogénea de carpetas por paciente. A partir de sesiones BIS y, cuando existen, registros ICCA asociados, la aplicación genera una carpeta individual para cada paciente.

La estructura general es:

```text
datos/
`-- pacientes/
    |-- PACIENTE_001/
    |   |-- paciente.json
    |   |-- ICCA/
    |   `-- SESIONES/
    |       |-- SESION_001_...
    |       `-- SESION_002_...
    |-- PACIENTE_002/
    `-- PACIENTE_003/
```

Cada paciente contiene la información necesaria para reconstruir su caso: metadatos, sesiones BIS, registros ICCA y archivos auxiliares generados durante el procesamiento.

Este flujo evita que el usuario tenga que decidir manualmente dónde guardar cada caso, ya que la aplicación trabaja siempre sobre una carpeta de pacientes configurada de forma fija.

## Visualización de pacientes

El visualizador permite seleccionar un paciente ya organizado y consultar sus sesiones BIS. Para cada sesión se muestran distintas representaciones de la información disponible.

Entre los elementos principales se incluyen:

- Matriz DSA.
- Reconstrucción de la matriz de densidad espectral cuando no está disponible directamente.
- Variables BIS, EMG, SEF, MEF y ASYM09.
- Variables clínicas procedentes de ICCA, cuando existen.
- Constantes vitales documentadas.
- Perfusiones y medicación administrada.
- Resumen del caso e informe exportable en PDF.

Uno de los apartados más importantes del proyecto ha sido la reconstrucción de la matriz DSA. A partir de los archivos crudos exportados por el monitor BIS y de la documentación disponible sobre el formato de los registros, se ha implementado un proceso que permite reconstruir la matriz de densidad espectral con una fidelidad suficiente para su consulta visual dentro de la aplicación.

## Integración de datos ICCA

Además de los registros BIS, el sistema integra información clínica procedente de archivos Excel exportados desde ICCA.

Esta integración permite visualizar, junto a la información cerebral, variables clínicas relevantes del paciente, como constantes vitales, análisis puntuales y perfusiones. En el caso de las perfusiones, la aplicación representa la evolución de la dosis o del volumen administrado según la información disponible en los registros.

La visualización de las variables ICCA se ha planteado evitando inventar datos entre mediciones: se muestran las mediciones reales documentadas y, cuando procede, tramos que indican el último valor registrado hasta la siguiente medición.

## Estructura del repositorio

TFG_BIS_GIS/
|-- aplicaciones/
|   |-- portal_bis_icca/
|   |-- organizador_bis_icca/
|   |-- visualizador_bis_icca/
|   |-- requirements.txt
|   |-- abrir_apps.ps1
|   |-- iniciar_aplicaciones.ps1
|   |-- detener_aplicaciones.ps1
|   |-- preparar_entorno.ps1
|   |-- preparar_entorno_offline.ps1
|
|-- datos/
|   `-- pacientes/
|
|-- TFG/
|   `-- memoria, anexos e imágenes del trabajo
|
|-- notebooks/
|   `-- validacion_metodos_dsa_multiregistro
|
|-- preparar_entornos.bat
|-- abrir_aplicaciones.bat
|-- cerrar_aplicaciones.bat
|-- README.md
`-- .gitignore

La carpeta `aplicaciones/` contiene el código fuente del sistema. Dentro de ella se encuentran los tres módulos principales:

- `portal_bis_icca/`: pantalla inicial de acceso, desde la que se puede entrar al organizador o al visualizador.
- `organizador_bis_icca/`: aplicación encargada de crear pacientes, asociar sesiones BIS y vincular registros ICCA cuando están disponibles.
- `visualizador_bis_icca/`: aplicación encargada de consultar pacientes ya organizados, visualizar las sesiones BIS, mostrar las variables clínicas ICCA y generar informes.

El archivo aplicaciones/requirements.txt recoge las dependencias necesarias para ejecutar el sistema completo. Además, organizador_bis_icca/ y visualizador_bis_icca/ conservan cada uno su propio requirements.txt, con las dependencias específicas de esa aplicación, para poder analizar o ejecutar cada una por separado si se desea.

La carpeta aplicaciones/ también incluye varios scripts internos de PowerShell. preparar_entorno.ps1 crea el entorno virtual e instala las dependencias; iniciar_aplicaciones.ps1 arranca el portal, el organizador y el visualizador; detener_aplicaciones.ps1 detiene los procesos iniciados; abrir_apps.ps1 agrupa el arranque completo usando la ruta local de pacientes; y preparar_entorno_offline.ps1 permite preparar el entorno usando paquetes locales si existen o, en caso contrario, instalando desde internet.

La carpeta datos/ contiene la ubicación de trabajo de la aplicación. En concreto, datos/pacientes/ es la carpeta donde se guardan los pacientes creados durante el uso local o de demostración.

La carpeta TFG/ contiene la documentación académica del proyecto, incluyendo memoria, anexos, imágenes y otros materiales utilizados en la redacción del trabajo.

La carpeta notebooks/ contiene el notebook utilizado para documentar y validar la metodología elegida para la reconstrucción de la matriz DSA.
En la raíz del repositorio se incluyen tres archivos .bat pensados para facilitar el uso en Windows. Estos permiten preparar el entorno, abrir la aplicación y detener los servidores sin necesidad de escribir comandos manualmente.

En el repositorio no deben incluirse datos clínicos reales. La carpeta datos/pacientes/ puede estar vacía inicialmente y se irá rellenando al utilizar la aplicación.

## Datos de prueba

Los datos para la visualización se proporcionarán en una memoria USB con una estructura similar a esta:

```text
DATOS/
|-- SESIONES_BIS/
|   |-- BIS_ICCA_1/
|   |-- BIS_ICCA_2/
|   |-- BIS_ICCA_3/
|   `-- sesiones_BIS_sin_icca/
`-- SESIONES_ICCA/
    |-- ICCA_1/
    |-- ICCA_2/
    `-- ICCA_3/
```

Las sesiones de BIS y los excels de variables clínicas están en carpetas separadas con el fin de facilitar la experiencia de uso. Se incluyen sesiones BIS de pacientes cuya estancia en la UCI ha estado monitorizada por el sistema ICCA. Los nombres de las sesiones de esos pacientes llevan incluido el nombre de la carpeta que contiene el excel correspondiente a su estancia.

## Instalación y ejecución local

Para ejecutar la aplicación en un ordenador nuevo, se recomienda seguir estos pasos.

### 1. Descargar el proyecto

El repositorio puede descargarse desde GitHub como archivo ZIP o clonarse mediante Git. Si se descarga como ZIP, es importante extraerlo antes de ejecutar la aplicación.

### 2. Instalar Python

La aplicación se ha probado con Python 3.12.10. Durante la instalación de Python en Windows es importante marcar la opción: `Add python.exe to PATH`.

Esto permite que Windows reconozca el comando `python` desde la terminal y que los scripts de preparación funcionen correctamente.

### 3. Preparar el entorno

Una vez descargado el repositorio, ejecutar:

```text
preparar_entornos.bat
```

Este archivo crea el entorno virtual de Python e instala las dependencias necesarias para ejecutar la aplicación. Este paso solo es necesario la primera vez, o si se borra el entorno virtual.

### 4. Abrir la aplicación

Después de preparar el entorno, ejecutar:

```text
abrir_aplicaciones.bat
```

Este archivo arranca las aplicaciones Dash necesarias y abre el portal principal en el navegador.

### 5. Cerrar la aplicación

Cuando se termine de utilizar la herramienta, ejecutar:

```text
cerrar_aplicaciones.bat
```

Este archivo detiene los servidores de la aplicación. Es posible que el navegador siga abierto, pero la aplicación dejará de ejecutarse en segundo plano.

Esta explicación, junto con el despliegue pensado con máquinas virtuales, se encuentra detallada en los anexos.

## Notas importantes

- La aplicación no incluye datos clínicos reales en el repositorio.
- La carpeta `datos/pacientes` puede estar vacía inicialmente.
- Los pacientes creados desde la aplicación se guardan automáticamente en la ubicación configurada.
- El navegador puede ser Chrome, Edge, Firefox u otro navegador moderno.
- La herramienta está orientada a organización, consulta y apoyo visual de datos exportados, no a la toma directa de decisiones clínicas.

---

Autora: Cristina Velázquez Romano

Tutores: David García-García, Sergio Ossa Echeverri y Rodrigo Albillos Almaraz

Grado en Ingeniería de la Salud - Escuela Politécnica Superior - UBU
