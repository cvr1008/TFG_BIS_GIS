from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from plotly.subplots import make_subplots


AVISO_SINTESIS = (
    "Solo se muestran mediciones registradas. Los tramos indican el último "
    "valor disponible hasta la siguiente medición."
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

CONFIGURACION_GRAFICO_ICCA = {"displaylogo": False, "scrollZoom": False}

COLORES_PERFUSIONES = [
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
]


def _extraer_peso_kg(general):
    if general is None or general.empty or "peso_kg" not in general:
        return None
    valores = pd.to_numeric(general["peso_kg"], errors="coerce").dropna()
    if valores.empty or float(valores.iloc[0]) <= 0:
        return None
    return float(valores.iloc[0])


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
        general = pd.read_excel(
            original,
            sheet_name="general",
            header=2,
            engine="openpyxl",
        )
    except (ValueError, KeyError):
        general = pd.DataFrame()
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
        "general": general,
        "peso_kg": _extraer_peso_kg(general),
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


def _mediciones_reales_constante(constantes, clave, columna_valor):
    if columna_valor not in constantes.columns or "timestamp" not in constantes.columns:
        return pd.DataFrame(columns=["timestamp", columna_valor])

    validos = constantes[columna_valor].notna()
    if "series_reales" in constantes.columns:
        reales = (
            constantes["series_reales"]
            .fillna("")
            .astype(str)
            .str.split(";")
            .map(lambda series: clave in series)
        )
        validos = validos & reales

    return (
        constantes.loc[validos, ["timestamp", columna_valor]]
        .dropna(subset=["timestamp", columna_valor])
        .sort_values("timestamp", kind="stable")
        .drop_duplicates(subset=["timestamp"], keep="last")
    )


def _tramo_documentado(mediciones, columna_valor, inicio, fin):
    mediciones = mediciones.sort_values("timestamp", kind="stable")
    anteriores = mediciones[mediciones["timestamp"] < inicio].tail(1)
    dentro = mediciones[mediciones["timestamp"].between(inicio, fin, inclusive="both")]
    puntos = []

    if not anteriores.empty:
        puntos.append(
            {
                "timestamp": pd.Timestamp(inicio),
                columna_valor: anteriores.iloc[0][columna_valor],
            }
        )

    puntos.extend(dentro[["timestamp", columna_valor]].to_dict("records"))
    if not puntos:
        return pd.DataFrame(columns=["timestamp", columna_valor]), dentro

    ultimo = puntos[-1]
    if pd.Timestamp(ultimo["timestamp"]) < pd.Timestamp(fin):
        puntos.append(
            {
                "timestamp": pd.Timestamp(fin),
                columna_valor: ultimo[columna_valor],
            }
        )

    return pd.DataFrame(puntos), dentro


def _etiquetas_hover_tramo_constante(linea, reales_dentro):
    reales = {
        pd.Timestamp(timestamp)
        for timestamp in pd.to_datetime(
            reales_dentro.get("timestamp", pd.Series(dtype="datetime64[ns]")),
            errors="coerce",
        ).dropna()
    }
    etiquetas = []
    for timestamp in linea["timestamp"]:
        if pd.Timestamp(timestamp) in reales:
            etiquetas.append("Medición real")
        else:
            etiquetas.append("Valor mantenido")
    return etiquetas


def _rango_y_con_margen(valores):
    serie = pd.to_numeric(pd.Series(valores), errors="coerce").dropna()
    if serie.empty:
        return None
    minimo = float(serie.min())
    maximo = float(serie.max())
    amplitud = maximo - minimo
    margen = max(amplitud * 0.12, abs(maximo) * 0.03, 1.0)
    return [minimo - margen, maximo + margen]


def _crear_figura_constantes(datos, inicio, fin):
    constantes = datos["constantes"]
    metadata = datos["series"]
    grupos = _agrupar_series(metadata)
    if constantes.empty or not grupos:
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
        valores_fila = []
        for _, metadata_serie in filas_metadata.iterrows():
            clave = metadata_serie["serie"]
            variable_serie = metadata_serie["variable"]
            columna_valor = f"{clave}__valor"
            mediciones = _mediciones_reales_constante(
                constantes,
                clave,
                columna_valor,
            )
            linea, reales_dentro = _tramo_documentado(
                mediciones,
                columna_valor,
                pd.Timestamp(inicio),
                pd.Timestamp(fin),
            )
            if linea.empty and reales_dentro.empty:
                continue
            nombre_variable = NOMBRES_VARIABLES.get(variable_serie, variable_serie)
            nombre = nombre_variable
            color = colores_variable.get(variable_serie, "#1f77b4")

            if not linea.empty and len(linea) > 1:
                valores_fila.extend(linea[columna_valor].dropna().tolist())
                figura.add_trace(
                    go.Scatter(
                        x=linea["timestamp"],
                        y=linea[columna_valor],
                        mode="lines",
                        name=nombre,
                        line={"shape": "hv", "width": 2, "color": color},
                        customdata=_etiquetas_hover_tramo_constante(
                            linea,
                            reales_dentro,
                        ),
                        hovertemplate=(
                            "%{customdata}: %{y:.2f} "
                            + str(metadata_serie.get("unidad") or "")
                            + "<extra></extra>"
                        ),
                    ),
                    row=fila_grafica,
                    col=1,
                )
            if not reales_dentro.empty:
                valores_fila.extend(reales_dentro[columna_valor].dropna().tolist())
                figura.add_trace(
                    go.Scatter(
                        x=reales_dentro["timestamp"],
                        y=reales_dentro[columna_valor],
                        mode="markers",
                        name=nombre,
                        marker={
                            "size": 8,
                            "color": color,
                            "line": {"width": 1, "color": "white"},
                        },
                        cliponaxis=False,
                        hoverinfo="skip",
                        showlegend=False,
                    ),
                    row=fila_grafica,
                    col=1,
                )

        unidad = next(
            (str(valor) for valor in filas_metadata.get("unidad", []) if pd.notna(valor)),
            "",
        )
        figura.update_yaxes(
            title_text=unidad,
            range=_rango_y_con_margen(valores_fila),
            title_standoff=24,
            automargin=True,
            row=fila_grafica,
            col=1,
        )

    if not figura.data:
        return None

    figura.update_layout(
        height=max(360, 220 * len(grupos)),
        margin={"l": 205, "r": 390, "t": 90, "b": 100},
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


def _curva_dosis_farmaco(grupo, inicio, fin):
    inicio = pd.Timestamp(inicio)
    fin = pd.Timestamp(fin)
    grupo = grupo.sort_values("timestamp", kind="stable").copy()
    if grupo.empty:
        return (
            pd.DataFrame(columns=["timestamp", "dosis"]),
            pd.DataFrame(columns=list(grupo.columns) + ["dosis_evento"]),
        )

    eventos = grupo[
        (grupo["timestamp"] <= fin) & grupo["dosis_actual"].notna()
    ].copy()
    if eventos.empty:
        return (
            pd.DataFrame(columns=["timestamp", "dosis"]),
            pd.DataFrame(columns=list(grupo.columns) + ["dosis_evento"]),
        )

    eventos_previos = eventos[eventos["timestamp"] <= inicio]
    eventos_visibles = eventos[eventos["timestamp"] > inicio]
    dosis_inicial = (
        float(eventos_previos["dosis_actual"].iloc[-1])
        if not eventos_previos.empty
        else None
    )
    puntos = []
    eventos_marcados = []

    def anadir_punto(instante, valor):
        instante = pd.Timestamp(instante)
        if inicio <= instante <= fin:
            puntos.append({"timestamp": instante, "dosis": float(valor)})

    def marcar_evento(fila):
        instante = pd.Timestamp(fila["timestamp"])
        if inicio <= instante <= fin:
            evento = fila.to_dict()
            evento["dosis_evento"] = float(fila["dosis_actual"])
            eventos_marcados.append(evento)

    if dosis_inicial is not None:
        anadir_punto(inicio, dosis_inicial)
        for _, fila in eventos_previos[eventos_previos["timestamp"] == inicio].iterrows():
            marcar_evento(fila)

    for _, fila in eventos_visibles.iterrows():
        instante = pd.Timestamp(fila["timestamp"])
        anadir_punto(instante, fila["dosis_actual"])
        marcar_evento(fila)

    if puntos:
        ultimo_valor = puntos[-1]["dosis"]
        if pd.Timestamp(puntos[-1]["timestamp"]) < fin:
            anadir_punto(fin, ultimo_valor)

    curva = pd.DataFrame(puntos)
    if curva.empty or curva["dosis"].notna().sum() < 2:
        curva = pd.DataFrame(columns=["timestamp", "dosis"])
    return curva, pd.DataFrame(eventos_marcados)


def _etiqueta_dosis(unidad):
    unidad = str(unidad or "").strip()
    return f"Dosis administrada ({unidad})" if unidad else "Dosis administrada"


def _preparar_grupo_perfusion(grupo, inicio, fin):
    grupo = grupo.sort_values("timestamp", kind="stable").copy()
    grupo = grupo[grupo["dosis_actual"].notna()].copy()
    if grupo.empty:
        return None, None

    unidades = grupo["unidad_dosis"].dropna().astype(str).str.strip()
    unidades = unidades[unidades != ""]
    if unidades.empty:
        return None, None
    unidad = unidades.iloc[0]

    grupo = grupo[
        grupo["unidad_dosis"].fillna("").astype(str).str.strip().eq(unidad)
    ].copy()
    if grupo.empty:
        return None, None
    return grupo, {
        "unidad": unidad,
        "etiqueta": _etiqueta_dosis(unidad),
    }


def _texto_hover_eventos_perfusion(grupo, configuracion):
    textos = []
    for _, fila in grupo.iterrows():
        lineas = []
        dosis = fila.get("dosis_actual")
        if pd.notna(dosis):
            unidad = fila.get("unidad_dosis")
            sufijo = f" {unidad}" if pd.notna(unidad) and str(unidad).strip() else ""
            lineas.append(f"Dosis desde este instante: {float(dosis):.2f}{sufijo}")
        velocidad = fila.get("velocidad_bomba_ml_h")
        if pd.notna(velocidad):
            lineas.append(f"Bomba documentada: {float(velocidad):.2f} mL/h")
        if not lineas:
            lineas.append("Registro real documentado")
        textos.append("<br>".join(lineas))
    return textos


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
    ]:
        if columna not in trabajo:
            trabajo[columna] = pd.NA
        trabajo[columna] = pd.to_numeric(trabajo[columna], errors="coerce")
    if "unidad_dosis" not in trabajo:
        trabajo["unidad_dosis"] = ""
    trabajo = trabajo[trabajo["dosis_actual"].notna()].sort_values(
        ["farmaco", "timestamp"],
        kind="stable",
    )
    trabajo = trabajo.drop_duplicates(
        subset=[
            "timestamp",
            "farmaco",
            "dosis_actual",
            "unidad_dosis",
            "velocidad_bomba_ml_h",
        ],
        keep="last",
    )
    if trabajo.empty:
        return None

    curvas = {}
    eventos_por_farmaco = {}
    configuraciones = {}
    for farmaco, grupo in trabajo.groupby("farmaco", sort=True):
        grupo_preparado, configuracion = _preparar_grupo_perfusion(
            grupo,
            inicio,
            fin,
        )
        if grupo_preparado is None:
            continue
        curva, eventos = _curva_dosis_farmaco(grupo_preparado, inicio, fin)
        if curva.empty:
            continue
        curvas[str(farmaco)] = curva
        eventos_por_farmaco[str(farmaco)] = eventos
        configuraciones[str(farmaco)] = configuracion

    if not curvas:
        return None

    figura = make_subplots(
        rows=len(curvas),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=min(0.12, 0.60 / max(1, len(curvas))),
        subplot_titles=list(curvas),
    )
    for fila, (farmaco, curva) in enumerate(curvas.items(), start=1):
        color = COLORES_PERFUSIONES[(fila - 1) % len(COLORES_PERFUSIONES)]
        figura.add_trace(
            go.Scatter(
                x=curva["timestamp"],
                y=curva["dosis"],
                mode="lines",
                line={"shape": "hv", "width": 2.4, "color": color},
                name=f"{farmaco} · {configuraciones[farmaco]['etiqueta']}",
                hoverinfo="skip",
            ),
            row=fila,
            col=1,
        )
        eventos = eventos_por_farmaco[farmaco]
        if not eventos.empty:
            figura.add_trace(
                go.Scatter(
                    x=eventos["timestamp"],
                    y=eventos["dosis_evento"],
                    mode="markers",
                    marker={
                        "size": 7,
                        "color": color,
                        "line": {"color": "#1f2d3a", "width": 1.2},
                    },
                    cliponaxis=False,
                    customdata=_texto_hover_eventos_perfusion(
                        eventos,
                        configuraciones[farmaco],
                    ),
                    hovertemplate="%{customdata}<extra></extra>",
                    name=f"{farmaco} · cambios registrados",
                    showlegend=False,
                ),
                row=fila,
                col=1,
            )
        figura.update_yaxes(
            title_text=configuraciones[farmaco]["etiqueta"],
            range=_rango_y_con_margen(curva["dosis"]),
            title_standoff=30,
            automargin=True,
            row=fila,
            col=1,
        )

    figura.update_layout(
        height=max(520, 390 * len(curvas)),
        margin={"l": 210, "r": 70, "t": 110, "b": 125},
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.18,
            "xanchor": "left",
            "x": 0,
        },
        template="plotly_white",
    )
    figura.update_xaxes(type="date", range=[inicio, fin])
    figura.update_xaxes(title_text="Tiempo", row=len(curvas), col=1)
    figura.update_xaxes(automargin=True)
    figura.update_yaxes(automargin=True)
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
                    config=CONFIGURACION_GRAFICO_ICCA,
                )
                if figura is not None
                else html.Div("Sin constantes vitales en este intervalo.", className="icca-sin-datos")
            ),
            html.H3("Análisis clínicos", style={"marginTop": "22px"}),
            _crear_tarjetas_analisis(datos, inicio, fin),
            html.H3("Perfusiones", style={"marginTop": "22px"}),
            html.Div(
                "Cada fármaco muestra la dosis activa documentada. La curva se "
                "mantiene estable hasta que ICCA registra un cambio de dosis.",
                style={"color": "#526170", "marginBottom": "8px"},
            ),
            html.Div(
                "Los saltos indican cambios reales de perfusión; las filas que "
                "solo contienen velocidad de bomba sin dosis no se representan "
                "como dosis administrada.",
                style={"color": "#526170", "marginBottom": "8px"},
            ),
            (
                dcc.Graph(
                    figure=figura_perfusiones,
                    config=CONFIGURACION_GRAFICO_ICCA,
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

