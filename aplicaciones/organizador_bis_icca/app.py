from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path 

from dash import ALL, Dash, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.pacientes import (
    actualizar_paciente,
    analizar_asignacion,
    crear_paciente,
    eliminar_paciente,
    listar_pacientes,
    obtener_fuentes_paciente,
    siguiente_paciente,
)
from src.intervalos import descubrir_icca_en_carpeta, descubrir_sesiones_bis_en_carpeta


# aplicación Dash del organizador

# elegir carpeta de pacientes
BASE_DIR = Path(__file__).resolve().parent


def _directorio_pacientes_predeterminado():
    """
    Función que decide dónde están los pacientes
    Busca en este orden:
        1. TFG_PACIENTES_DIR
        2. datos\pacientes
    """
    # calcula la carpeta raíz del proyecto -> Si BASE_DIR es ...\tfg\aplicaciones\organizador_bis_icca
    # BASE_DIR.parent.parent = ...\tfg
    raiz_proyecto = BASE_DIR.parent.parent

    """
    Crea una lista de posibles carpetas donde podrían estar los pacientes.
     - os.environ.get("TFG_PACIENTES_DIR"): Busca una variable de entorno llamada TFG_PACIENTES_DIR. Si existe, usa esa ruta.
     - raiz_proyecto / "datos" / "pacientes": construye la ruta ...\tfg\datos\pacientes (carpeta final para pacientes)
    """
    candidatos = [
        os.environ.get("TFG_PACIENTES_DIR"),
        raiz_proyecto / "datos" / "pacientes",
    ]
    # Mira cada posible carpeta, una por una.
    for candidato in candidatos:

        # comprueba si hay algo en candidato o está vacío
        # Si el candidato no está vacío y además existe como carpeta, devuelve esa ruta.
        if candidato and Path(candidato).expanduser().is_dir():
            return Path(candidato).expanduser().resolve()
        
    # Si ninguna carpeta existe, devuelve la ruta nueva datos\pacientes. Porque después otra parte del código puede crearla.
    return (raiz_proyecto / "datos" / "pacientes").resolve()


# Guarda esa ruta elegida.
DIRECTORIO_PREDETERMINADO = _directorio_pacientes_predeterminado()


def _env_bool(nombre, valor_por_defecto=False):
    """
    Lee una variable de entorno y la interpreta como un valor booleano.

    Esta función se usa para activar o desactivar opciones de configuración desde fuera del código. 
    Permite indicar si la aplicación debe usar una ruta fija de pacientes sin modificar el archivo Python.

    Parámetros:
     - nombre : str
        Nombre de la variable de entorno que se quiere leer.
        Ejemplo: "TFG_RUTA_PACIENTES_FIJA".

     - valor_por_defecto : bool, optional
        Valor que se devuelve si la variable de entorno no existe.
        Por defecto es False.

    Devuelve:
     - bool
        True si la variable de entorno existe y contiene alguno de estos valores:
        "1", "true", "yes", "si" o "s".

        False si contiene otro valor.

        Si la variable no existe, devuelve valor_por_defecto.

    """
    valor = os.environ.get(nombre)
    if valor is None:
        return valor_por_defecto
    return valor.strip().casefold() in {"1", "true", "yes", "si", "s"}


def _env_int(nombre, valor_por_defecto):
    """
    Lee una variable de entorno y la interpreta como un número entero.

    Esta función se usa para configurar valores numéricos desde fuera del código, especialmente puertos de las aplicaciones Dash. 
    Si la variable no existe o no contiene un número válido, se usa un valor por defecto.

    Parámetros:
     - nombre : str
        Nombre de la variable de entorno que se quiere leer.
        Ejemplo: "TFG_ORGANIZADOR_PORT".

     - valor_por_defecto : int
        Número que se devuelve si la variable de entorno no existe o no se puede
        convertir correctamente a entero.

    Devuelve:
     - int
        Valor entero leído desde la variable de entorno, o valor_por_defecto si no existe o es inválido.
    
    Ejemplo:
     - TFG_ORGANIZADOR_PORT=9000
     - Si existe: 
        _env_int("TFG_ORGANIZADOR_PORT", 8060) devuelve 9000.

     - Si no existe:
        _env_int("TFG_ORGANIZADOR_PORT", 8060) devuelve 8060.

     - Si existe pero está mal: TFG_ORGANIZADOR_PORT=abc
        _env_int("TFG_ORGANIZADOR_PORT", 8060) devuelve 8060.
    """
    try:
        return int(os.environ.get(nombre, valor_por_defecto))
    except (TypeError, ValueError):
        return valor_por_defecto


# Pregunta si se prefiere ocultar el selector de carpeta de pacientes (Si vale True, la app no deja al médico elegir dónde guardar pacientes)
RUTA_PACIENTES_FIJA = _env_bool("TFG_RUTA_PACIENTES_FIJA")

# decide dónde se abre la app
HOST_DASH = os.environ.get("TFG_DASH_HOST", "127.0.0.1")
PUERTO_ORGANIZADOR = _env_int("TFG_ORGANIZADOR_PORT", 8060)

# colores para la interfaz
AZUL = "#1f4e78"
AZUL_CLARO = "#dbeaf7"
FONDO = "#f5f7fa"
BORDE = "#cad5df"
VERDE = "#e7f5ea"
AMARILLO = "#fff4cf"
ROJO = "#fde8e7"


