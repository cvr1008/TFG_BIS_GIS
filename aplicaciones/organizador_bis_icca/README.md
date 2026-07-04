# Organizador BIS-ICCA

Aplicacion local para agrupar sesiones BIS y, de forma opcional, registros
ICCA coincidentes en carpetas de paciente.

## Flujo

1. Seleccionar el directorio donde se guardaran los pacientes.
2. Seleccionar uno o varios Excel ICCA ya preparados, si estan disponibles.
3. Anadir una carpeta por cada sesion BIS.
4. Revisar los intervalos y el solapamiento temporal.
5. Crear `PACIENTE_###`.

La pestaña **Pacientes** permite:

- consultar las fuentes y sesiones ya asignadas;
- abrir el Excel ICCA auxiliar de cada sesión;
- añadir o retirar Excel ICCA y sesiones BIS;
- volver a validar los intervalos antes de guardar una edición;
- eliminar un paciente mediante confirmación.

Una fuente ICCA o una sesión BIS ya asignada no puede reutilizarse para crear
otro paciente. Las ediciones se construyen en una carpeta temporal y solo
sustituyen la carpeta anterior cuando terminan correctamente.

Cada sesion queda en una subcarpeta con:

- una copia completa de la carpeta BIS;
- un Excel ICCA auxiliar recortado al intervalo BIS;
- un manifiesto `sesion.json` con procedencia e intervalos.

Los archivos originales no se modifican.

## Ejecucion

```powershell
cd "C:\Users\usuario\OneDrive - Universidad de Burgos\Documentos\tfg\organizador_bis_icca"
python app.py
```

La aplicacion se abre en `http://127.0.0.1:8060/`.
