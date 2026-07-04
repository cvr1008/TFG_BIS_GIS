from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from plotly.subplots import make_subplots


AVISO_SINTESIS = (
    "Constantes vitales simuladas a partir de mediciones intermitentes. "
    "No aptas para validación clínica ni correlaciones reales con BIS."
)

NOMBRES_VARIABLES = {
    "fc": "Frecuencia cardíaca",
    "spo2": "SpO₂",
    "pic": "PIC",
    "frecuencia_respiratoria": "Frecuencia respiratoria",
    "temperatura": "Temperatura",
    "presion_arterial": "Presión arterial",
    "pa_sistolica": "PA sistólica",
    "pa_diastolica": "PA diastólica",
    "pa_media": "PA media",
}

RANGOS_REFERENCIA = {
    "hemoglobina": (12.0, 16.0),
    "sodio": (135.0, 145.0),
    "potasio": (3.5, 5.0),
    "calcio_ionico": (4.6, 5.3),
    "cloro": (90.0, 110.0),
    "glucosa_laboratorio": (70.0, 100.0),
    "glucemia_capilar": (70.0, 100.0),
}


def _inicio_dia_clinico(instante):
    inicio = pd.Timestamp(instante).replace(hour=8, minute=0, second=0, microsecond=0)
    if pd.Timestamp(instante) < inicio:
        inicio -= pd.Timedelta(days=1)
    return inicio


def _integrar_acumulado_hasta(inicio, fin, velocidad_ml_h, acumulado, dia_clinico):
    velocidad = float(velocidad_ml_h or 0.0)
    actual = pd.Timestamp(inicio)
    fin = pd.Timestamp(fin)
    while actual < fin:
        siguiente_reset = dia_clinico + pd.Timedelta(days=1)
        tramo_fin = min(fin, siguiente_reset)
        acumulado += velocidad * max(0.0, (tramo_fin - actual).total_seconds()) / 3600.0
        actual = tramo_fin
        if actual == siguiente_reset and actual < fin:
            dia_clinico = siguiente_reset
            acumulado = 0.0
    return acumulado, dia_clinico


def _calcular_acumulado_perfusiones(perfusiones):
    if perfusiones is None or perfusiones.empty:
        return perfusiones
    trabajo = perfusiones.copy()
    if "volumen_acumulado_calculado_ml" in trabajo.columns and trabajo[
        "volumen_acumulado_calculado_ml"
    ].notna().any():
        return trabajo

    for columna in [
        "volumen_acumulado_calculado_ml",
        "dia_clinico_inicio",
        "acumulado_calculado_origen",
        "velocidad_bomba_ml_h",
        "volumen_acumulado_24h_ml",
    ]:
        if columna not in trabajo.columns:
            trabajo[columna] = pd.NA

    trabajo["timestamp"] = pd.to_datetime(trabajo["timestamp"], errors="coerce")
    trabajo["velocidad_bomba_ml_h"] = pd.to_numeric(
        trabajo["velocidad_bomba_ml_h"], errors="coerce"
    )
    trabajo["volumen_acumulado_24h_ml"] = pd.to_numeric(
        trabajo["volumen_acumulado_24h_ml"], errors="coerce"
    )

    for _, grupo in trabajo.dropna(subset=["timestamp", "farmaco"]).groupby(
        "farmaco",
        sort=True,
    ):
        grupo = grupo.sort_values("timestamp", kind="stable")
        acumulado = 0.0
        dia_clinico = None
        instante_previo = None
        velocidad_previa = 0.0
        for indice, fila in grupo.iterrows():
            instante = pd.Timestamp(fila["timestamp"])
            dia_actual = _inicio_dia_clinico(instante)
            if dia_clinico is None:
                acumulado = 0.0
                dia_clinico = dia_actual
                instante_previo = dia_actual
                velocidad_previa = 0.0
            if instante_previo is not None and instante > instante_previo:
                acumulado, dia_clinico = _integrar_acumulado_hasta(
                    instante_previo,
                    instante,
                    velocidad_previa,
                    acumulado,
                    dia_clinico,
                )

            acumulado_real = fila.get("volumen_acumulado_24h_ml")
            if pd.notna(acumulado_real):
                acumulado = float(acumulado_real)
                origen = "ICCA acumulado 24h"
            elif velocidad_previa:
                origen = "integrado desde mL/h"
            else:
                origen = "sin volumen previo; acumulado calculado desde 0"

            trabajo.loc[indice, "volumen_acumulado_calculado_ml"] = round(acumulado, 4)
            trabajo.loc[indice, "dia_clinico_inicio"] = dia_clinico
            trabajo.loc[indice, "acumulado_calculado_origen"] = origen

            velocidad_actual = fila.get("velocidad_bomba_ml_h")
            if pd.notna(velocidad_actual):
                velocidad_previa = float(velocidad_actual)
            instante_previo = instante
    return trabajo