def _ejecutar_dialogo(codigo, argumento=""):
    """
    Esta función ejecuta una ventana de selección de archivos/carpetas.
    """
    opciones = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "check": False,
    }
    if sys.platform == "win32":
        opciones["creationflags"] = subprocess.CREATE_NO_WINDOW
    resultado = subprocess.run([sys.executable, "-c", codigo, argumento], **opciones)
    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.strip() or "No se pudo abrir el selector.")
    salida = resultado.stdout.strip().splitlines()
    return json.loads(salida[-1]) if salida else None


def _seleccionar_excel(ruta_inicial=""):
    """
    Abre una ventana para elegir Excel ICCA.
    """
    codigo = r'''
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

inicial = Path(sys.argv[1]).expanduser() if sys.argv[1] else Path.home()
if inicial.is_file():
    inicial = inicial.parent
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
rutas = filedialog.askopenfilenames(
    parent=root,
    title="Selecciona uno o varios Excel ICCA",
    initialdir=str(inicial),
    filetypes=[("Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")],
)
root.destroy()
print(json.dumps(list(rutas), ensure_ascii=False))
'''
    return _ejecutar_dialogo(codigo, ruta_inicial) or []


def _seleccionar_carpeta(titulo, ruta_inicial=""):
    """
    Abre una ventana para elegir una carpeta BIS o una carpeta con ICCA.
    Selecciona archivos de entrada, no la carpeta final de pacientes
    """
    codigo = rf'''
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

inicial = Path(sys.argv[1]).expanduser() if sys.argv[1] else Path.home()
if inicial.is_file():
    inicial = inicial.parent
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
ruta = filedialog.askdirectory(
    parent=root,
    title={titulo!r},
    initialdir=str(inicial),
    mustexist=True,
)
root.destroy()
print(json.dumps(ruta, ensure_ascii=False))
'''
    return _ejecutar_dialogo(codigo, ruta_inicial) or ""


def _opciones(rutas):
    return [
        {"label": f"{Path(ruta).name}  |  {ruta}", "value": ruta}
        for ruta in rutas
    ]


def _tarjetas_seleccion(rutas, tipo, etiqueta, mensaje_vacio):
    """
    Imprime en pantalla las cosas seleccionadas.
    """
    if not rutas:
        return html.Div(
            mensaje_vacio,
            className="seleccion-vacia",
        )
    return [
        html.Div(
            [
                html.Div(
                    [
                        html.Strong(Path(ruta).name),
                        html.Small(str(ruta)),
                    ],
                    className="seleccion-contenido",
                ),
                html.Button(
                    "×",
                    id={"type": tipo, "index": ruta},
                    className="boton-quitar",
                    title=f"Quitar {Path(ruta).name}",
                    **{"aria-label": f"Quitar {Path(ruta).name}"},
                ),
            ],
            className="seleccion-tarjeta",
        )
        for ruta in rutas
    ]


def _formatear_fecha(valor):
    if not valor:
        return "Sin fecha"
    return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M:%S")


def _formatear_duracion(segundos):
    segundos = int(segundos or 0)
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    partes = []
    if dias:
        partes.append(f"{dias} d")
    if horas:
        partes.append(f"{horas} h")
    partes.append(f"{minutos} min")
    return " ".join(partes)


def _formatear_bytes(numero):
    valor = float(numero or 0)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidad == "TB":
            return f"{valor:.1f} {unidad}"
        valor /= 1024


def _buscar_paciente(directorio, paciente_id):
    return next(
        (
            item
            for item in listar_pacientes(directorio or DIRECTORIO_PREDETERMINADO)
            if item["paciente_id"] == paciente_id
        ),
        None,
    )


def _tarjeta_icca(registro):
    """
    Imprime la información de ICCA correctamente en la pantalla.
    """
    return html.Div(
        [
            html.Strong(registro["nombre"]),
            html.Div(f"Entrada: {_formatear_fecha(registro['inicio'])}"),
            html.Div(f"Salida: {_formatear_fecha(registro['fin'])}"),
            html.Div(f"Duración: {_formatear_duracion(registro['duracion_s'])}"),
            html.Small(registro["ruta"]),
        ],
        className="tarjeta",
    )


def _tarjeta_bis(sesion):
    """
    Imprime la información de BIS correctamente en la pantalla.
    """
    solapamientos = [item for item in sesion["solapamientos"] if item["segundos"] > 0]
    cobertura_completa = any(item["completo"] for item in solapamientos)
    compatible = bool(solapamientos)
    color = VERDE if cobertura_completa else (AMARILLO if compatible else ROJO)
    if cobertura_completa:
        estado = "ICCA cubre toda la sesión"
    elif compatible:
        mejor = max(item["cobertura_bis"] for item in solapamientos)
        estado = f"Cobertura ICCA parcial: {mejor:.1%}"
    else:
        estado = "Sin información ICCA coincidente"

    return html.Div(
        [
            html.Div(
                [
                    html.Strong(f"{sesion['sesion_id']} ({sesion['modo']})"),
                    html.Span(estado, className="estado", style={"background": color}),
                ],
                className="fila-separada",
            ),
            html.Div(f"Inicio BIS: {_formatear_fecha(sesion['inicio'])}"),
            html.Div(f"Fin BIS: {_formatear_fecha(sesion['fin'])}"),
            html.Div(
                f"Duración: {_formatear_duracion(sesion['duracion_s'])} · "
                f"{_formatear_bytes(sesion['bytes'])}"
            ),
            html.Small(sesion["ruta"]),
        ],
        className="tarjeta",
    )


