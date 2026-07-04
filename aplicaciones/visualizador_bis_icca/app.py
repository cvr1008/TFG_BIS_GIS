from threading import Lock
from uuid import uuid4
from pathlib import Path
import os
import subprocess
import sys

import numpy as np 
import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.carpeta_bis import detectar_exportacion_bis
from src.figuras import (
    DSA_FA_GAMMA,
    DSA_FA_VMAX_DB,
    DSA_FA_VMIN_DB,
    crear_figura_dsa_bilateral_interactiva,
    crear_figura_dsa_unilateral_interactiva,
)
from src.figuras_estaticas import crear_panoramica_estatica
from src.lectura_fa import (
    cargar_fa_bilateral_completo_desde_ruta,
    cargar_fa_unilateral_desde_ruta,
)
from src.lectura_spa import (
    cargar_spa_bilateral_desde_ruta,
    cargar_spa_unilateral_desde_ruta,
    preparar_dsa_bilateral_con_spa,
    preparar_dsa_unilateral_con_spa,
)
from src.pacientes_icca import listar_pacientes, preparar_sesiones_paciente
from src.reconstruccion import (
    calcular_mascaras_comunes_desde_rutas,
    reconstruir_desde_rutas,
)
from src.vistas_temporales import (
    crear_opciones_tramos_horarios,
    preparar_vista_temporal,
)
from src.visualizacion_icca import cargar_datos_icca, crear_panel_icca


app = Dash(__name__)
app.title = "Visualizador BIS-ICCA"

ESTILO_PANTALLA = {
    "maxWidth": "1720px",
    "margin": "0 auto",
    "padding": "24px",
    "fontFamily": "Arial, sans-serif",
}

ESTILO_BOTON_PRINCIPAL = {
    "padding": "11px 24px",
    "border": "none",
    "borderRadius": "6px",
    "backgroundColor": "#1f5f99",
    "color": "white",
    "fontSize": "1rem",
    "cursor": "pointer",
}

CONFIGURACION_GRAFICO = {
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToAdd": ["drawline", "eraseshape"],
}

REGISTROS = {}
REGISTROS_LOCK = Lock()


def _directorio_pacientes_predeterminado():
    raiz_proyecto = Path(__file__).resolve().parent.parent.parent
    candidatos = [
        os.environ.get("TFG_PACIENTES_DIR"),
        raiz_proyecto / "datos" / "pacientes",
    ]
    for candidato in candidatos:
        if candidato and Path(candidato).expanduser().is_dir():
            return str(Path(candidato).expanduser().resolve())
    return ""


DIRECTORIO_PACIENTES_PREDETERMINADO = _directorio_pacientes_predeterminado()


def _env_bool(nombre, valor_por_defecto=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return valor_por_defecto
    return valor.strip().casefold() in {"1", "true", "yes", "si", "s"}


def _env_int(nombre, valor_por_defecto):
    try:
        return int(os.environ.get(nombre, valor_por_defecto))
    except (TypeError, ValueError):
        return valor_por_defecto


RUTA_PACIENTES_FIJA = _env_bool("TFG_RUTA_PACIENTES_FIJA")
HOST_DASH = os.environ.get("TFG_DASH_HOST", "127.0.0.1")
PUERTO_VISUALIZADOR = _env_int("TFG_VISUALIZADOR_PORT", 8050)

ESTILO_CONTROLES_TRAMO = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
    "gap": "18px",
    "alignItems": "end",
    "padding": "14px",
    "marginBottom": "12px",
    "backgroundColor": "#f7f9fb",
    "borderRadius": "8px",
}


def _crear_spinner_visualizador():
    return html.Div(
        html.Div(className="spinner-visualizador-anillo"),
        className="spinner-visualizador-contenedor",
        role="status",
        **{"aria-label": "Cargando"},
    )


def _formatear_instante(valor):
    if not valor:
        return "No disponible"
    instante = pd.to_datetime(valor, errors="coerce")
    if pd.isna(instante):
        return "No disponible"
    return instante.strftime("%d/%m/%Y %H:%M:%S")


def _formatear_duracion_segundos(segundos):
    segundos = max(0, int(segundos or 0))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    partes = []
    if horas:
        partes.append(f"{horas} h")
    if minutos:
        partes.append(f"{minutos} min")
    if segundos or not partes:
        partes.append(f"{segundos} s")
    return " ".join(partes)


def _badge(texto, fondo, color):
    return html.Span(
        texto,
        style={
            "display": "inline-block",
            "padding": "5px 9px",
            "borderRadius": "999px",
            "backgroundColor": fondo,
            "color": color,
            "fontSize": "0.8rem",
            "fontWeight": "bold",
        },
    )


def _crear_tarjeta_sesion(sesion):
    estado_icca = sesion.get("estado_icca")
    if estado_icca == "completa":
        badges = [_badge("ICCA disponible para toda la sesión", "#e7f5ea", "#225c2e")]
    elif estado_icca == "parcial":
        cobertura = float(sesion.get("cobertura_icca") or 0)
        badges = [_badge(f"ICCA parcial ({cobertura:.0%})", "#fff4cf", "#725400")]
    else:
        badges = [_badge("Sin información ICCA", "#f1f3f5", "#55616d")]

    sintetico = sesion.get("icca_sintetico") or {}
    if sintetico:
        badges.append(_badge("ICCA con valores sintéticos", "#e8f1fb", "#1f5f99"))
    elif sesion.get("error_sintesis_icca"):
        badges.append(_badge("No se pudo generar el ICCA sintético", "#fdecec", "#8a1f1f"))
    if sesion.get("alerta_recorte_bis"):
        badges.append(_badge("Aviso: recorte BIS ≥ 50 %", "#fdecec", "#8a1f1f"))
    badges.append(
        _badge(
            ".f_a disponible" if sesion.get("fa_disponible") else "Sin .f_a",
            "#e7f5ea" if sesion.get("fa_disponible") else "#f1f3f5",
            "#225c2e" if sesion.get("fa_disponible") else "#55616d",
        )
    )
    badges.append(
        _badge(
            "Reconstrucción disponible"
            if sesion.get("reconstruccion_disponible")
            else "Reconstrucción no disponible",
            "#e8f1fb" if sesion.get("reconstruccion_disponible") else "#f1f3f5",
            "#1f5f99" if sesion.get("reconstruccion_disponible") else "#55616d",
        )
    )

    inicio = _formatear_instante(sesion.get("inicio_bis"))
    fin = _formatear_instante(sesion.get("fin_bis"))
    error_bis = sesion.get("error_bis")
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Sesión BIS", className="sesion-etiqueta"),
                            html.H3(
                                sesion.get("nombre_carpeta") or sesion.get("sesion_bis_id"),
                                style={"margin": "4px 0"},
                            ),
                            html.Div(
                                f"{inicio} – {fin}",
                                style={"color": "#4f5d69"},
                            ),
                            html.Div(
                                f"Registro {sesion.get('modo') or 'no identificado'}",
                                style={"color": "#4f5d69", "marginTop": "4px"},
                            ),
                        ]
                    ),
                    html.Button(
                        "Seleccionar sesión",
                        id={
                            "type": "seleccionar-sesion",
                            "index": sesion.get("nombre_carpeta"),
                        },
                        disabled=bool(error_bis),
                        style={
                            **ESTILO_BOTON_PRINCIPAL,
                            "whiteSpace": "nowrap",
                            **(
                                {"opacity": 0.45, "cursor": "not-allowed"}
                                if error_bis
                                else {}
                            ),
                        },
                    ),
                ],
                className="sesion-cabecera",
            ),
            html.Div(badges, className="sesion-badges"),
            (
                html.Div(
                    f"Constantes: {sintetico.get('series', 0)} series, "
                    f"{sintetico.get('mediciones_reales', 0)} mediciones reales.",
                    className="sesion-resumen-icca",
                )
                if sintetico
                else None
            ),
            html.Div(f"No se pudo preparar la sesión BIS: {error_bis}", className="sesion-error")
            if error_bis
            else None,
        ],
        className="tarjeta-sesion-paciente",
    )