def _normalizar_variable(valor):
    texto = str(valor or "").casefold()
    traduccion = str.maketrans("áéíóúüñ", "aeiouun")
    return "_".join(texto.translate(traduccion).replace("-", " ").split())


def _primer_texto_no_vacio(*valores):
    for valor in valores:
        if pd.notna(valor) and str(valor).strip():
            return str(valor).strip()
    return ""


def cargar_datos_icca(ruta_sintetico, ruta_original):
    sintetico = Path(ruta_sintetico)
    original = Path(ruta_original)
    if sintetico.suffix.casefold() == ".csv":
        constantes = pd.read_csv(sintetico, low_memory=False)
        metadata = json.loads(
            sintetico.with_suffix(".meta.json").read_text(encoding="utf-8")
        )
        series = pd.DataFrame(metadata.get("series_sinteticas") or [])
        auditoria_gasometrias = pd.DataFrame(
            metadata.get("gasometrias_auditoria") or []
        )
    else:
        constantes = pd.read_excel(
            sintetico,
            sheet_name="constantes_1s",
            engine="openpyxl",
        )
        series = pd.read_excel(
            sintetico,
            sheet_name="series_sinteticas",
            engine="openpyxl",
        )
        try:
            auditoria_gasometrias = pd.read_excel(
                sintetico,
                sheet_name="gasometrias_auditoria",
                engine="openpyxl",
            )
        except (ValueError, KeyError):
            auditoria_gasometrias = pd.DataFrame()
    constantes["timestamp"] = pd.to_datetime(constantes["timestamp"], errors="coerce")
    try:
        analisis = pd.read_excel(
            original,
            sheet_name="analisis",
            header=2,
            engine="openpyxl",
        )
        analisis["timestamp"] = pd.to_datetime(analisis["timestamp"], errors="coerce")
    except (ValueError, KeyError):
        analisis = pd.DataFrame()
    try:
        perfusiones = pd.read_excel(
            original,
            sheet_name="perfusiones",
            header=2,
            engine="openpyxl",
        )
        perfusiones["timestamp"] = pd.to_datetime(
            perfusiones["timestamp"], errors="coerce"
        )
    except (ValueError, KeyError):
        perfusiones = pd.DataFrame()
    if not auditoria_gasometrias.empty:
        auditoria_gasometrias["timestamp"] = pd.to_datetime(
            auditoria_gasometrias["timestamp"], errors="coerce"
        )

    if not analisis.empty and "variable" in analisis.columns:
        es_gasometria = analisis["variable"].map(_normalizar_variable).isin(
            {"po2", "pco2"}
        )
        analisis = analisis.loc[~es_gasometria].copy()
    if not auditoria_gasometrias.empty:
        incluidas = auditoria_gasometrias[
            auditoria_gasometrias["incluida_visualizacion"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .eq("si")
        ].copy()
        analisis = pd.concat([analisis, incluidas], ignore_index=True, sort=False)
    return {
        "constantes": constantes,
        "series": series,
        "analisis": analisis,
        "perfusiones": perfusiones,
        "ruta_sintetico": str(sintetico),
        "ruta_original": str(original),
    }


def _agrupar_series(metadata):
    grupos = []
    orden = ["fc", "presion_arterial", "spo2", "pic", "frecuencia_respiratoria", "temperatura"]
    for variable in orden:
        if variable == "presion_arterial":
            filas = metadata[
                metadata["variable"].isin(["pa_sistolica", "pa_diastolica", "pa_media"])
            ]
        else:
            filas = metadata[metadata["variable"] == variable]
        if not filas.empty:
            grupos.append((variable, filas))
    return grupos


def _crear_figura_constantes(datos, inicio, fin):
    constantes = datos["constantes"]
    metadata = datos["series"]
    tramo = constantes[
        constantes["timestamp"].between(inicio, fin, inclusive="both")
    ].copy()
    grupos = _agrupar_series(metadata)
    if tramo.empty or not grupos:
        return None

    figura = make_subplots(
        rows=len(grupos),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=min(0.08, 0.28 / max(1, len(grupos))),
        subplot_titles=[NOMBRES_VARIABLES.get(variable, variable) for variable, _ in grupos],
    )
    colores_variable = {
        "fc": "#1f77b4",
        "pa_sistolica": "#d62728",
        "pa_diastolica": "#1f77b4",
        "pa_media": "#9467bd",
        "spo2": "#17a2b8",
        "pic": "#ff7f0e",
        "frecuencia_respiratoria": "#2ca02c",
        "temperatura": "#e377c2",
    }

    for fila_grafica, (variable, filas_metadata) in enumerate(grupos, start=1):
        for _, metadata_serie in filas_metadata.iterrows():
            clave = metadata_serie["serie"]
            variable_serie = metadata_serie["variable"]
            columna_valor = f"{clave}__valor"
            if columna_valor not in tramo.columns:
                continue
            validos = tramo[columna_valor].notna()
            if not validos.any():
                continue
            paso = max(1, math.ceil(int(validos.sum()) / 5000))
            linea = tramo.loc[validos, ["timestamp", columna_valor]].iloc[::paso]
            fuente = str(metadata_serie.get("fuente") or "")
            nombre_variable = NOMBRES_VARIABLES.get(variable_serie, variable_serie)
            nombre = f"{nombre_variable} · {fuente}" if fuente else nombre_variable
            color = colores_variable.get(variable_serie, "#1f77b4")
            opciones_relleno = (
                {"fill": "tonexty", "fillcolor": "rgba(31, 119, 180, 0.10)"}
                if variable_serie == "pa_diastolica"
                else {}
            )
            figura.add_trace(
                go.Scattergl(
                    x=linea["timestamp"],
                    y=linea[columna_valor],
                    mode="lines",
                    name=nombre,
                    line={"width": 1.4, "color": color},
                    **opciones_relleno,
                    hovertemplate=(
                        "%{x|%d/%m/%Y %H:%M:%S}<br>%{y:.2f} "
                        + str(metadata_serie.get("unidad") or "")
                        + "<extra></extra>"
                    ),
                ),
                row=fila_grafica,
                col=1,
            )
            if "series_reales" in tramo.columns:
                reales = (
                    tramo["series_reales"]
                    .fillna("")
                    .astype(str)
                    .str.split(";")
                    .map(lambda series: clave in series)
                ) & tramo[columna_valor].notna()
                figura.add_trace(
                    go.Scattergl(
                        x=tramo.loc[reales, "timestamp"],
                        y=tramo.loc[reales, columna_valor],
                        mode="markers",
                        name=f"Medición real · {nombre}",
                        marker={"size": 7, "color": color, "line": {"width": 1, "color": "white"}},
                        hovertemplate=(
                            "Medición real<br>%{x|%d/%m/%Y %H:%M:%S}<br>%{y:.2f} "
                            + str(metadata_serie.get("unidad") or "")
                            + "<extra></extra>"
                        ),
                    ),
                    row=fila_grafica,
                    col=1,
                )

        unidad = next(
            (str(valor) for valor in filas_metadata.get("unidad", []) if pd.notna(valor)),
            "",
        )
        figura.update_yaxes(title_text=unidad, row=fila_grafica, col=1)

    figura.update_layout(
        height=max(330, 190 * len(grupos)),
        margin={"l": 170, "r": 390, "t": 80, "b": 80},
        hovermode="x unified",
        legend={
            "orientation": "v",
            "yanchor": "top",
            "y": 1,
            "xanchor": "left",
            "x": 1.03,
        },
        template="plotly_white",
    )
    figura.update_xaxes(
        type="date",
        range=[inicio, fin],
        minallowed=inicio,
        maxallowed=fin,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
    )
    figura.update_xaxes(title_text="Tiempo", row=len(grupos), col=1)
    return figura


def _aviso_rango(fila):
    variable = _normalizar_variable(fila.get("variable"))
    valor = pd.to_numeric(pd.Series([fila.get("valor")]), errors="coerce").iloc[0]
    tipo_gas = _normalizar_variable(
        _primer_texto_no_vacio(
            fila.get("tipo_gasometria_final"), fila.get("tipo_gasometria")
        )
    )
    rango = RANGOS_REFERENCIA.get(variable)
    if variable == "pco2":
        rango = (41.0, 51.0) if "venosa" in tipo_gas else (35.0, 45.0) if "arterial" in tipo_gas else None
    elif variable == "po2":
        rango = (24.0, 40.0) if "venosa" in tipo_gas else (80.0, 100.0) if "arterial" in tipo_gas else None
    if pd.notna(valor) and rango:
        if valor < rango[0]:
            return f"Valor inferior al intervalo de referencia ({rango[0]:g}–{rango[1]:g})"
        if valor > rango[1]:
            return f"Valor superior al intervalo de referencia ({rango[0]:g}–{rango[1]:g})"
        return None
    marca = str(fila.get("marca_original") or "").strip()
    fuera = str(fila.get("fuera_rango_uci") or "").casefold() == "si"
    if marca or fuera:
        return "Marcado fuera de rango en ICCA"
    return None


def _crear_tarjetas_analisis(datos, inicio, fin):
    analisis = datos.get("analisis")
    if analisis is None or analisis.empty or "timestamp" not in analisis:
        return html.Div("Sin análisis clínicos en este intervalo.", className="icca-sin-datos")
    tramo = analisis[analisis["timestamp"].between(inicio, fin, inclusive="both")].copy()
    tramo["_variable_normalizada"] = tramo["variable"].map(_normalizar_variable)
    tramo["_valor_presente"] = (
        tramo["valor"].notna()
        & tramo["valor"].astype(str).str.strip().ne("")
    )
    tramo = tramo.sort_values(
        ["timestamp", "_variable_normalizada", "_valor_presente"],
        ascending=[True, True, False],
        kind="stable",
    )
    tramo = tramo.drop_duplicates(
        subset=["timestamp", "_variable_normalizada"],
        keep="first",
    )
    tramo = tramo.sort_values("timestamp")
    if tramo.empty:
        return html.Div("Sin análisis clínicos en este intervalo.", className="icca-sin-datos")

    tarjetas = []
    for timestamp, grupo in tramo.groupby("timestamp", sort=True):
        mediciones = []
        for _, fila in grupo.iterrows():
            valor = fila.get("valor")
            if pd.isna(valor):
                continue
            aviso = _aviso_rango(fila)
            variable_normalizada = _normalizar_variable(fila.get("variable"))
            origen_tipo = _primer_texto_no_vacio(
                fila.get("origen_tipo_gasometria")
            )
            tipo_final = _primer_texto_no_vacio(fila.get("tipo_gasometria_final"))
            etiqueta_gasometria = None
            if variable_normalizada in {"po2", "pco2"} and tipo_final:
                etiqueta_gasometria = html.Div(
                    f"Gasometria {tipo_final} - tipo {origen_tipo}",
                    style={"fontSize": "0.78rem", "color": "#52606d"},
                )
            mediciones.append(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Strong(str(fila.get("variable") or "Variable")),
                                html.Span(
                                    f"{valor:g} {fila.get('unidad') or ''}"
                                    if isinstance(valor, (int, float))
                                    else f"{valor} {fila.get('unidad') or ''}",
                                ),
                            ],
                            className="icca-medicion-fila",
                        ),
                        etiqueta_gasometria,
                        html.Div(aviso, className="icca-aviso-rango") if aviso else None,
                    ]
                )
            )
        if not mediciones:
            continue
        tarjetas.append(
            html.Div(
                [
                    html.Div(pd.Timestamp(timestamp).strftime("%d/%m/%Y · %H:%M:%S"), className="icca-tarjeta-hora"),
                    html.Div("Análisis clínico", className="icca-tarjeta-titulo"),
                    *mediciones,
                ],
                className="icca-tarjeta-analisis",
            )
        )
    return html.Div(tarjetas, className="icca-timeline-analisis")