def _vista_analisis(analisis):
    """
    Muestra el resultado de comprobar si las sesiones BIS y los ICCA coinciden en tiempo. Cosas como si:
     - ICCA cubre toda la sesión
     - Cobertura parcial
     - Sin información ICCA coincidente
    """
    return html.Div(
        [
            html.H3("Registros ICCA"),
            html.Div(
                [_tarjeta_icca(registro) for registro in analisis["icca"]]
                or [html.Div("No se han seleccionado registros ICCA.")],
                className="rejilla-tarjetas",
            ),
            html.H3("Sesiones BIS", style={"marginTop": "20px"}),
            *[_tarjeta_bis(sesion) for sesion in analisis["bis"]],
            html.Div(
                "La selección es válida. Las sesiones sin solapamiento ICCA se "
                "guardarán y podrán visualizarse solo con sus datos BIS.",
                className="mensaje-ok",
            ),
        ]
    )


def _detalle_paciente(datos):
    carpeta = Path(datos["carpeta"])
    registros_icca = []
    for registro in datos.get("icca", []):
        registros_icca.append(
            html.Div(
                [
                    html.Strong(registro.get("nombre", "Excel ICCA")),
                    html.Div(
                        f"{_formatear_fecha(registro.get('inicio'))} - "
                        f"{_formatear_fecha(registro.get('fin'))}"
                    ),
                ],
                className="fuente",
            )
        )

    sesiones = []
    for sesion in datos.get("sesiones", []):
        excel_relativo = sesion.get("excel_icca_auxiliar")
        excel = (carpeta / excel_relativo).resolve() if excel_relativo else None
        detalle_icca = (
            html.Div(
                [
                    html.Span("ICCA auxiliar: "),
                    html.Button(
                        excel.name,
                        id={"type": "abrir-excel", "index": str(excel)},
                        className="boton-enlace",
                        title="Abrir el Excel auxiliar",
                    ),
                ]
            )
            if excel is not None
            else html.Div("Sin información ICCA para esta sesión.")
        )
        sesiones.append(
            html.Div(
                [
                    html.Strong(sesion["nombre_carpeta"]),
                    html.Div(
                        f"BIS: {_formatear_fecha(sesion['inicio_bis'])} - "
                        f"{_formatear_fecha(sesion['fin_bis'])}"
                    ),
                    detalle_icca,
                    html.Small(f"Carpeta BIS: {sesion['carpeta_bis']}"),
                ],
                className="sesion",
            )
        )

    return html.Div(
        [
            html.H3(datos["paciente_id"], style={"marginBottom": "4px"}),
            html.Div(f"Carpeta: {datos['carpeta']}"),
            html.Div(f"Creado: {datos.get('creado', '')}"),
            html.H4("Registros ICCA", style={"marginTop": "18px"}),
            *(registros_icca or [html.Div("No hay registros ICCA asignados.")]),
            html.H4("Sesiones", style={"marginTop": "18px"}),
            *(sesiones or [html.Div("No hay sesiones registradas.")]),
        ]
    )

# ------------------------ Paneles de la interfaz -------------------------------
def _panel_nuevo_paciente():
    # Crear la pestaña de Añadir paciente
    return html.Div(
        [
            html.H2("Añadir paciente"),
            html.P(
                "Selecciona uno o varios Excel ICCA ya preparados, si están "
                "disponibles. También puedes crear un paciente solo con sesiones BIS."
            ),

            # Botón de Añadir Excel ICCA
            html.Button("Añadir Excel ICCA", id="anadir-icca", className="boton-secundario"),
            # Botón de Añadir carpeta ICCA
            html.Button(
                "Anadir carpeta ICCA",
                id="anadir-carpeta-icca",
                className="boton-secundario",
                style={"marginLeft": "8px"},
            ),
            dcc.Dropdown(
                id="lista-icca",
                multi=True,
                placeholder="Todavía no se ha seleccionado ningún Excel ICCA",
                style={"display": "none"},
            ),
            html.Div(id="selecciones-icca", className="lista-selecciones"),
            html.P(
                "Selecciona una carpeta por cada sesión BIS.",
                style={"marginTop": "20px"},
            ),
            # Añadir carpeta BIS
            html.Button("Añadir carpeta BIS", id="anadir-bis", className="boton-secundario"),
            # Añadir carpeta madre BIS
            html.Button(
                "Anadir carpeta madre BIS",
                id="anadir-carpeta-madre-bis",
                className="boton-secundario",
                style={"marginLeft": "8px"},
            ),
            dcc.Dropdown(
                id="lista-bis",
                multi=True,
                placeholder="Todavía no se ha seleccionado ninguna sesión BIS",
                style={"display": "none"},
            ),
            html.Div(id="selecciones-bis", className="lista-selecciones"),
            # Botón Analizar intervalos
            html.Button(
                "Analizar intervalos",
                id="analizar",
                className="boton-principal",
                style={"marginTop": "22px"},
            ),
            dcc.Loading(html.Div(id="resultado-analisis", style={"marginTop": "18px"})),
            # Botón Crear carpeta del paciente
            html.Button(
                "Crear carpeta del paciente",
                id="crear-paciente",
                disabled=True,
                className="boton-principal",
                style={"marginTop": "18px"},
            ),
            dcc.Loading(html.Div(id="estado-creacion", style={"marginTop": "14px"})),
            dcc.Interval(id="limpiar-estado-creacion", interval=4500, disabled=True),
        ],
        className="panel",
    )