def _archivo_estado_texto(estado):
    return {
        "found": "Encontrado",
        "empty": "Vacío",
        "missing": "No encontrado",
    }.get(estado, "No disponible")


def _archivo_estado_color(estado):
    return {
        "found": ("#edf7ef", "#225c2e"),
        "empty": ("#fff4d9", "#725400"),
        "missing": ("#fdecec", "#8a1f1f"),
    }.get(estado, ("#f2f5f8", "#4a5560"))


def _crear_panel_validacion(deteccion):
    validacion = deteccion.get("validacion") or {}
    warnings = validacion.get("warnings") or []
    cobertura = validacion.get("cobertura_temporal") or {}
    alerta_temporal = bool(cobertura.get("alerta"))
    modo = "bilateral" if deteccion.get("modo") == "bilateral" else "unilateral"
    if alerta_temporal:
        estado_texto = "Revisar recorte temporal"
        estado_fondo = "#fdecec"
        estado_color = "#8a1f1f"
    else:
        estado_texto = "Lista con avisos" if warnings else "Lista para visualización"
        estado_fondo = "#fff7e6" if warnings else "#edf7ef"
        estado_color = "#755100" if warnings else "#225c2e"

    archivos = []
    for archivo in validacion.get("files", []):
        fondo, color = _archivo_estado_color(archivo.get("status"))
        archivos.append(
            html.Div(
                children=[
                    html.Div(
                        [
                            html.Strong(archivo.get("label", "Archivo")),
                            html.Span(
                                _archivo_estado_texto(archivo.get("status")),
                                style={
                                    "padding": "3px 8px",
                                    "borderRadius": "999px",
                                    "backgroundColor": fondo,
                                    "color": color,
                                    "fontSize": "0.78rem",
                                    "fontWeight": "bold",
                                },
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "gap": "10px",
                        },
                    ),
                    html.Div(
                        archivo.get("name", "No encontrado"),
                        style={"fontWeight": "bold", "marginTop": "6px"},
                    ),
                    html.Div(
                        archivo.get("size_label", "No disponible"),
                        style={"color": "#55616d", "fontSize": "0.86rem"},
                    ),
                ],
                style={
                    "padding": "11px",
                    "border": "1px solid #d8e0e7",
                    "borderRadius": "8px",
                    "backgroundColor": "white",
                },
            )
        )

    spa = validacion.get("spa") or {}
    fa = validacion.get("fa") or {}
    alignment = validacion.get("alignment") or {}
    alineacion = {
        "aligned": "Alineados",
        "minor_offset": "Desfase menor",
        "mismatch": "No alineados",
        "unknown": "No evaluable",
    }.get(alignment.get("status"), "No evaluable")

    metricas = [
        ("Modo", modo),
        ("Inicio .spa", _formatear_instante(spa.get("first_timestamp"))),
        ("Fin .spa", _formatear_instante(spa.get("last_timestamp"))),
        ("Filas .spa", spa.get("row_count", 0)),
        ("Tiempos válidos .spa", spa.get("valid_timestamp_count", 0)),
        ("Duplicados .spa eliminados", spa.get("duplicate_timestamp_count", 0)),
    ]
    if fa.get("found"):
        filas_bins = (
            f"{fa.get('rows_with_expected_bins', 0)} / "
            f"{fa.get('rows_checked_for_bins', 0)}"
            if fa.get("rows_checked_for_bins", 0) < fa.get("rows_parsed", 0)
            else fa.get("rows_with_expected_bins", 0)
        )
        metricas.extend(
            [
                ("Datasets .f_a", fa.get("datasets", 0)),
                ("Filas .f_a", fa.get("rows_parsed", 0)),
                (
                    "Duplicados .f_a eliminados",
                    fa.get("duplicate_timestamp_count", 0),
                ),
                ("Filas muestreadas con 60 bins", filas_bins),
                ("Alineación .spa/.f_a", alineacion),
            ]
        )
    else:
        metricas.append(("Matriz .f_a", "No disponible; se usará raw si procede"))

    inicio_cobertura = cobertura.get("inicio") or spa.get("first_timestamp")
    fin_cobertura = cobertura.get("fin") or spa.get("last_timestamp")
    inicio = _formatear_instante(inicio_cobertura)
    fin = _formatear_instante(fin_cobertura)
    if inicio_cobertura and fin_cobertura:
        inicio_dt = pd.to_datetime(inicio_cobertura, errors="coerce")
        fin_dt = pd.to_datetime(fin_cobertura, errors="coerce")
        if pd.notna(inicio_dt) and pd.notna(fin_dt):
            duracion = fin_dt - inicio_dt
            total_seg = max(0, int(duracion.total_seconds()))
            horas, resto = divmod(total_seg, 3600)
            minutos = resto // 60
            duracion_texto = (
                f"{horas} h {minutos} min" if horas else f"{minutos} min"
            )
        else:
            duracion_texto = "No disponible"
    else:
        duracion_texto = "No disponible"

    for nombre, datos in (cobertura.get("fuentes") or {}).items():
        etiqueta = {
            "raw": "Onda cruda",
            "spa": "Variables .spa",
            "fa": "Matriz .f_a",
        }.get(nombre, nombre)
        metricas.append(
            (
                f"Recorte {etiqueta}",
                (
                    f"{datos.get('segundos_retenidos', 0)} / "
                    f"{datos.get('segundos_originales', 0)} s; "
                    f"{datos.get('proporcion_eliminada', 0) * 100:.1f}% "
                    "eliminado"
                ),
            )
        )
        tramos = datos.get("tramos_recortados") or []
        if not tramos:
            descripcion_recorte = "Sin recorte de extremos"
        elif len(tramos) == 1:
            tramo = tramos[0]
            descripcion_recorte = (
                f"Bloque continuo al {tramo.get('posicion')}: "
                f"{_formatear_duracion_segundos(tramo.get('segundos'))}"
            )
        else:
            descripcion_recorte = (
                f"{len(tramos)} bloques en los extremos: "
                + " + ".join(
                    _formatear_duracion_segundos(tramo.get("segundos"))
                    for tramo in tramos
                )
            )
        metricas.append(
            (f"Forma del recorte {etiqueta}", descripcion_recorte)
        )

        numero_huecos = datos.get("numero_tramos_huecos_internos", 0)
        if numero_huecos:
            descripcion_huecos = (
                f"{datos.get('segundos_huecos_internos', 0)} s ausentes "
                f"en {numero_huecos} tramo(s)"
            )
        else:
            descripcion_huecos = "Sin discontinuidades internas"
        metricas.append(
            (f"Huecos internos {etiqueta}", descripcion_huecos)
        )

    origenes = deteccion.get("origenes") or []
    if "fa" in origenes and "raw" in origenes:
        disponibilidad = "Matriz original y reconstrucción disponibles"
    elif "fa" in origenes:
        disponibilidad = "Matriz original disponible"
    elif "raw" in origenes:
        disponibilidad = "Se usará reconstrucción desde la onda cruda"
    else:
        disponibilidad = "No hay una matriz disponible"

    return html.Div(
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Sesión BIS detectada",
                                style={
                                    "textTransform": "uppercase",
                                    "letterSpacing": "0.06em",
                                    "fontSize": "0.78rem",
                                    "fontWeight": "bold",
                                    "color": "#65727f",
                                },
                            ),
                            html.H3(
                                f"{deteccion.get('base')} ({modo})",
                                style={"margin": "5px 0 0"},
                            ),
                        ]
                    ),
                    html.Span(
                        estado_texto,
                        style={
                            "padding": "6px 10px",
                            "borderRadius": "999px",
                            "backgroundColor": estado_fondo,
                            "color": estado_color,
                            "fontWeight": "bold",
                            "whiteSpace": "nowrap",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "flex-start",
                    "gap": "16px",
                    "marginBottom": "14px",
                },
            ),
            html.Div(
                [
                    html.Div([html.Strong("Intervalo"), html.Span(f"{inicio} - {fin}")]),
                    html.Div([html.Strong("Duración"), html.Span(duracion_texto)]),
                    html.Div([html.Strong("Tipo de registro"), html.Span(modo)]),
                    html.Div([html.Strong("Visualización"), html.Span(disponibilidad)]),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(240px, 1fr))",
                    "gap": "10px 24px",
                    "marginBottom": "12px",
                },
            ),
            html.Div(
                [html.Strong("Avisos: "), html.Span(" | ".join(warnings))]
                if warnings
                else "Todo listo para visualizar.",
                style={
                    "padding": "10px 12px",
                    "backgroundColor": (
                        "#fdecec"
                        if alerta_temporal
                        else "#fff7e6" if warnings else "#edf7ef"
                    ),
                    "color": (
                        "#8a1f1f"
                        if alerta_temporal
                        else "#755100" if warnings else "#225c2e"
                    ),
                    "borderRadius": "6px",
                    "fontSize": "0.9rem",
                    "marginBottom": "10px",
                },
            ),
            html.Details(
                children=[
                    html.Summary(
                        "Detalles técnicos",
                        style={
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "color": "#254a6b",
                        },
                    ),
                    html.Div(
                        archivos,
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                            "gap": "10px",
                            "marginTop": "12px",
                            "marginBottom": "12px",
                        },
                    ),
                    html.Div(
                        [
                            html.Div(
                                [html.Strong(nombre), html.Span(str(valor))],
                                style={
                                    "display": "flex",
                                    "justifyContent": "space-between",
                                    "gap": "12px",
                                    "padding": "7px 0",
                                    "borderBottom": "1px solid #e4ebf1",
                                },
                            )
                            for nombre, valor in metricas
                        ],
                    ),
                ]
            ),
        ],
        style={
            "padding": "14px",
            "marginBottom": "14px",
            "backgroundColor": "#f7f9fb",
            "border": "1px solid #dce5ed",
            "borderRadius": "10px",
        },
    )