def _crear_figura_perfusiones(datos, inicio, fin):
    perfusiones = datos.get("perfusiones")
    if (
        perfusiones is None
        or perfusiones.empty
        or "timestamp" not in perfusiones
        or "farmaco" not in perfusiones
    ):
        return None

    inicio = pd.Timestamp(inicio)
    fin = pd.Timestamp(fin)
    trabajo = perfusiones.copy()
    trabajo["timestamp"] = pd.to_datetime(trabajo["timestamp"], errors="coerce")
    trabajo = trabajo.dropna(subset=["timestamp", "farmaco"])
    for columna in [
        "dosis_actual",
        "velocidad_bomba_ml_h",
        "volumen_acumulado_24h_ml",
        "volumen_acumulado_calculado_ml",
    ]:
        if columna not in trabajo:
            trabajo[columna] = pd.NA
        trabajo[columna] = pd.to_numeric(trabajo[columna], errors="coerce")
    trabajo = _calcular_acumulado_perfusiones(trabajo)
    trabajo = trabajo[
        trabajo[
            [
                "dosis_actual",
                "velocidad_bomba_ml_h",
                "volumen_acumulado_calculado_ml",
            ]
        ].notna().any(axis=1)
    ].sort_values(["farmaco", "timestamp"], kind="stable")
    trabajo = trabajo.drop_duplicates(
        subset=[
            "timestamp",
            "farmaco",
            "dosis_actual",
            "velocidad_bomba_ml_h",
            "volumen_acumulado_calculado_ml",
        ],
        keep="last",
    )
    if trabajo.empty:
        return None

    tramos = {}
    for farmaco, grupo in trabajo.groupby("farmaco", sort=True):
        dentro = grupo[grupo["timestamp"].between(inicio, fin, inclusive="both")]
        anterior = grupo[grupo["timestamp"] < inicio].tail(1)
        if dentro.empty and anterior.empty:
            continue
        linea = pd.concat([anterior, dentro], ignore_index=True)
        linea = linea.sort_values("timestamp", kind="stable")
        if not anterior.empty:
            ancla = anterior.copy()
            ancla["timestamp"] = inicio
            linea = pd.concat([ancla, dentro], ignore_index=True)
        linea[["dosis_actual", "velocidad_bomba_ml_h"]] = linea[
            ["dosis_actual", "velocidad_bomba_ml_h"]
        ].ffill()
        ultimo = linea.tail(1).copy()
        if not ultimo.empty and ultimo.iloc[0]["timestamp"] < fin:
            ultimo["timestamp"] = fin
            linea = pd.concat([linea, ultimo], ignore_index=True)
        tramos[str(farmaco)] = {"linea": linea, "reales": dentro}

    if not tramos:
        return None

    figura = make_subplots(
        rows=len(tramos),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=min(0.08, 0.28 / max(1, len(tramos))),
        subplot_titles=list(tramos),
        specs=[[{"secondary_y": True}] for _ in tramos],
    )
    for fila, (farmaco, tramo) in enumerate(tramos.items(), start=1):
        linea = tramo["linea"]
        reales = tramo["reales"]
        unidad_dosis = _primer_texto_no_vacio(
            *(linea.get("unidad_dosis", pd.Series(dtype=object)).dropna().tolist())
        )
        if linea["dosis_actual"].notna().any():
            figura.add_trace(
                go.Scatter(
                    x=linea["timestamp"],
                    y=linea["dosis_actual"],
                    mode="lines",
                    line={"shape": "hv", "width": 2, "color": "#1f5f99"},
                    name=f"{farmaco} · dosis",
                    hovertemplate=(
                        "%{x|%d/%m/%Y %H:%M:%S}<br>%{y:g} "
                        + unidad_dosis
                        + "<extra></extra>"
                    ),
                ),
                row=fila,
                col=1,
                secondary_y=False,
            )
            reales_dosis = reales[reales["dosis_actual"].notna()]
            figura.add_trace(
                go.Scatter(
                    x=reales_dosis["timestamp"],
                    y=reales_dosis["dosis_actual"],
                    mode="markers",
                    marker={"size": 7, "color": "#1f5f99"},
                    name=f"Cambio real · {farmaco} dosis",
                    hovertemplate=(
                        "Cambio documentado<br>%{x|%d/%m/%Y %H:%M:%S}<br>%{y:g} "
                        + unidad_dosis
                        + "<extra></extra>"
                    ),
                ),
                row=fila,
                col=1,
                secondary_y=False,
            )
            figura.update_yaxes(
                title_text=unidad_dosis or "Dosis",
                row=fila,
                col=1,
                secondary_y=False,
            )
        if linea["velocidad_bomba_ml_h"].notna().any():
            figura.add_trace(
                go.Scatter(
                    x=linea["timestamp"],
                    y=linea["velocidad_bomba_ml_h"],
                    mode="lines",
                    line={"shape": "hv", "width": 2, "color": "#e67e22"},
                    name=f"{farmaco} · bomba",
                    hovertemplate=(
                        "%{x|%d/%m/%Y %H:%M:%S}<br>%{y:g} mL/h<extra></extra>"
                    ),
                ),
                row=fila,
                col=1,
                secondary_y=True,
            )
            reales_bomba = reales[reales["velocidad_bomba_ml_h"].notna()]
            figura.add_trace(
                go.Scatter(
                    x=reales_bomba["timestamp"],
                    y=reales_bomba["velocidad_bomba_ml_h"],
                    mode="markers",
                    marker={"size": 7, "color": "#e67e22"},
                    name=f"Cambio real · {farmaco} bomba",
                    hovertemplate=(
                        "Cambio documentado<br>%{x|%d/%m/%Y %H:%M:%S}<br>"
                        "%{y:g} mL/h<extra></extra>"
                    ),
                ),
                row=fila,
                col=1,
                secondary_y=True,
            )
            figura.update_yaxes(
                title_text="mL/h / mL",
                row=fila,
                col=1,
                secondary_y=True,
            )
        if linea["volumen_acumulado_calculado_ml"].notna().any():
            figura.add_trace(
                go.Scatter(
                    x=linea["timestamp"],
                    y=linea["volumen_acumulado_calculado_ml"],
                    mode="lines",
                    line={"shape": "linear", "width": 2.2, "color": "#2ca02c"},
                    name=f"{farmaco} - acumulado desde 08:00",
                    hovertemplate=(
                        "%{x|%d/%m/%Y %H:%M:%S}<br>%{y:.2f} mL acumulados"
                        "<extra></extra>"
                    ),
                ),
                row=fila,
                col=1,
                secondary_y=True,
            )
            reales_acumulado = reales[
                reales["volumen_acumulado_calculado_ml"].notna()
            ]
            figura.add_trace(
                go.Scatter(
                    x=reales_acumulado["timestamp"],
                    y=reales_acumulado["volumen_acumulado_calculado_ml"],
                    mode="markers",
                    marker={"size": 7, "color": "#2ca02c"},
                    name=f"Acumulado calculado - {farmaco}",
                    hovertemplate=(
                        "Registro usado para acumulado<br>%{x|%d/%m/%Y %H:%M:%S}"
                        "<br>%{y:.2f} mL<extra></extra>"
                    ),
                ),
                row=fila,
                col=1,
                secondary_y=True,
            )
            figura.update_yaxes(
                title_text="mL/h / mL",
                row=fila,
                col=1,
                secondary_y=True,
            )

    figura.update_layout(
        height=max(330, 190 * len(tramos)),
        margin={"l": 170, "r": 390, "t": 80, "b": 80},
        hovermode="x unified",
        legend={
            "orientation": "v",
            "yanchor": "top",
            "y": 1,
            "xanchor": "left",
            "x": 1.03,
        },
        template="plotly_white",
    )
    figura.update_xaxes(type="date", range=[inicio, fin])
    figura.update_xaxes(title_text="Tiempo", row=len(tramos), col=1)
    return figura