def _panel_pacientes():
    # Crea la pestaña de Pacientes creados
    return html.Div(
        [
            # aquí se pueden ver los pacientes ya creados -> inspección de los archivos que contienen
            html.H2("Pacientes creados"),
            dcc.Dropdown(
                id="selector-paciente",
                placeholder="Selecciona un paciente",
                clearable=False,
            ),
            html.Div(id="detalle-paciente", style={"marginTop": "16px"}),
            html.Div(id="notificacion-abrir", style={"marginTop": "10px"}),
            dcc.Interval(id="limpiar-notificacion-abrir", interval=3500, disabled=True),
            html.Details(
                [
                    # aquí se pueden editar asignaciones
                    html.Summary("Editar asignaciones"),
                    html.Div(
                        [
                            html.P(
                                "Quita una fuente incorrecta o añade otra. Al guardar se "
                                "recalculan los intervalos y los Excel auxiliares."
                            ),
                            html.Label("Excel ICCA", className="etiqueta"),
                            
                            # añadir/quitar ICCA
                            html.Button(
                                "Añadir Excel ICCA",
                                id="editar-anadir-icca",
                                className="boton-secundario",
                            ),
                            html.Button(
                                "Anadir carpeta ICCA",
                                id="editar-anadir-carpeta-icca",
                                className="boton-secundario",
                                style={"marginLeft": "8px"},
                            ),
                            dcc.Dropdown(
                                id="editar-lista-icca",
                                multi=True,
                                style={"display": "none"},
                            ),
                            html.Div(
                                id="editar-selecciones-icca",
                                className="lista-selecciones",
                            ),
                            html.Label("Sesiones BIS", className="etiqueta"),
                            
                            # añadir/quitar BIS
                            html.Button(
                                "Añadir carpeta BIS",
                                id="editar-anadir-bis",
                                className="boton-secundario",
                            ),
                            html.Button(
                                "Anadir carpeta madre BIS",
                                id="editar-anadir-carpeta-madre-bis",
                                className="boton-secundario",
                                style={"marginLeft": "8px"},
                            ),
                            dcc.Dropdown(
                                id="editar-lista-bis",
                                multi=True,
                                style={"display": "none"},
                            ),
                            html.Div(
                                id="editar-selecciones-bis",
                                className="lista-selecciones",
                            ),

                            # análisis, aceptación y guardado de los cambios
                            html.Div(
                                [
                                    html.Button(
                                        "Comprobar cambios",
                                        id="editar-analizar",
                                        className="boton-secundario",
                                    ),
                                    html.Button(
                                        "Guardar cambios",
                                        id="guardar-cambios",
                                        disabled=True,
                                        className="boton-principal",
                                    ),

                                    # eliminar paciente
                                    html.Button(
                                        "Eliminar paciente",
                                        id="solicitar-eliminar",
                                        className="boton-peligro",
                                    ),
                                ],
                                className="acciones",
                            ),
                            dcc.Loading(
                                html.Div(id="resultado-edicion", style={"marginTop": "16px"})
                            ),
                            dcc.Loading(
                                html.Div(id="estado-edicion", style={"marginTop": "12px"})
                            ),
                            dcc.Interval(
                                id="limpiar-estado-edicion",
                                interval=4500,
                                disabled=True,
                            ),
                        ],
                        className="contenido-edicion",
                    ),
                ],
                className="desplegable-edicion",
            ),
            dcc.ConfirmDialog(
                id="confirmar-eliminacion",
                message="Se eliminará la carpeta completa de este paciente. ¿Deseas continuar?",
            ),
        ],
        className="panel",
    )

# Crear La App Dash. 
# suppress_callback_exceptions=True permite que algunos componentes existan dentro de pestañas o partes dinámicas sin que Dash se queje al arrancar.
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Organizador BIS-ICCA"


# Define la pantalla principal.
app.layout = html.Div(
    [
        dcc.Store(id="actualizacion-creacion", data=0),
        dcc.Store(id="actualizacion-gestion", data=0),
        html.Div(
            # configuración de la cabecera
            [
                html.H1("Organizador de pacientes BIS-ICCA", style={"margin": 0}),
                html.P(
                    "Agrupa sesiones BIS por paciente y, cuando existe ICCA "
                    "coincidente, genera un Excel auxiliar por sesión.",
                    style={"marginBottom": 0},
                ),
            ],
            className="cabecera",
        ),
        html.Div(
            # configuración de la ubicación de pacientes
            [
                html.Div(
                    [
                        html.H2("Ubicación de pacientes"),
                        html.Div(
                            [
                                dcc.Input(
                                    id="directorio-pacientes",
                                    value=str(DIRECTORIO_PREDETERMINADO),
                                    type="text",
                                    style=(
                                        {"display": "none"}
                                        if RUTA_PACIENTES_FIJA
                                        else {"flex": 1, "padding": "10px"}
                                    ),
                                ),
                                html.Button(
                                    "Examinar",
                                    id="examinar-directorio",
                                    className="boton-secundario",
                                    style={"display": "none"} if RUTA_PACIENTES_FIJA else None,
                                ),
                            ],
                            className="fila",
                        ),
                        html.Div(
                            [
                                html.Strong("Ruta configurada"),
                                html.Code(str(DIRECTORIO_PREDETERMINADO)),
                            ],
                            className="ruta-fija",
                        )
                        # Si está activado el modo ruta fija, oculta el input de carpeta.
                        if RUTA_PACIENTES_FIJA
                        else None,
                        # modo local normal: puedes ver/elegir carpeta de pacientes
                        # modo HUBU: no eliges carpeta y la app usa la ruta configurada
                        html.Div(id="siguiente-paciente", style={"marginTop": "10px", "fontWeight": "bold"}),
                    ],
                    className="panel",
                ),

                # pestaña Añadir paciente
                dcc.Tabs(
                    id="pestanas",
                    value="nuevo",
                    children=[
                        dcc.Tab(label="Añadir paciente", value="nuevo", children=[_panel_nuevo_paciente()]),
                        dcc.Tab(label="Pacientes", value="pacientes", children=[_panel_pacientes()]),
                    ],
                ),
            ],
            className="contenedor",
        ),
    ],
    style={"background": FONDO, "minHeight": "100vh", "fontFamily": "Arial, sans-serif"},
)