app.layout = html.Div(
    children=[
        dcc.Store(id="registro-activo", storage_type="memory"),
        dcc.Store(id="carpeta-detectada", storage_type="memory"),
        dcc.Store(id="sesiones-paciente", storage_type="memory"),
        dcc.Store(id="sesion-seleccionada", storage_type="memory"),
        html.Div(
            id="pantalla-archivos",
            children=[
                html.H1("Visualizador BIS-ICCA"),
                html.P(
                    id="texto-introduccion",
                    children=(
                        "Selecciona la carpeta que contiene los pacientes organizados, "
                        "elige un paciente y después una de sus sesiones BIS."
                    ),
                ),
                html.Div(
                    children=[
                        html.Label(
                            "Repositorio de pacientes"
                            if RUTA_PACIENTES_FIJA
                            else "Carpeta que contiene los pacientes",
                            style={
                                "display": "block",
                                "fontWeight": "bold",
                                "marginBottom": "7px",
                            },
                        ),
                        html.Div(
                            [
                                dcc.Input(
                                    id="ruta-carpeta-pacientes",
                                    value=DIRECTORIO_PACIENTES_PREDETERMINADO,
                                    type="text",
                                    debounce=True,
                                    placeholder=(
                                        "Selecciona la carpeta PACIENTES o pega aquí su ruta"
                                    ),
                                    style=(
                                        {"display": "none"}
                                        if RUTA_PACIENTES_FIJA
                                        else {
                                            "flex": "1",
                                            "minWidth": "280px",
                                            "padding": "10px 12px",
                                            "border": "1px solid #aeb8c2",
                                            "borderRadius": "6px",
                                            "fontSize": "0.95rem",
                                        }
                                    ),
                                ),
                                html.Button(
                                    "Seleccionar carpeta",
                                    id="boton-seleccionar-carpeta",
                                    n_clicks=0,
                                    style=(
                                        {"display": "none"}
                                        if RUTA_PACIENTES_FIJA
                                        else {
                                            "padding": "10px 18px",
                                            "border": "1px solid #1f5f99",
                                            "borderRadius": "6px",
                                            "backgroundColor": "white",
                                            "color": "#1f5f99",
                                            "cursor": "pointer",
                                        }
                                    ),
                                ),
                            ],
                            style={
                                "display": "flex",
                                "gap": "10px",
                                "flexWrap": "wrap",
                            },
                        ),
                        html.Div(
                            [
                                html.Strong("Ruta configurada"),
                                html.Code(DIRECTORIO_PACIENTES_PREDETERMINADO),
                            ],
                            style={
                                "display": "grid",
                                "gap": "6px",
                                "padding": "12px",
                                "backgroundColor": "white",
                                "border": "1px solid #dce5ed",
                                "borderRadius": "8px",
                                "overflowWrap": "anywhere",
                            },
                        )
                        if RUTA_PACIENTES_FIJA
                        else None,
                    ],
                    style={
                        "padding": "14px",
                        "marginBottom": "18px",
                        "backgroundColor": "#f7f9fb",
                        "borderRadius": "8px",
                    },
                ),
                html.Div(
                    [
                        html.Label(
                            "Paciente",
                            style={
                                "display": "block",
                                "fontWeight": "bold",
                                "marginBottom": "7px",
                            },
                        ),
                        dcc.Dropdown(
                            id="selector-paciente",
                            options=[],
                            value=None,
                            clearable=False,
                            placeholder="Selecciona un paciente",
                        ),
                        html.Div(id="estado-pacientes", style={"marginTop": "10px"}),
                    ],
                    style={
                        "padding": "14px",
                        "marginBottom": "18px",
                        "backgroundColor": "#f7f9fb",
                        "borderRadius": "8px",
                    },
                ),
                dcc.Loading(
                    type="circle",
                    children=html.Div(id="tarjetas-sesiones", className="lista-sesiones"),
                ),
                html.Div(
                    id="contenedor-origen-dsa",
                    children=[
                        html.Label(
                            "Origen de la matriz",
                            style={
                                "display": "block",
                                "fontWeight": "bold",
                                "marginBottom": "7px",
                            },
                        ),
                        dcc.RadioItems(
                            id="origen-dsa",
                            options=[],
                            value=None,
                            inline=True,
                            labelStyle={"marginRight": "24px"},
                        ),
                    ],
                    style={
                        "display": "none",
                        "padding": "14px",
                        "marginBottom": "14px",
                        "backgroundColor": "#f7f9fb",
                        "borderRadius": "8px",
                    },
                ),
                html.Div(
                    id="resumen-parametros-reconstruccion",
                    children=(
                        "Reconstrucción siguiendo el notebook: Welch con "
                        "ventana de 2 s y avance de 1 s; potencia por bins de "
                        "0,5 Hz; máscara final según SQI, TOTPOW, ceros, "
                        "discontinuidades y ausencia de DSA; media móvil "
                        "causal según SpSmooth; desplazamiento empírico de "
                        "10 s en unilateral o 6 s en bilateral. Unilateral: "
                        "canal 1. Bilateral: canal 1 para la izquierda y canal "
                        "3 para la derecha, siguiendo el dataset espectral "
                        "exportado por VISTA. SEF, MEF y BIS siguen la máscara "
                        "de su hemisferio; ASYM09 requiere ambas DSA."
                    ),
                    style={
                        "display": "none",
                        "padding": "12px 14px",
                        "marginBottom": "14px",
                        "backgroundColor": "#eef5fb",
                        "borderRadius": "6px",
                        "color": "#254a6b",
                        "fontSize": "0.92rem",
                    },
                ),
                html.Div(
                    id="estado-archivos",
                    children="Selecciona una sesión BIS.",
                    style={
                        "padding": "12px 14px",
                        "marginBottom": "14px",
                        "backgroundColor": "#f2f5f8",
                        "borderRadius": "6px",
                    },
                ),
                html.Div(
                    id="panel-validacion-archivos",
                    style={"display": "none"},
                ),
                html.Div(
                    id="error-procesado",
                    style={
                        "display": "none",
                        "padding": "12px 14px",
                        "marginBottom": "14px",
                        "backgroundColor": "#fdecec",
                        "color": "#8a1f1f",
                        "borderRadius": "6px",
                    },
                ),
                dcc.Loading(
                    type="circle",
                    children=html.Div(
                        id="estado-carga-matriz",
                        children="",
                        style={
                            "minHeight": "28px",
                            "marginBottom": "8px",
                        },
                    ),
                ),
                dcc.Loading(
                    type="circle",
                    custom_spinner=_crear_spinner_visualizador(),
                    delay_show=150,
                    children=html.Button(
                        "Ver matriz",
                        id="boton-ver-matriz",
                        n_clicks=0,
                        disabled=True,
                        style={
                            **ESTILO_BOTON_PRINCIPAL,
                            "opacity": 0.45,
                            "cursor": "not-allowed",
                        },
                    ),
                ),
            ],
            style=ESTILO_PANTALLA,
        ),
        html.Div(
            id="pantalla-matriz",
            children=[
                html.Div(
                    children=[
                        html.Button(
                            "Cambiar sesión",
                            id="boton-volver",
                            n_clicks=0,
                            style={
                                "padding": "9px 16px",
                                "border": "1px solid #1f5f99",
                                "borderRadius": "6px",
                                "backgroundColor": "white",
                                "color": "#1f5f99",
                                "fontSize": "0.95rem",
                                "cursor": "pointer",
                            },
                        ),
                        html.H1(
                            id="titulo-matriz",
                            children="Matriz DSA",
                            style={"margin": "0"},
                        ),
                    ],
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "20px",
                        "marginBottom": "18px",
                    },
                ),
                html.Div(
                    id="intervalo-matriz",
                    style={
                        "padding": "12px 14px",
                        "marginBottom": "10px",
                        "backgroundColor": "#f2f5f8",
                        "borderRadius": "6px",
                    },
                ),
                html.Div(id="aviso-icca-matriz", style={"display": "none"}),
                html.Div(
                    id="parametros-matriz",
                    style={"display": "none"},
                ),
                html.Div(
                    id="controles-tramo",
                    children=[
                        html.Div(
                            children=[
                                html.Label(
                                    "Tramo horario",
                                    style={
                                        "display": "block",
                                        "fontWeight": "bold",
                                        "marginBottom": "6px",
                                    },
                                ),
                                dcc.Dropdown(
                                    id="selector-tramo",
                                    options=[],
                                    value=None,
                                    clearable=False,
                                    searchable=True,
                                ),
                            ]
                        ),
                        html.Div(
                            children=[
                                html.Label(
                                    "Duración / vista",
                                    style={
                                        "display": "block",
                                        "fontWeight": "bold",
                                        "marginBottom": "8px",
                                    },
                                ),
                                dcc.Tabs(
                                    id="duracion-vista",
                                    children=[
                                        dcc.Tab(label="1 h", value="1h"),
                                        dcc.Tab(label="2 h", value="2h"),
                                        dcc.Tab(label="4 h", value="4h"),
                                        dcc.Tab(label="Todo", value="todo"),
                                    ],
                                    value="1h",
                                    colors={
                                        "border": "#d6dce2",
                                        "primary": "#1f5f99",
                                        "background": "#f2f5f8",
                                    },
                                ),
                            ]
                        ),
                    ],
                    style={"display": "none"},
                ),
                html.Div(
                    id="error-vista",
                    style={
                        "display": "none",
                        "padding": "12px 14px",
                        "marginBottom": "12px",
                        "backgroundColor": "#fdecec",
                        "color": "#8a1f1f",
                        "borderRadius": "6px",
                    },
                ),
                dcc.Loading(
                    custom_spinner=_crear_spinner_visualizador(),
                    delay_show=150,
                    parent_style={"minHeight": "110px"},
                    children=html.Div(id="contenedor-visualizacion"),
                ),
                html.P(
                    "Selecciona primero un tramo horario. Dentro de esa vista puedes "
                    "elegir una duración de 1 h, 2 h, 4 h o Todo; "
                    "también puedes hacer zoom directamente sobre la matriz.",
                    style={"color": "#555", "fontSize": "0.92rem"},
                ),
                html.P(
                    id="descripcion-matriz",
                    children=(
                        "El color representa la potencia espectral de las 60 "
                        "frecuencias entre 0,5 y 30 Hz. El cuadro del cursor muestra "
                        "la hora y los valores SEF, MEF, BIS y SR correspondientes a "
                        "ese segundo; el EMG se representa como una gráfica alineada."
                    ),
                    style={"display": "none"},
                ),
            ],
            style={**ESTILO_PANTALLA, "display": "none"},
        ),
    ]
)