def crear_panel_icca(datos, inicio, fin):
    if not datos:
        return html.Div(
            "No hay información ICCA disponible para esta sesión.",
            className="icca-sin-datos",
        )
    figura = _crear_figura_constantes(datos, inicio, fin)
    figura_perfusiones = _crear_figura_perfusiones(datos, inicio, fin)
    return html.Div(
        [
            html.H2("Variables clínicas ICCA", style={"marginBottom": "6px"}),
            html.Div(AVISO_SINTESIS, className="icca-aviso-sintesis"),
            html.H3("Constantes vitales", style={"marginTop": "22px"}),
            (
                dcc.Graph(
                    figure=figura,
                    config={"displaylogo": False, "scrollZoom": True},
                )
                if figura is not None
                else html.Div("Sin constantes vitales en este intervalo.", className="icca-sin-datos")
            ),
            html.H3("Análisis clínicos", style={"marginTop": "22px"}),
            _crear_tarjetas_analisis(datos, inicio, fin),
            html.H3("Perfusiones", style={"marginTop": "22px"}),
            html.Div(
                "La curva verde muestra el volumen acumulado desde el ultimo "
                "reinicio de las 08:00. Si ICCA trae acumulado real se usa como "
                "ancla; si no, se integra la velocidad de bomba en mL/h.",
                style={"color": "#526170", "marginBottom": "8px"},
            ),
            html.Div(
                "Las líneas escalonadas mantienen el último ajuste documentado "
                "hasta el siguiente cambio. Los marcadores corresponden a "
                "registros reales de ICCA; no se sintetizan dosis.",
                style={"color": "#526170", "marginBottom": "8px"},
            ),
            (
                dcc.Graph(
                    figure=figura_perfusiones,
                    config={"displaylogo": False, "scrollZoom": True},
                )
                if figura_perfusiones is not None
                else html.Div(
                    "Sin perfusiones documentadas en este intervalo.",
                    className="icca-sin-datos",
                )
            ),
        ],
        className="panel-icca",
    )