# estilo visual de la página
app.index_string = f"""
<!DOCTYPE html>
<html>
  <head>
    {{%metas%}}
    <title>{{%title%}}</title>
    {{%favicon%}}
    {{%css%}}
    <style>
      body {{ margin: 0; background: {FONDO}; }}
      .cabecera {{ background: {AZUL}; color: white; padding: 24px 30px; }}
      .contenedor {{ max-width: 1250px; margin: 0 auto; padding: 24px; }}
      .panel {{ background: white; border: 1px solid {BORDE}; border-radius: 10px; padding: 22px; margin: 18px 0; }}
      .fila {{ display: flex; gap: 10px; }}
      .ruta-fija {{ display: grid; gap: 6px; background: #f7f9fb; border: 1px solid {BORDE}; border-radius: 8px; padding: 12px; }}
      .ruta-fija code {{ overflow-wrap: anywhere; color: #173b59; }}
      .fila-separada {{ display: flex; justify-content: space-between; gap: 12px; }}
      .rejilla-tarjetas {{ display: flex; gap: 10px; flex-wrap: wrap; }}
      .tarjeta {{ border: 1px solid {BORDE}; border-radius: 8px; padding: 12px; background: white; min-width: 310px; margin-bottom: 10px; }}
      .estado {{ padding: 4px 9px; border-radius: 12px; font-size: 12px; }}
      .sesion {{ border-left: 4px solid {AZUL}; background: #f9fbfc; padding: 12px 14px; margin-bottom: 9px; }}
      .fuente {{ background: #f9fbfc; border: 1px solid {BORDE}; padding: 10px 12px; margin-bottom: 7px; }}
      .etiqueta {{ display: block; font-weight: bold; margin: 18px 0 8px; }}
      .lista-selecciones {{ display: grid; gap: 8px; margin-top: 10px; }}
      .seleccion-tarjeta {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid {BORDE}; border-radius: 8px; background: #f9fbfc; padding: 10px 12px; }}
      .seleccion-contenido {{ min-width: 0; }}
      .seleccion-contenido small {{ margin-top: 3px; }}
      .seleccion-vacia {{ color: #677581; border: 1px dashed {BORDE}; border-radius: 8px; padding: 11px 12px; }}
      .boton-quitar {{ flex: 0 0 auto; width: 32px; height: 32px; padding: 0; border: 1px solid {BORDE}; border-radius: 50%; background: white; color: #7b2d28; font-size: 22px; line-height: 28px; }}
      .boton-quitar:hover {{ background: {ROJO}; border-color: #d5a3a0; }}
      .desplegable-edicion {{ border: 1px solid {BORDE}; border-radius: 9px; margin-top: 26px; background: #f9fbfc; }}
      .desplegable-edicion summary {{ cursor: pointer; color: {AZUL}; font-weight: 700; padding: 14px 16px; }}
      .desplegable-edicion[open] summary {{ border-bottom: 1px solid {BORDE}; }}
      .contenido-edicion {{ padding: 2px 16px 18px; }}
      .acciones {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 22px; }}
      .mensaje-ok {{ background: {VERDE}; padding: 12px; margin-top: 12px; }}
      .mensaje-error {{ background: {ROJO}; padding: 12px; }}
      button {{ border: 0; border-radius: 6px; padding: 10px 15px; cursor: pointer; font-weight: 600; }}
      button:disabled {{ cursor: not-allowed; opacity: .55; }}
      .boton-principal {{ background: {AZUL}; color: white; }}
      .boton-secundario {{ background: {AZUL_CLARO}; color: #173b59; }}
      .boton-peligro {{ background: #a83b34; color: white; }}
      .boton-enlace {{ background: none; color: {AZUL}; padding: 0; text-decoration: underline; }}
      small {{ display: block; color: #5d6974; margin-top: 6px; overflow-wrap: anywhere; }}
    </style>
  </head>
  <body>
    {{%app_entry%}}
    <footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>
  </body>
</html>
"""

# --------------------------- Callbacks: Cuando el usuario haga algo en la interfaz, ejecuta esta función --------------------------------
@callback(
    Output("directorio-pacientes", "value"),
    Input("examinar-directorio", "n_clicks"),
    State("directorio-pacientes", "value"),
    prevent_initial_call=True,
)
def examinar_directorio(_n_clicks, actual):
    try:
        return _seleccionar_carpeta("Selecciona la carpeta donde guardar los pacientes", actual) or no_update
    except Exception:
        return no_update


@callback(
    Output("lista-icca", "options"),
    Output("lista-icca", "value"),
    Input("anadir-icca", "n_clicks"),
    Input("anadir-carpeta-icca", "n_clicks"),
    State("lista-icca", "value"),
    prevent_initial_call=True,
)
# Se ejecuta cuando pulsas: Añadir Excel ICCA
def anadir_excel_icca(_n_clicks, _n_clicks_carpeta, valores_actuales):
    existentes = list(valores_actuales or [])
    try:
        if ctx.triggered_id == "anadir-carpeta-icca":
            carpeta = _seleccionar_carpeta(
                "Selecciona una carpeta con Excel ICCA",
                existentes[-1] if existentes else "",
            )
            nuevos = descubrir_icca_en_carpeta(carpeta) if carpeta else []
        else:
            nuevos = _seleccionar_excel(existentes[-1] if existentes else "")
    except Exception:
        return no_update, no_update
    rutas = list(dict.fromkeys(existentes + nuevos))
    return _opciones(rutas), rutas