app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
      body { margin: 0; background: #ffffff; }
      .lista-sesiones { display: grid; gap: 14px; margin-bottom: 18px; }
      .tarjeta-sesion-paciente { border: 1px solid #d8e0e7; border-radius: 10px; padding: 16px; background: #ffffff; box-shadow: 0 2px 8px rgba(31, 95, 153, .06); }
      .sesion-cabecera { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; }
      .sesion-etiqueta { text-transform: uppercase; letter-spacing: .06em; color: #65727f; font-size: .75rem; font-weight: bold; }
      .sesion-badges { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 13px; }
      .sesion-resumen-icca { margin-top: 11px; color: #4f5d69; font-size: .9rem; }
      .sesion-error { margin-top: 11px; padding: 9px 11px; border-radius: 6px; background: #fdecec; color: #8a1f1f; }
      .panel-icca { margin-top: 28px; padding-top: 22px; border-top: 2px solid #dce5ed; }
      .icca-aviso-sintesis { padding: 11px 13px; background: #fff4cf; color: #6d5100; border-radius: 7px; font-weight: 600; }
      .icca-timeline-analisis { display: flex; align-items: stretch; gap: 13px; overflow-x: auto; padding: 8px 2px 16px; }
      .icca-tarjeta-analisis { min-width: 260px; max-width: 330px; border: 1px solid #ccd8e2; border-top: 4px solid #1f5f99; border-radius: 8px; padding: 12px; background: #f9fbfc; }
      .icca-tarjeta-hora { color: #526170; font-size: .82rem; }
      .icca-tarjeta-titulo { font-weight: 700; margin: 4px 0 9px; color: #254a6b; }
      .icca-medicion-fila { display: flex; justify-content: space-between; gap: 12px; padding: 5px 0; border-bottom: 1px solid #e2e8ee; }
      .icca-aviso-rango { color: #9a3d00; background: #fff0dc; border-radius: 4px; padding: 4px 6px; margin-top: 4px; font-size: .78rem; }
      .icca-sin-datos { padding: 12px 14px; border: 1px dashed #c7d1da; border-radius: 7px; color: #5c6975; background: #f9fbfc; }
      .spinner-visualizador-contenedor { transform: translateY(-28px); }
      .spinner-visualizador-anillo { width: 58px; height: 58px; border: 6px solid #e4d8f4; border-top-color: #7641bd; border-radius: 50%; animation: giro-visualizador .8s linear infinite; box-sizing: border-box; }
      @keyframes giro-visualizador { to { transform: rotate(360deg); } }
      @media (max-width: 720px) { .sesion-cabecera { flex-direction: column; } }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
  </body>
</html>
"""


@app.callback(
    Output("ruta-carpeta-pacientes", "value"),
    Input("boton-seleccionar-carpeta", "n_clicks"),
    State("ruta-carpeta-pacientes", "value"),
    prevent_initial_call=True,
)
def abrir_selector_carpeta(_n_clicks, ruta_actual):
    codigo_selector = r"""
import sys
from pathlib import Path
from tkinter import Tk, filedialog

sys.stdout.reconfigure(encoding="utf-8")
inicial = sys.argv[1] if len(sys.argv) > 1 else ""
opciones = {
    "title": "Selecciona la carpeta que contiene los pacientes",
    "mustexist": True,
}
if inicial and Path(inicial).is_dir():
    opciones["initialdir"] = inicial

raiz = Tk()
raiz.withdraw()
raiz.attributes("-topmost", True)
try:
    ruta = filedialog.askdirectory(**opciones)
    if ruta:
        print(ruta, end="")
finally:
    raiz.destroy()
"""
    resultado = subprocess.run(
        [sys.executable, "-c", codigo_selector, ruta_actual or ""],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if resultado.returncode != 0:
        print("No se pudo abrir el selector de carpeta:", resultado.stderr)
        return no_update
    ruta = resultado.stdout.strip()
    return ruta or no_update


@app.callback(
    Output("selector-paciente", "options"),
    Output("selector-paciente", "value"),
    Output("estado-pacientes", "children"),
    Input("ruta-carpeta-pacientes", "value"),
)
def actualizar_selector_pacientes(ruta_pacientes):
    if not ruta_pacientes:
        return [], None, "Selecciona primero la carpeta que contiene los pacientes."
    try:
        pacientes = listar_pacientes(ruta_pacientes)
    except Exception as exc:
        return [], None, html.Div(str(exc), style={"color": "#8a1f1f"})
    opciones = [
        {
            "label": (
                f"{paciente.get('paciente_id')} · "
                f"{len(paciente.get('sesiones', []))} sesión(es)"
            ),
            "value": paciente.get("paciente_id"),
        }
        for paciente in pacientes
    ]
    return opciones, None, f"{len(opciones)} paciente(s) encontrado(s)."


@app.callback(
    Output("sesiones-paciente", "data"),
    Output("tarjetas-sesiones", "children"),
    Input("selector-paciente", "value"),
    State("ruta-carpeta-pacientes", "value"),
)
def cargar_sesiones_del_paciente(paciente_id, ruta_pacientes):
    if not paciente_id:
        return [], html.Div(
            "Selecciona un paciente para consultar sus sesiones BIS.",
            className="icca-sin-datos",
        )
    try:
        sesiones = preparar_sesiones_paciente(
            ruta_pacientes,
            paciente_id,
            generar_sinteticos=True,
        )
    except Exception as exc:
        return [], html.Div(str(exc), className="sesion-error")
    if not sesiones:
        return [], html.Div(
            "Este paciente todavía no contiene sesiones BIS.",
            className="icca-sin-datos",
        )
    return sesiones, [_crear_tarjeta_sesion(sesion) for sesion in sesiones]


@app.callback(
    Output("sesion-seleccionada", "data"),
    Input({"type": "seleccionar-sesion", "index": ALL}, "n_clicks"),
    State("sesiones-paciente", "data"),
    prevent_initial_call=True,
)
def seleccionar_sesion(n_clicks, sesiones):
    if not any(n_clicks or []) or not isinstance(ctx.triggered_id, dict):
        raise PreventUpdate
    identificador = ctx.triggered_id.get("index")
    sesion = next(
        (
            item
            for item in (sesiones or [])
            if item.get("nombre_carpeta") == identificador
        ),
        None,
    )
    if sesion is None:
        raise PreventUpdate
    return sesion


@app.callback(
    Output("carpeta-detectada", "data"),
    Output("estado-archivos", "children"),
    Output("estado-archivos", "style"),
    Output("panel-validacion-archivos", "children"),
    Output("panel-validacion-archivos", "style"),
    Output("origen-dsa", "options"),
    Output("origen-dsa", "value"),
    Output("contenedor-origen-dsa", "style"),
    Input("sesion-seleccionada", "data"),
)
def analizar_carpeta(sesion):
    estilo_base = {
        "padding": "12px 14px",
        "marginBottom": "14px",
        "backgroundColor": "#f2f5f8",
        "borderRadius": "6px",
    }
    estilo_origen = {
        "display": "none",
        "padding": "14px",
        "marginBottom": "14px",
        "backgroundColor": "#f7f9fb",
        "borderRadius": "8px",
    }
    if not sesion:
        return (
            None,
            "Selecciona una sesión BIS.",
            estilo_base,
            "",
            {"display": "none"},
            [],
            None,
            estilo_origen,
        )

    try:
        deteccion_base = sesion.get("deteccion_bis") or detectar_exportacion_bis(
            sesion.get("carpeta_bis_absoluta")
        )
        deteccion = dict(deteccion_base)
        deteccion["sesion_paciente"] = {
            clave: valor
            for clave, valor in sesion.items()
            if clave != "deteccion_bis"
        }
    except Exception as exc:
        return (
            None,
            f"No se pudo preparar la carpeta: {exc}",
            {
                **estilo_base,
                "backgroundColor": "#fdecec",
                "color": "#8a1f1f",
            },
            "",
            {"display": "none"},
            [],
            None,
            estilo_origen,
        )

    modo = "bilateral" if deteccion["modo"] == "bilateral" else "unilateral"
    if deteccion["origen_forzado"] == "raw":
        detalle = (
            "El .f_a no existe o está vacío; se utilizará automáticamente "
            "la reconstrucción desde la onda cruda."
        )
    elif deteccion["origen_forzado"] == "fa":
        detalle = "Solo está disponible la matriz original del .f_a."
    else:
        detalle = (
            "Están disponibles la matriz original y la reconstrucción; "
            "elige cuál quieres mostrar."
        )

    opciones = []
    if "fa" in deteccion["origenes"]:
        opciones.append(
            {"label": "Matriz original del archivo .f_a", "value": "fa"}
        )
    if "raw" in deteccion["origenes"]:
        opciones.append(
            {"label": "Reconstrucción desde la onda cruda", "value": "raw"}
        )
    valor = deteccion["origen_forzado"] or "fa"
    if len(opciones) > 1:
        estilo_origen["display"] = "block"

    estado = f"Sesión {deteccion['base']} seleccionada ({modo}). {detalle}"
    return (
        deteccion,
        estado,
        {
            **estilo_base,
            "display": "none",
            "backgroundColor": "#edf7ef",
            "color": "#225c2e",
        },
        "",
        {"display": "none"},
        opciones,
        valor,
        estilo_origen,
    )


@app.callback(
    Output("boton-ver-matriz", "disabled"),
    Output("boton-ver-matriz", "style"),
    Output("boton-ver-matriz", "children"),
    Output("resumen-parametros-reconstruccion", "style"),
    Input("carpeta-detectada", "data"),
    Input("origen-dsa", "value"),
)
def actualizar_accion_carpeta(deteccion, origen_dsa):
    disponible = bool(
        deteccion
        and origen_dsa
        and origen_dsa in deteccion.get("origenes", [])
    )
    estilo_boton = (
        ESTILO_BOTON_PRINCIPAL
        if disponible
        else {
            **ESTILO_BOTON_PRINCIPAL,
            "opacity": 0.45,
            "cursor": "not-allowed",
        }
    )
    texto = (
        "Reconstruir y ver matriz"
        if origen_dsa == "raw"
        else "Ver matriz"
    )
    estilo_resumen = {"display": "none"}
    return not disponible, estilo_boton, texto, estilo_resumen


def _guardar_registro(registro):
    identificador = uuid4().hex
    with REGISTROS_LOCK:
        REGISTROS.clear()
        REGISTROS[identificador] = registro
    return identificador


def _eliminar_registro(datos_registro):
    if not datos_registro:
        return
    with REGISTROS_LOCK:
        REGISTROS.pop(datos_registro.get("id"), None)


def _obtener_registro(datos_registro):
    if not datos_registro:
        return None
    with REGISTROS_LOCK:
        return REGISTROS.get(datos_registro.get("id"))


def _crear_figura_vista(vista, vista_completa):
    argumentos_comunes = {
        "tiempo": vista["tiempo"],
        "frecuencias": vista["frecuencias"],
        "vmin": DSA_FA_VMIN_DB,
        "vmax": DSA_FA_VMAX_DB,
        "gamma": DSA_FA_GAMMA,
        "mostrar_controles_tiempo": not vista_completa,
        "modo_panoramico": False,
    }

    if vista["modo"] == "bilateral":
        return crear_figura_dsa_bilateral_interactiva(
            matriz_izq=vista["matriz_izq"],
            matriz_der=vista["matriz_der"],
            sef_izq=vista["sef_izq"],
            mef_izq=vista["mef_izq"],
            sef_der=vista["sef_der"],
            mef_der=vista["mef_der"],
            asimetria=vista["asimetria"],
            bis_izq=vista["bis_izq"],
            bis_der=vista["bis_der"],
            emg_izq=vista["emg_izq"],
            emg_der=vista["emg_der"],
            sr_izq=vista["sr_izq"],
            sr_der=vista["sr_der"],
            **argumentos_comunes,
        )

    return crear_figura_dsa_unilateral_interactiva(
        matriz=vista["matriz"],
        sef=vista["sef"],
        mef=vista["mef"],
        bis=vista["bis"],
        emg=vista["emg"],
        sr=vista["sr"],
        mask_total=None,
        titulo=None,
        **argumentos_comunes,
    )


def _crear_componente_vista(vista, vista_completa):
    if vista.get("vista_estatica", False):
        return html.Img(
            src=crear_panoramica_estatica(vista),
            alt="Vista estática de la matriz DSA",
            style={
                "display": "block",
                "width": "100%",
                "height": "auto",
                "margin": "0 auto",
            },
        )

    return dcc.Graph(
        figure=_crear_figura_vista(vista, vista_completa),
        config=CONFIGURACION_GRAFICO,
        style={"width": "100%"},
    )


@app.callback(
    Output("pantalla-archivos", "style"),
    Output("pantalla-matriz", "style"),
    Output("titulo-matriz", "children"),
    Output("descripcion-matriz", "children"),
    Output("parametros-matriz", "children"),
    Output("parametros-matriz", "style"),
    Output("error-procesado", "children"),
    Output("error-procesado", "style"),
    Output("estado-carga-matriz", "children"),
    Output("selector-tramo", "options"),
    Output("selector-tramo", "value"),
    Output("controles-tramo", "style"),
    Output("duracion-vista", "value"),
    Output("registro-activo", "data"),
    Input("boton-ver-matriz", "n_clicks"),
    Input("boton-volver", "n_clicks"),
    State("carpeta-detectada", "data"),
    State("origen-dsa", "value"),
    State("registro-activo", "data"),
    prevent_initial_call=True,
)
def cambiar_pantalla(
    _n_ver,
    _n_volver,
    deteccion,
    origen_dsa,
    registro_activo,
):
    estilo_error = {
        "display": "block",
        "padding": "12px 14px",
        "marginBottom": "14px",
        "backgroundColor": "#fdecec",
        "color": "#8a1f1f",
        "borderRadius": "6px",
    }

    if ctx.triggered_id == "boton-volver":
        _eliminar_registro(registro_activo)
        return (
            ESTILO_PANTALLA,
            {**ESTILO_PANTALLA, "display": "none"},
            no_update,
            no_update,
            no_update,
            {"display": "none"},
            "",
            {"display": "none"},
            "",
            [],
            None,
            {"display": "none"},
            "1h",
            None,
        )

    if (
        not deteccion
        or not origen_dsa
        or origen_dsa not in deteccion.get("origenes", [])
    ):
        return (
            ESTILO_PANTALLA,
            {**ESTILO_PANTALLA, "display": "none"},
            no_update,
            no_update,
            no_update,
            {"display": "none"},
            "Selecciona una sesión BIS válida antes de continuar.",
            estilo_error,
            "",
            [],
            None,
            {"display": "none"},
            "1h",
            None,
        )

    try:
        modo_analisis = deteccion["modo"]
        archivos = deteccion["archivos"]
        df_spa = (
            cargar_spa_bilateral_desde_ruta(archivos["spa"])
            if modo_analisis == "bilateral"
            else cargar_spa_unilateral_desde_ruta(archivos["spa"])
        )

        if origen_dsa == "raw":
            registro = reconstruir_desde_rutas(
                modo=modo_analisis,
                ruta_header=archivos["header"],
                ruta_ta=archivos["ta"],
                ruta_raw=archivos["raw"],
                df_spa=df_spa,
                ruta_fa=(
                    archivos["fa"]
                    if deteccion.get("fa_disponible")
                    else None
                ),
            )
            parametros = registro["parametros_reconstruccion"]
            titulo_matriz = (
                "DSA reconstruida bilateral"
                if modo_analisis == "bilateral"
                else "DSA reconstruida unilateral"
            )
            descripcion = (
                "Reconstrucción desde la onda cruda mediante Welch. "
                + (
                    "En bilateral se reconstruye el dataset izquierdo desde "
                    "C1 y el derecho desde C3. "
                    if modo_analisis == "bilateral"
                    else (
                        "En unilateral se reconstruye desde C1, el dataset "
                        "espectral válido exportado por VISTA. "
                    )
                )
                + "Se alinea con la timeline oficial del .spa. La máscara de "
                "calidad se calcula antes del suavizado para que los segundos "
                "no válidos no contribuyan a la media móvil, y se conserva "
                "después como bandas blancas. "
                "El índice BIS, EMGLOW01 y SR12 se alinean con la misma timeline. "
                "El recuadro derecho muestra la densidad espectral media de "
                "cada banda y el ratio alfa-delta calculado mediante la "
                "potencia absoluta del intervalo seleccionado."
            )
            descripcion_lofilter = (
                f"LoFilter {parametros['lofilter_codigo']}: "
                f"{parametros['filtro_pasa_altos_hz']} Hz"
                if parametros["lofilter_codigo"] is not None
                else (
                    "LoFilter ausente: "
                    f"{parametros['filtro_pasa_altos_hz']} Hz predeterminado"
                )
            )
            descripcion_combinacion = (
                "canal 1 unilateral"
                if modo_analisis == "unilateral"
                else (
                    "canal 1 para izquierda y canal 3 para derecha"
                )
            )
            texto_parametros = (
                "Procesamiento aplicado: "
                f"Welch (ventana {parametros['ventana_welch_s']} s, avance "
                f"{parametros['paso_welch_s']} s, referencia temporal "
                f"{parametros['tiempo_referencia']}); fs "
                f"{parametros['fs']} Hz; potencia por bin de "
                f"{parametros['paso_frecuencia']} Hz; Butterworth pasa-altos "
                f"causal de orden {parametros['orden_filtro_pasa_altos']} "
                f"({descripcion_lofilter}); media móvil causal de "
                f"{parametros['suavizado_s']} s "
                f"(SpSmooth {parametros['spsmooth_codigo']}) calculada solo "
                "con segundos válidos; desplazamiento "
                f"empírico de {parametros['shift_s']} s; máscara previa y "
                f"final por hemisferio para SQI < {parametros['umbral_sqi']}, "
                "TOTPOW ausente, "
                f"al menos el {parametros['umbral_ceros_raw'] * 100:.0f}% de "
                "muestras crudas a cero, discontinuidad temporal o ausencia "
                "de DSA. "
                "SEF, MEF, BIS, EMG y SR siguen la máscara de su hemisferio; ASYM09 "
                "requiere ambas DSA; "
                f"{descripcion_combinacion}. Visualización lineal: 49–94 dB. "
                "Conversión a dB según la convención actual del notebook."
            )
            estilo_parametros = {"display": "none"}
        elif modo_analisis == "bilateral":
            mascaras_comunes = calcular_mascaras_comunes_desde_rutas(
                modo=modo_analisis,
                ruta_header=archivos["header"],
                ruta_ta=archivos["ta"],
                ruta_raw=archivos["raw"],
                df_spa=df_spa,
                ruta_fa=archivos["fa"],
            )
            tiempo, frecuencias, dsa_izq, dsa_der = (
                cargar_fa_bilateral_completo_desde_ruta(archivos["fa"])
            )
            (
                tiempo_comun,
                dsa_plot_izq,
                dsa_plot_der,
                curvas_izq,
                curvas_der,
                asimetria,
                _mask_izq,
                _mask_der,
            ) = preparar_dsa_bilateral_con_spa(
                tiempo=tiempo,
                dsa_izq=dsa_izq,
                dsa_der=dsa_der,
                df_spa=df_spa,
                umbral_sqi=15,
                mask_izq_comun=mascaras_comunes["final"]["izquierda"],
                mask_der_comun=mascaras_comunes["final"]["derecha"],
                timeline_comun=mascaras_comunes["timeline"],
            )
            registro = {
                "modo": "bilateral",
                "origen": "fa",
                "tiempo": tiempo_comun.reset_index(drop=True),
                "frecuencias": np.asarray(frecuencias, dtype=float),
                "matriz_izq": dsa_plot_izq.to_numpy(dtype=float),
                "matriz_der": dsa_plot_der.to_numpy(dtype=float),
                "sef_izq": curvas_izq["SEF08"].to_numpy(dtype=float),
                "mef_izq": curvas_izq["MEDFRQ08"].to_numpy(dtype=float),
                "sef_der": curvas_der["SEF08"].to_numpy(dtype=float),
                "mef_der": curvas_der["MEDFRQ08"].to_numpy(dtype=float),
                "bis_izq": curvas_izq["DB13U01"].to_numpy(dtype=float),
                "bis_der": curvas_der["DB13U01"].to_numpy(dtype=float),
                "emg_izq": curvas_izq["EMGLOW01"].to_numpy(dtype=float),
                "emg_der": curvas_der["EMGLOW01"].to_numpy(dtype=float),
                "sr_izq": curvas_izq["SR12"].to_numpy(dtype=float),
                "sr_der": curvas_der["SR12"].to_numpy(dtype=float),
                "asimetria": np.asarray(asimetria, dtype=float),
            }
            titulo_matriz = "Matriz DSA bilateral"
            descripcion = (
                "Las matrices izquierda y derecha comparten el mismo rango temporal "
                "y la escala clínica fija de 49 a 94 dB. Entre ambas se muestran "
                "ASYM09, los índices BIS y el EMG de ambos hemisferios, todos "
                "alineados segundo a segundo. El cuadro del cursor incluye el SR "
                "de los últimos 63 segundos. La vista Todo ofrece una panorámica general "
                "no interactiva cuando el registro es largo. Los recuadros "
                "derechos resumen la densidad espectral media por bandas y "
                "el ratio alfa-delta de cada hemisferio."
            )
            texto_parametros = ""
            estilo_parametros = {"display": "none"}
        else:
            mascaras_comunes = calcular_mascaras_comunes_desde_rutas(
                modo=modo_analisis,
                ruta_header=archivos["header"],
                ruta_ta=archivos["ta"],
                ruta_raw=archivos["raw"],
                df_spa=df_spa,
                ruta_fa=archivos["fa"],
            )
            tiempo, frecuencias, dsa = cargar_fa_unilateral_desde_ruta(
                archivos["fa"]
            )
            dsa_plot, df_alineado, _mask_total = preparar_dsa_unilateral_con_spa(
                tiempo=tiempo,
                dsa=dsa,
                df_spa=df_spa,
                umbral_sqi=15,
                mask_comun=mascaras_comunes["final"]["unilateral"],
                timeline_comun=mascaras_comunes["timeline"],
            )
            registro = {
                "modo": "unilateral",
                "origen": "fa",
                "tiempo": pd.to_datetime(
                    df_alineado["Time"],
                    errors="coerce",
                ).reset_index(drop=True),
                "frecuencias": np.asarray(frecuencias, dtype=float),
                "matriz": dsa_plot.to_numpy(dtype=float),
                "sef": df_alineado["SEF08"].to_numpy(dtype=float),
                "mef": df_alineado["MEDFRQ08"].to_numpy(dtype=float),
                "bis": df_alineado["DB13U01"].to_numpy(dtype=float),
                "emg": df_alineado["EMGLOW01"].to_numpy(dtype=float),
                "sr": df_alineado["SR12"].to_numpy(dtype=float),
            }
            titulo_matriz = "Matriz DSA unilateral"
            descripcion = (
                "El color representa la potencia espectral entre 0,5 y 30 Hz con "
                "la escala clínica fija de 49 a 94 dB. Debajo se muestra el índice "
                "BIS y el EMG alineados segundo a segundo; el cuadro del cursor "
                "incluye el SR de los últimos 63 segundos. La vista Todo ofrece "
                "una panorámica "
                "general no interactiva cuando el registro es largo. El recuadro "
                "derecho resume la densidad espectral media por bandas y el "
                "ratio alfa-delta del intervalo mostrado."
            )
            texto_parametros = ""
            estilo_parametros = {"display": "none"}

        sesion_paciente = deteccion.get("sesion_paciente") or {}
        resumen_sintetico = sesion_paciente.get("icca_sintetico") or {}
        registro["sesion_paciente"] = sesion_paciente
        registro["icca"] = None
        if resumen_sintetico.get("ruta") and sesion_paciente.get(
            "icca_auxiliar_absoluto"
        ):
            registro["icca"] = cargar_datos_icca(
                resumen_sintetico["ruta"],
                sesion_paciente["icca_auxiliar_absoluto"],
            )

        opciones = crear_opciones_tramos_horarios(registro["tiempo"])
        identificador = _guardar_registro(registro)
        return (
            {**ESTILO_PANTALLA, "display": "none"},
            ESTILO_PANTALLA,
            titulo_matriz,
            descripcion,
            texto_parametros,
            estilo_parametros,
            "",
            {"display": "none"},
            "",
            opciones,
            opciones[0]["value"],
            ESTILO_CONTROLES_TRAMO,
            "1h",
            {"id": identificador},
        )

    except Exception as exc:
        return (
            ESTILO_PANTALLA,
            {**ESTILO_PANTALLA, "display": "none"},
            no_update,
            no_update,
            no_update,
            {"display": "none"},
            f"Error al procesar los archivos: {exc}",
            estilo_error,
            "",
            [],
            None,
            {"display": "none"},
            "1h",
            None,
        )


@app.callback(
    Output("contenedor-visualizacion", "children"),
    Output("intervalo-matriz", "children"),
    Output("error-vista", "children"),
    Output("error-vista", "style"),
    Input("registro-activo", "data"),
    Input("selector-tramo", "value"),
    Input("duracion-vista", "value"),
)
def actualizar_vista_temporal(registro_activo, valor_tramo, duracion):
    if not registro_activo:
        return None, "", "", {"display": "none"}

    registro = _obtener_registro(registro_activo)
    if registro is None:
        return (
            no_update,
            no_update,
            "El registro ya no está disponible. Vuelve a cargar los archivos.",
            {
                "display": "block",
                "padding": "12px 14px",
                "marginBottom": "12px",
                "backgroundColor": "#fdecec",
                "color": "#8a1f1f",
                "borderRadius": "6px",
            },
        )

    try:
        if valor_tramo is None:
            return (
                no_update,
                no_update,
                "",
                {"display": "none"},
            )

        vista, inicio, fin, vista_completa = preparar_vista_temporal(
            registro,
            valor_tramo,
            duracion,
        )
        componente_dsa = _crear_componente_vista(vista, vista_completa)
        componente = html.Div(
            [
                componente_dsa,
                crear_panel_icca(registro.get("icca"), inicio, fin),
            ]
        )
        inicio_texto = inicio.strftime("%d/%m/%Y %H:%M:%S")
        fin_texto = fin.strftime("%d/%m/%Y %H:%M:%S")

        if vista_completa:
            if vista.get("vista_estatica", False):
                elementos = (
                    "las dos matrices, SEF, MEF, ASYM09, BIS y EMG"
                    if vista["modo"] == "bilateral"
                    else "la matriz, SEF, MEF, BIS y EMG"
                )
                intervalo = (
                    f"Vista completa estática: {inicio_texto} - {fin_texto}. "
                    f"Se representan {elementos} utilizando todos los segundos "
                    "originales, sin agrupar la DSA. Los recuadros muestran "
                    "la densidad espectral media y el ratio alfa-delta de los "
                    "segundos válidos."
                )
            else:
                intervalo = (
                    f"Vista completa: {inicio_texto} - {fin_texto}. "
                    "Resolución original: una columna por segundo. Los recuadros "
                    "muestran la densidad espectral media y el ratio alfa-delta "
                    "de los segundos válidos."
                )
        else:
            intervalo = (
                f"{'Vista estática de 4 h' if vista.get('vista_estatica') else 'Intervalo mostrado'}: {inicio_texto} - {fin_texto}. "
                "La densidad espectral media por bandas y el ratio alfa-delta "
                "corresponden a este intervalo."
            )

        return componente, intervalo, "", {"display": "none"}

    except Exception as exc:
        return (
            no_update,
            no_update,
            f"Error al preparar la vista: {exc}",
            {
                "display": "block",
                "padding": "12px 14px",
                "marginBottom": "12px",
                "backgroundColor": "#fdecec",
                "color": "#8a1f1f",
                "borderRadius": "6px",
            },
        )


@app.callback(
    Output("aviso-icca-matriz", "children"),
    Output("aviso-icca-matriz", "style"),
    Input("registro-activo", "data"),
)
def mostrar_estado_icca_matriz(registro_activo):
    registro = _obtener_registro(registro_activo)
    if registro is None:
        return "", {"display": "none"}
    sesion = registro.get("sesion_paciente") or {}
    if registro.get("icca") is not None:
        return (
            "ICCA disponible. Las constantes intermedias son valores sintéticos "
            "reproducibles; las mediciones reales se conservan marcadas.",
            {
                "display": "block",
                "padding": "11px 13px",
                "marginBottom": "10px",
                "backgroundColor": "#fff4cf",
                "color": "#6d5100",
                "borderRadius": "7px",
            },
        )
    if sesion.get("estado_icca") == "ausente":
        texto = "Esta sesión no contiene información ICCA."
    else:
        texto = "Hay información ICCA, pero no se pudo preparar la copia sintética."
    return (
        texto,
        {
            "display": "block",
            "padding": "11px 13px",
            "marginBottom": "10px",
            "backgroundColor": "#f1f3f5",
            "color": "#55616d",
            "borderRadius": "7px",
        },
    )


@app.callback(
    Output("selector-tramo", "disabled"),
    Input("duracion-vista", "value"),
)
def bloquear_selector_en_vista_completa(duracion):
    return duracion == "todo"


if __name__ == "__main__":
    app.run(host=HOST_DASH, port=PUERTO_VISUALIZADOR, debug=False)