@callback(Output("selecciones-icca", "children"), Input("lista-icca", "value"))
def mostrar_selecciones_icca(rutas):
    return _tarjetas_seleccion(
        rutas,
        "quitar-icca",
        "Excel ICCA",
        "No hay Excel ICCA seleccionados.",
    )


@callback(
    Output("lista-icca", "options", allow_duplicate=True),
    Output("lista-icca", "value", allow_duplicate=True),
    Input({"type": "quitar-icca", "index": ALL}, "n_clicks"),
    State("lista-icca", "value"),
    prevent_initial_call=True,
)
def quitar_excel_icca(n_clicks, rutas):
    if not any(n_clicks or []) or not isinstance(ctx.triggered_id, dict):
        raise PreventUpdate
    restantes = [ruta for ruta in (rutas or []) if ruta != ctx.triggered_id["index"]]
    return _opciones(restantes), restantes


@callback(
    Output("lista-bis", "options"),
    Output("lista-bis", "value"),
    Input("anadir-bis", "n_clicks"),
    Input("anadir-carpeta-madre-bis", "n_clicks"),
    State("lista-bis", "value"),
    prevent_initial_call=True,
)
def anadir_carpeta_bis(_n_clicks, _n_clicks_carpeta, valores_actuales):
    existentes = list(valores_actuales or [])
    inicial = str(Path(existentes[-1]).parent) if existentes else ""
    try:
        nueva = _seleccionar_carpeta("Selecciona una carpeta con una sesión BIS", inicial)
        if ctx.triggered_id == "anadir-carpeta-madre-bis":
            nuevas = descubrir_sesiones_bis_en_carpeta(nueva) if nueva else []
        else:
            nuevas = [nueva] if nueva else []
    except Exception:
        return no_update, no_update
    rutas = list(dict.fromkeys(existentes + nuevas))
    return _opciones(rutas), rutas


@callback(Output("selecciones-bis", "children"), Input("lista-bis", "value"))
def mostrar_selecciones_bis(rutas):
    return _tarjetas_seleccion(
        rutas,
        "quitar-bis",
        "sesión BIS",
        "No hay sesiones BIS seleccionadas.",
    )


@callback(
    Output("lista-bis", "options", allow_duplicate=True),
    Output("lista-bis", "value", allow_duplicate=True),
    Input({"type": "quitar-bis", "index": ALL}, "n_clicks"),
    State("lista-bis", "value"),
    prevent_initial_call=True,
)
def quitar_carpeta_bis(n_clicks, rutas):
    if not any(n_clicks or []) or not isinstance(ctx.triggered_id, dict):
        raise PreventUpdate
    restantes = [ruta for ruta in (rutas or []) if ruta != ctx.triggered_id["index"]]
    return _opciones(restantes), restantes


@callback(
    Output("siguiente-paciente", "children"),
    Input("directorio-pacientes", "value"),
    Input("actualizacion-creacion", "data"),
    Input("actualizacion-gestion", "data"),
)
def mostrar_siguiente_paciente(directorio, _creacion, _gestion):
    try:
        identificador = siguiente_paciente(directorio or DIRECTORIO_PREDETERMINADO)
        return f"La próxima carpeta será: {identificador}"
    except Exception as exc:
        return f"No se puede usar ese directorio: {exc}"


@callback(
    Output("resultado-analisis", "children"),
    Output("crear-paciente", "disabled"),
    Input("analizar", "n_clicks"),
    Input("lista-icca", "value"),
    Input("lista-bis", "value"),
    Input("directorio-pacientes", "value"),
)
# Se ejecuta cuando pulsas: Analizar intervalos
def analizar_intervalos(n_clicks, rutas_icca, carpetas_bis, directorio):
    if ctx.triggered_id != "analizar":
        return html.Div("Pulsa «Analizar intervalos» después de completar la selección."), True
    if not carpetas_bis:
        return html.Div("Selecciona al menos una carpeta BIS."), True
    try:
        analisis = analizar_asignacion(directorio, rutas_icca or [], carpetas_bis)
    except Exception as exc:
        return html.Div(str(exc), className="mensaje-error"), True
    return _vista_analisis(analisis), False


@callback(
    Output("estado-creacion", "children"),
    Output("actualizacion-creacion", "data"),
    Output("pestanas", "value"),
    Output("limpiar-estado-creacion", "disabled"),
    Input("crear-paciente", "n_clicks"),
    State("directorio-pacientes", "value"),
    State("lista-icca", "value"),
    State("lista-bis", "value"),
    State("actualizacion-creacion", "data"),
    prevent_initial_call=True,
)
# Se ejecuta cuando pulsas: Crear carpeta del paciente y llama a crear_paciente(...)
def crear_carpeta_paciente(_n_clicks, directorio, rutas_icca, carpetas_bis, actualizacion):
    if not directorio or not carpetas_bis:
        return (
            html.Div("La selección está incompleta.", className="mensaje-error"),
            no_update,
            no_update,
            False,
        )
    try:
        manifiesto = crear_paciente(directorio, rutas_icca or [], carpetas_bis)
    except Exception as exc:
        return (
            html.Div(f"No se pudo crear el paciente: {exc}", className="mensaje-error"),
            no_update,
            no_update,
            False,
        )
    return (
        html.Div(
            f"{manifiesto['paciente_id']} creado correctamente.",
            className="mensaje-ok",
        ),
        int(actualizacion or 0) + 1,
        "pacientes",
        False,
    )


@callback(
    Output("estado-creacion", "children", allow_duplicate=True),
    Output("limpiar-estado-creacion", "disabled", allow_duplicate=True),
    Input("limpiar-estado-creacion", "n_intervals"),
    prevent_initial_call=True,
)
def limpiar_estado_creacion(_n_intervals):
    return None, True


@callback(
    Output("selector-paciente", "options"),
    Output("selector-paciente", "value"),
    Input("directorio-pacientes", "value"),
    Input("actualizacion-creacion", "data"),
    Input("actualizacion-gestion", "data"),
    State("selector-paciente", "value"),
)
def actualizar_lista_pacientes(directorio, _creacion, _gestion, seleccionado):
    try:
        pacientes = listar_pacientes(directorio or DIRECTORIO_PREDETERMINADO)
    except Exception:
        return [], None
    opciones = [
        {
            "label": f"{paciente['paciente_id']} · {len(paciente.get('sesiones', []))} sesión(es)",
            "value": paciente["paciente_id"],
        }
        for paciente in pacientes
    ]
    valores = {opcion["value"] for opcion in opciones}
    valor = seleccionado if seleccionado in valores else (opciones[-1]["value"] if opciones else None)
    return opciones, valor


@callback(
    Output("detalle-paciente", "children"),
    Input("selector-paciente", "value"),
    Input("directorio-pacientes", "value"),
    Input("actualizacion-creacion", "data"),
    Input("actualizacion-gestion", "data"),
)
def visualizar_paciente(paciente_id, directorio, _creacion, _gestion):
    try:
        pacientes = listar_pacientes(directorio or DIRECTORIO_PREDETERMINADO)
    except Exception as exc:
        return html.Div(f"No se pudieron leer los pacientes: {exc}")
    if not pacientes:
        return html.Div("Todavía no se ha creado ningún paciente.")
    if not paciente_id:
        return html.Div("Selecciona un paciente para consultar sus sesiones.")
    paciente = next((item for item in pacientes if item["paciente_id"] == paciente_id), None)
    return _detalle_paciente(paciente) if paciente else html.Div("El paciente seleccionado ya no existe.")


@callback(
    Output("editar-lista-icca", "options"),
    Output("editar-lista-icca", "value"),
    Input("selector-paciente", "value"),
    Input("actualizacion-creacion", "data"),
    Input("actualizacion-gestion", "data"),
    Input("editar-anadir-icca", "n_clicks"),
    Input("editar-anadir-carpeta-icca", "n_clicks"),
    Input({"type": "editar-quitar-icca", "index": ALL}, "n_clicks"),
    State("directorio-pacientes", "value"),
    State("editar-lista-icca", "value"),
)
def cargar_o_anadir_icca(
    paciente_id,
    _creacion,
    _gestion,
    _n_clicks,
    _n_clicks_carpeta,
    quitar_clicks,
    directorio,
    actuales,
):
    if ctx.triggered_id in {"editar-anadir-icca", "editar-anadir-carpeta-icca"}:
        existentes = list(actuales or [])
        try:
            if ctx.triggered_id == "editar-anadir-carpeta-icca":
                carpeta = _seleccionar_carpeta(
                    "Selecciona una carpeta con Excel ICCA",
                    existentes[-1] if existentes else "",
                )
                nuevos = descubrir_icca_en_carpeta(carpeta) if carpeta else []
            else:
                nuevos = _seleccionar_excel(existentes[-1] if existentes else "")
        except Exception:
            return no_update, no_update
        rutas = list(dict.fromkeys(existentes + nuevos))
        return _opciones(rutas), rutas
    if isinstance(ctx.triggered_id, dict):
        if not any(quitar_clicks or []):
            raise PreventUpdate
        rutas = [ruta for ruta in (actuales or []) if ruta != ctx.triggered_id["index"]]
        return _opciones(rutas), rutas
    paciente = _buscar_paciente(directorio, paciente_id) if paciente_id else None
    rutas = obtener_fuentes_paciente(paciente)["icca"] if paciente else []
    return _opciones(rutas), rutas


@callback(
    Output("editar-selecciones-icca", "children"),
    Input("editar-lista-icca", "value"),
)
def mostrar_edicion_icca(rutas):
    return _tarjetas_seleccion(
        rutas,
        "editar-quitar-icca",
        "Excel ICCA",
        "No hay Excel ICCA seleccionados.",
    )


@callback(
    Output("editar-lista-bis", "options"),
    Output("editar-lista-bis", "value"),
    Input("selector-paciente", "value"),
    Input("actualizacion-creacion", "data"),
    Input("actualizacion-gestion", "data"),
    Input("editar-anadir-bis", "n_clicks"),
    Input("editar-anadir-carpeta-madre-bis", "n_clicks"),
    Input({"type": "editar-quitar-bis", "index": ALL}, "n_clicks"),
    State("directorio-pacientes", "value"),
    State("editar-lista-bis", "value"),
)
def cargar_o_anadir_bis(
    paciente_id,
    _creacion,
    _gestion,
    _n_clicks,
    _n_clicks_carpeta,
    quitar_clicks,
    directorio,
    actuales,
):
    if ctx.triggered_id in {"editar-anadir-bis", "editar-anadir-carpeta-madre-bis"}:
        existentes = list(actuales or [])
        inicial = str(Path(existentes[-1]).parent) if existentes else ""
        try:
            nueva = _seleccionar_carpeta("Selecciona una carpeta con una sesión BIS", inicial)
            if ctx.triggered_id == "editar-anadir-carpeta-madre-bis":
                nuevas = descubrir_sesiones_bis_en_carpeta(nueva) if nueva else []
            else:
                nuevas = [nueva] if nueva else []
        except Exception:
            return no_update, no_update
        rutas = list(dict.fromkeys(existentes + nuevas))
        return _opciones(rutas), rutas
    if isinstance(ctx.triggered_id, dict):
        if not any(quitar_clicks or []):
            raise PreventUpdate
        rutas = [ruta for ruta in (actuales or []) if ruta != ctx.triggered_id["index"]]
        return _opciones(rutas), rutas
    paciente = _buscar_paciente(directorio, paciente_id) if paciente_id else None
    rutas = obtener_fuentes_paciente(paciente)["bis"] if paciente else []
    return _opciones(rutas), rutas


@callback(
    Output("editar-selecciones-bis", "children"),
    Input("editar-lista-bis", "value"),
)
def mostrar_edicion_bis(rutas):
    return _tarjetas_seleccion(
        rutas,
        "editar-quitar-bis",
        "sesión BIS",
        "No hay sesiones BIS seleccionadas.",
    )


@callback(
    Output("resultado-edicion", "children"),
    Output("guardar-cambios", "disabled"),
    Input("editar-analizar", "n_clicks"),
    Input("editar-lista-icca", "value"),
    Input("editar-lista-bis", "value"),
    Input("selector-paciente", "value"),
    State("directorio-pacientes", "value"),
)
def analizar_edicion(_n_clicks, rutas_icca, carpetas_bis, paciente_id, directorio):
    if ctx.triggered_id != "editar-analizar":
        return html.Div("Comprueba los cambios antes de guardarlos."), True
    if not paciente_id or not carpetas_bis:
        return html.Div(
            "El paciente necesita al menos una sesión BIS.",
            className="mensaje-error",
        ), True
    try:
        analisis = analizar_asignacion(
            directorio,
            rutas_icca or [],
            carpetas_bis,
            excluir_paciente=paciente_id,
        )
    except Exception as exc:
        return html.Div(str(exc), className="mensaje-error"), True
    return _vista_analisis(analisis), False


@callback(
    Output("confirmar-eliminacion", "displayed"),
    Input("solicitar-eliminar", "n_clicks"),
    prevent_initial_call=True,
)
def pedir_confirmacion_eliminacion(_n_clicks):
    return True


@callback(
    Output("estado-edicion", "children"),
    Output("actualizacion-gestion", "data"),
    Output("limpiar-estado-edicion", "disabled"),
    Input("guardar-cambios", "n_clicks"),
    Input("confirmar-eliminacion", "submit_n_clicks"),
    State("selector-paciente", "value"),
    State("directorio-pacientes", "value"),
    State("editar-lista-icca", "value"),
    State("editar-lista-bis", "value"),
    State("actualizacion-gestion", "data"),
    prevent_initial_call=True,
)
def guardar_o_eliminar_paciente(
    _guardar,
    _eliminar,
    paciente_id,
    directorio,
    rutas_icca,
    carpetas_bis,
    actualizacion,
):
    if not paciente_id:
        return html.Div("Selecciona un paciente.", className="mensaje-error"), no_update, False
    try:
        if ctx.triggered_id == "guardar-cambios":
            actualizar_paciente(
                directorio,
                paciente_id,
                rutas_icca or [],
                carpetas_bis,
            )
            mensaje = f"{paciente_id} se ha actualizado correctamente."
        elif ctx.triggered_id == "confirmar-eliminacion":
            eliminar_paciente(directorio, paciente_id)
            mensaje = f"{paciente_id} se ha eliminado."
        else:
            raise PreventUpdate
    except Exception as exc:
        return (
            html.Div(f"No se pudo completar la operación: {exc}", className="mensaje-error"),
            no_update,
            False,
        )
    return html.Div(mensaje, className="mensaje-ok"), int(actualizacion or 0) + 1, False


@callback(
    Output("estado-edicion", "children", allow_duplicate=True),
    Output("limpiar-estado-edicion", "disabled", allow_duplicate=True),
    Input("limpiar-estado-edicion", "n_intervals"),
    prevent_initial_call=True,
)
def limpiar_estado_edicion(_n_intervals):
    return None, True


@callback(
    Output("notificacion-abrir", "children"),
    Output("limpiar-notificacion-abrir", "disabled"),
    Input({"type": "abrir-excel", "index": ALL}, "n_clicks"),
    State("directorio-pacientes", "value"),
    prevent_initial_call=True,
)
def abrir_excel_auxiliar(n_clicks, directorio):
    if not any(n_clicks or []) or not isinstance(ctx.triggered_id, dict):
        raise PreventUpdate
    try:
        ruta = Path(ctx.triggered_id["index"]).resolve()
        raiz = Path(directorio or DIRECTORIO_PREDETERMINADO).resolve()
        ruta.relative_to(raiz)
        if not ruta.is_file() or ruta.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise ValueError("El Excel auxiliar no existe.")
        if sys.platform == "win32":
            os.startfile(str(ruta))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
        return html.Div(f"Abriendo {ruta.name}...", className="mensaje-ok"), False
    except Exception as exc:
        return html.Div(f"No se pudo abrir el Excel: {exc}", className="mensaje-error"), False


@callback(
    Output("notificacion-abrir", "children", allow_duplicate=True),
    Output("limpiar-notificacion-abrir", "disabled", allow_duplicate=True),
    Input("limpiar-notificacion-abrir", "n_intervals"),
    prevent_initial_call=True,
)
def limpiar_notificacion_abrir(_n_intervals):
    return None, True

# Arranque de la app
if __name__ == "__main__":
    app.run(host=HOST_DASH, port=PUERTO_ORGANIZADOR, debug=False)

# en local: http://127.0.0.1:8060
# para abrirse desde otra máquina con la IP real -> host=0.0.0.0
