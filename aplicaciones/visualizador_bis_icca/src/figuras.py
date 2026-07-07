import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.bandas import (
    BANDAS_EEG,
    calcular_densidad_espectral_media_bandas,
    lineas_densidad_bandas,
)

COLORES_BIS = [
    [0.00, "#000080"],
    [0.15, "#0033cc"],
    [0.35, "#25fade"],
    [0.50, "#94ff6e"],
    [0.68, "#f5f532"],
    [0.85, "#FF3F34"],
    [1.00, "#ac0505"],
]

DSA_FA_VMIN_DB = 49.0
DSA_FA_VMAX_DB = 94.0
DSA_FA_GAMMA = 1.0


def _añadir_etiquetas_bandas(fig, xref="x domain", yref="y"):
    """Añade los nombres de las bandas fuera del lateral izquierdo de una DSA."""
    for nombre, limite_inferior, limite_superior in BANDAS_EEG:
        fig.add_annotation(
            x=-0.055,
            y=(limite_inferior + limite_superior) / 2,
            xref=xref,
            yref=yref,
            text=f"<b>{nombre}</b>",
            showarrow=False,
            xanchor="right",
            yanchor="middle",
            font={"size": 11, "color": "#222222"},
        )


def _añadir_resumen_bandas(fig, resumen, titulo, x, y):
    lineas = [
        linea.replace(" ", "\u00a0")
        for linea in lineas_densidad_bandas(resumen)
    ]
    fig.add_annotation(
        x=x,
        y=y,
        xref="paper",
        yref="paper",
        text=f"<b>{titulo}</b><br>" + "<br>".join(lineas),
        showarrow=False,
        xanchor="left",
        yanchor="top",
        align="left",
        bordercolor="#8ea3b7",
        borderwidth=1,
        borderpad=14,
        width=235,
        bgcolor="rgba(247, 249, 251, 0.97)",
        font={
            "size": 12,
            "color": "#20384f",
            "family": "Consolas, Lucida Console, monospace",
        },
    )


def _formatear_sr_hover(sr, etiqueta="SR"):
    textos = []
    for valor in np.asarray(sr, dtype=float):
        if np.isfinite(valor):
            segundos = valor * 63.0 / 100.0
            segundos_texto = f"{segundos:.1f}".replace(".", ",")
            textos.append(
                f"{etiqueta} (últimos 63 s): {valor:.0f} % — "
                f"{segundos_texto} s suprimidos"
            )
        else:
            textos.append(f"{etiqueta} (últimos 63 s): Sin dato")
    return np.asarray(textos, dtype=object)


def _formatear_variable_hover(
    valores,
    etiqueta,
    decimales=1,
    unidad="",
):
    sufijo = f" {unidad}" if unidad else ""
    textos = []
    for valor in np.asarray(valores, dtype=float):
        if np.isfinite(valor):
            textos.append(
                f"{etiqueta}: {valor:.{decimales}f}{sufijo}"
            )
        else:
            textos.append(f"{etiqueta}: Sin dato")
    return np.asarray(textos, dtype=object)


def _combinar_lineas_hover(*lineas):
    return np.asarray(
        ["<br>".join(valores) for valores in zip(*lineas)],
        dtype=object,
    )


def _añadir_hover_exacto(
    fig,
    tiempo,
    fila,
    textos,
    y_referencia,
    color="#607d8b",
    simbolo="circle",
    color_borde=None,
):
    """Añade un punto invisible por segundo para evitar valores vecinos."""
    marcador = {
        "size": 1,
        "opacity": 1,
        "color": color,
        "symbol": simbolo,
    }
    if color_borde is not None:
        marcador["line"] = {"color": color_borde, "width": 1.5}

    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=np.full(len(tiempo), y_referencia, dtype=float),
            mode="markers",
            marker=marcador,
            customdata=np.asarray(textos, dtype=object),
            hovertemplate="%{customdata}<extra></extra>",
            hoverlabel={"namelength": 0},
            showlegend=False,
            name="",
        ),
        row=fila,
        col=1,
    )


def _aplicar_cursor_vertical_compartido(fig, filas):
    """Muestra la guia vertical de hover en todas las filas sincronizadas."""
    for fila in filas:
        fig.update_xaxes(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikecolor="rgba(32, 56, 79, 0.65)",
            spikethickness=1,
            spikedash="dot",
            row=fila,
            col=1,
        )


def crear_figura_dsa(tiempo, frecuencias, dsa, titulo="DSA"):
    """Crea una figura DSA horizontal básica."""
    return crear_figura_dsa_plotly(
        tiempo=tiempo,
        frecuencias=frecuencias,
        matriz=dsa.to_numpy(dtype=float),
        titulo=titulo,
    )


def crear_figura_dsa_plotly(tiempo, frecuencias, matriz, titulo="DSA"):
    fig = go.Figure(
        data=go.Heatmap(
            x=tiempo,
            y=frecuencias,
            z=np.asarray(matriz, dtype=float).T,
            zmin=DSA_FA_VMIN_DB,
            zmax=DSA_FA_VMAX_DB,
            colorscale=COLORES_BIS,
            colorbar={
                "title": "Potencia (dB)",
                "tickmode": "array",
                "tickvals": [DSA_FA_VMIN_DB, DSA_FA_VMAX_DB],
                "ticktext": ["49", "94"],
            },
            hoverongaps=False,
        )
    )

    fig.update_layout(
        title=titulo,
        xaxis_title="Tiempo",
        yaxis_title="Frecuencia (Hz)",
        height=650,
    )
    fig.update_yaxes(range=[0.5, 30])

    for frecuencia in [4, 8, 13]:
        fig.add_hline(y=frecuencia, line_dash="dash", line_color="gray")

    return fig


def _normalizar_potencia(
    matriz,
    vmin=DSA_FA_VMIN_DB,
    vmax=DSA_FA_VMAX_DB,
    gamma=DSA_FA_GAMMA,
):
    matriz = np.asarray(matriz, dtype=float)
    valores = matriz[np.isfinite(matriz)]

    if valores.size == 0:
        raise ValueError("No hay valores válidos en la DSA para representar.")

    if vmin >= vmax:
        raise ValueError("La escala de color no tiene un intervalo válido.")

    normalizada = np.clip((matriz - vmin) / (vmax - vmin), 0, 1)
    normalizada = np.power(normalizada, gamma)
    return normalizada, vmin, vmax


def crear_figura_dsa_unilateral_interactiva(
    tiempo,
    frecuencias,
    matriz,
    sef,
    mef,
    bis,
    emg,
    sr,
    mask_total=None,
    titulo="DSA unilateral",
    vmin=DSA_FA_VMIN_DB,
    vmax=DSA_FA_VMAX_DB,
    gamma=DSA_FA_GAMMA,
    mostrar_controles_tiempo=True,
    modo_panoramico=False,
):
    """
    Crea una DSA Plotly interactiva con SEF, MEF y BIS sincronizados.

    El selector inferior, los botones de intervalo y el zoom modifican un
    único eje temporal compartido por la matriz y el índice BIS.
    """
    tiempo = pd.to_datetime(pd.Series(tiempo), errors="coerce")
    frecuencias = np.asarray(frecuencias, dtype=float)
    matriz = np.asarray(matriz, dtype=float)
    sef = np.asarray(sef, dtype=float).copy()
    mef = np.asarray(mef, dtype=float).copy()
    bis = np.asarray(bis, dtype=float).copy()
    emg = np.asarray(emg, dtype=float).copy()
    sr = np.asarray(sr, dtype=float).copy()
    tiempo_inicio = tiempo.iloc[0]
    tiempo_fin = tiempo.iloc[-1]

    if matriz.shape != (len(tiempo), len(frecuencias)):
        raise ValueError(
            "La matriz DSA debe tener forma tiempo x frecuencia."
        )

    if mask_total is not None:
        mask = np.asarray(mask_total, dtype=bool)
        sef[mask] = np.nan
        mef[mask] = np.nan
        bis[mask] = np.nan
        emg[mask] = np.nan
        sr[mask] = np.nan

    matriz_normalizada, vmin, vmax = _normalizar_potencia(
        matriz,
        vmin=vmin,
        vmax=vmax,
        gamma=gamma,
    )
    resumen_bandas = calcular_densidad_espectral_media_bandas(
        matriz,
        frecuencias,
    )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.14, 0.14],
        vertical_spacing=0.06,
        subplot_titles=(
            titulo or "DSA unilateral",
            "Índice BIS DB13U01",
            "Electromiograma frontal (EMGLOW01)",
        ),
    )
    fig.add_trace(
        go.Heatmap(
            x=tiempo,
            y=frecuencias,
            z=matriz_normalizada.T,
            zmin=0,
            zmax=1,
            colorscale=COLORES_BIS,
            colorbar={
                "title": {"text": "Potencia (dB)", "side": "right"},
                "tickmode": "array",
                "tickvals": [0, 1],
                "ticktext": [f"{vmin:.1f}", f"{vmax:.1f}"],
                "x": 1.01,
            },
            hoverinfo="skip",
            hoverongaps=False,
            name="DSA",
        ),
        row=1,
        col=1,
    )

    # Trazos oscuros inferiores para que SEF y MEF sigan siendo legibles
    # sobre cualquier zona del mapa de color.
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=sef,
            mode="lines",
            line={"color": "rgba(0, 0, 0, 0.75)", "width": 5},
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=sef,
            mode="lines+markers",
            line={"color": "white", "width": 2.3},
            marker={
                "symbol": "square",
                "size": 5,
                "color": "white",
                "line": {"color": "#222222", "width": 1.2},
                "maxdisplayed": 45,
            },
            name="SEF",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        1,
        _formatear_variable_hover(sef, "SEF", 2, "Hz"),
        0.5,
        color="white",
        simbolo="square",
        color_borde="#333333",
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=mef,
            mode="lines",
            line={"color": "rgba(0, 0, 0, 0.7)", "width": 5},
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=mef,
            mode="lines+markers",
            line={"color": "#9c27b0", "width": 2.4},
            marker={
                "symbol": "square",
                "size": 5,
                "color": "#9c27b0",
                "line": {"color": "#222222", "width": 1.0},
                "maxdisplayed": 45,
            },
            name="MEF",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        1,
        _formatear_variable_hover(mef, "MEF", 2, "Hz"),
        0.5,
        color="#9c27b0",
        simbolo="square",
        color_borde="#4a1254",
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        1,
        _formatear_sr_hover(sr),
        0.5,
        color="#e91e63",
        simbolo="circle",
        color_borde="#8e123c",
    )

    for frecuencia in [4, 8, 13]:
        fig.add_hline(
            y=frecuencia,
            row=1,
            col=1,
            line_dash="dash",
            line_color="rgba(80, 80, 80, 0.7)",
            line_width=1,
        )

    _añadir_etiquetas_bandas(fig)
    _añadir_resumen_bandas(
        fig,
        resumen_bandas,
        "Ratio alfa-delta",
        x=1.07,
        y=0.86,
    )

    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=bis,
            mode="lines",
            line={"color": "#1565c0", "width": 2},
            name="BIS",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=2,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        2,
        _formatear_variable_hover(bis, "BIS", 1),
        0,
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=emg,
            mode="lines",
            line={"color": "#ef6c00", "width": 2},
            name="EMG",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=3,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        3,
        _formatear_variable_hover(emg, "EMG", 1, "dB"),
        20,
    )

    fig.update_layout(
        height=1020,
        margin={"l": 170, "r": 390, "t": 160, "b": 80},
        plot_bgcolor="white",
        hovermode="x unified",
        hoversubplots="axis",
        title_x=0.5,
        title_y=0.98,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.10,
            "xanchor": "left",
            "x": 0,
        },
        uirevision=(
            f"dsa-unilateral-{tiempo_inicio.isoformat()}-"
            f"{tiempo_fin.isoformat()}"
        ),
    )
    for fila in [1, 2, 3]:
        fig.update_xaxes(
            type="date",
            range=[tiempo_inicio, tiempo_fin],
            minallowed=tiempo_inicio,
            maxallowed=tiempo_fin,
            row=fila,
            col=1,
        )

    fig.update_xaxes(
        title_text="Tiempo",
        rangeslider={
            "visible": mostrar_controles_tiempo,
            "thickness": 0.09,
            "range": [tiempo_inicio, tiempo_fin],
        },
        row=3,
        col=1,
    )
    _aplicar_cursor_vertical_compartido(fig, [1, 2, 3])
    fig.update_yaxes(
        title_text="Frecuencia (Hz)",
        title_standoff=105,
        automargin=True,
        range=[0.5, 30],
        tickvals=[0.5, 4, 8, 13, 30],
        fixedrange=modo_panoramico,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text="BIS",
        range=[0, 100],
        tickvals=[0, 20, 40, 60, 80, 100],
        fixedrange=modo_panoramico,
        row=2,
        col=1,
    )
    fig.update_yaxes(
        title_text="EMG (dB)",
        range=[20, 80],
        tickvals=[20, 30, 40, 50, 60, 70, 80],
        fixedrange=modo_panoramico,
        row=3,
        col=1,
    )

    if modo_panoramico:
        fig.update_traces(hoverinfo="skip", hovertemplate=None)
        fig.update_layout(hovermode=False, dragmode=False)
        fig.update_xaxes(fixedrange=True)

    return fig


def crear_figura_dsa_bilateral_plotly(
    tiempo,
    frecuencias,
    matriz_izq,
    matriz_der,
    titulo="DSA bilateral",
):
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Hemisferio izquierdo", "Hemisferio derecho"),
        vertical_spacing=0.08,
    )

    fig.add_trace(
        go.Heatmap(
            x=tiempo,
            y=frecuencias,
            z=np.asarray(matriz_izq, dtype=float).T,
            colorscale=COLORES_BIS,
            colorbar={"title": "Potencia (dB)"},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Heatmap(
            x=tiempo,
            y=frecuencias,
            z=np.asarray(matriz_der, dtype=float).T,
            colorscale=COLORES_BIS,
            showscale=False,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(title=titulo, height=850)
    fig.update_yaxes(title_text="Frecuencia (Hz)", range=[0.5, 30], row=1, col=1)
    fig.update_yaxes(title_text="Frecuencia (Hz)", range=[0.5, 30], row=2, col=1)
    fig.update_xaxes(title_text="Tiempo", row=2, col=1)

    for fila in [1, 2]:
        for frecuencia in [4, 8, 13]:
            fig.add_hline(
                y=frecuencia,
                row=fila,
                col=1,
                line_dash="dash",
                line_color="gray",
            )

    return fig


def crear_figura_dsa_bilateral_interactiva(
    tiempo,
    frecuencias,
    matriz_izq,
    matriz_der,
    sef_izq,
    mef_izq,
    sef_der,
    mef_der,
    asimetria,
    bis_izq,
    bis_der,
    emg_izq,
    emg_der,
    sr_izq,
    sr_der,
    vmin=DSA_FA_VMIN_DB,
    vmax=DSA_FA_VMAX_DB,
    gamma=DSA_FA_GAMMA,
    mostrar_controles_tiempo=True,
    modo_panoramico=False,
):
    """
    Crea dos DSA bilaterales con ASYM09 y BIS en un tiempo compartido.
    """
    tiempo = pd.to_datetime(pd.Series(tiempo), errors="coerce")
    frecuencias = np.asarray(frecuencias, dtype=float)
    matriz_izq = np.asarray(matriz_izq, dtype=float)
    matriz_der = np.asarray(matriz_der, dtype=float)
    bis_izq = np.asarray(bis_izq, dtype=float)
    bis_der = np.asarray(bis_der, dtype=float)
    emg_izq = np.asarray(emg_izq, dtype=float)
    emg_der = np.asarray(emg_der, dtype=float)
    sr_izq = np.asarray(sr_izq, dtype=float)
    sr_der = np.asarray(sr_der, dtype=float)

    forma_esperada = (len(tiempo), len(frecuencias))
    if matriz_izq.shape != forma_esperada or matriz_der.shape != forma_esperada:
        raise ValueError(
            "Las matrices bilaterales deben tener forma tiempo x frecuencia."
        )

    valores = np.concatenate(
        [
            matriz_izq[np.isfinite(matriz_izq)],
            matriz_der[np.isfinite(matriz_der)],
        ]
    )
    if valores.size == 0:
        raise ValueError("No hay valores válidos en las DSA bilaterales.")

    if vmin >= vmax:
        raise ValueError("La escala bilateral no tiene un intervalo válido.")

    def normalizar(matriz):
        resultado = np.clip((matriz - vmin) / (vmax - vmin), 0, 1)
        return np.power(resultado, gamma)

    matriz_norm_izq = normalizar(matriz_izq)
    matriz_norm_der = normalizar(matriz_der)
    resumen_bandas_izq = calcular_densidad_espectral_media_bandas(
        matriz_izq,
        frecuencias,
    )
    resumen_bandas_der = calcular_densidad_espectral_media_bandas(
        matriz_der,
        frecuencias,
    )
    tiempo_inicio = tiempo.iloc[0]
    tiempo_fin = tiempo.iloc[-1]

    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.34, 0.10, 0.10, 0.10, 0.34],
        vertical_spacing=0.045,
        subplot_titles=(
            "Hemisferio izquierdo",
            "Asimetría bilateral (ASYM09)",
            "Índice BIS",
            "Electromiograma frontal (EMGLOW01)",
            "Hemisferio derecho",
        ),
    )

    fig.add_trace(
        go.Heatmap(
            x=tiempo,
            y=frecuencias,
            z=matriz_norm_izq.T,
            zmin=0,
            zmax=1,
            colorscale=COLORES_BIS,
            colorbar={
                "title": {"text": "Potencia (dB)", "side": "right"},
                "tickmode": "array",
                "tickvals": [0, 1],
                "ticktext": [f"{vmin:.1f}", f"{vmax:.1f}"],
                "len": 0.85,
                "y": 0.5,
                "x": 1.01,
            },
            hoverinfo="skip",
            hoverongaps=False,
            name="DSA izquierda",
        ),
        row=1,
        col=1,
    )

    def añadir_curva(
        valores_curva,
        fila,
        nombre,
        color,
        borde,
        leyenda,
        grupo_leyenda,
        mostrar_leyenda,
        texto_adicional=None,
    ):
        texto_hover = _formatear_variable_hover(
            valores_curva,
            nombre,
            2,
            "Hz",
        )
        if texto_adicional is not None:
            texto_hover = _combinar_lineas_hover(
                texto_hover,
                texto_adicional,
            )

        fig.add_trace(
            go.Scatter(
                x=tiempo,
                y=valores_curva,
                mode="lines",
                line={"color": borde, "width": 5},
                hoverinfo="skip",
                legendgroup=grupo_leyenda,
                showlegend=False,
            ),
            row=fila,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=tiempo,
                y=valores_curva,
                mode="lines+markers",
                line={"color": color, "width": 2.2},
                marker={
                    "symbol": "square",
                    "size": 4,
                    "color": color,
                    "line": {"color": "#222222", "width": 1},
                    "maxdisplayed": 45,
                },
                name=leyenda,
                legendgroup=grupo_leyenda,
                showlegend=mostrar_leyenda,
                connectgaps=False,
                hoverinfo="skip",
            ),
            row=fila,
            col=1,
        )
        _añadir_hover_exacto(
            fig,
            tiempo,
            fila,
            texto_hover,
            0.5,
            color=color,
            simbolo="square",
            color_borde="#222222",
        )

    añadir_curva(
        sef_izq,
        1,
        "SEF izquierda",
        "white",
        "rgba(0, 0, 0, 0.75)",
        "SEF",
        "sef",
        True,
    )
    añadir_curva(
        mef_izq,
        1,
        "MEF izquierda",
        "#9c27b0",
        "rgba(0, 0, 0, 0.7)",
        "MEF",
        "mef",
        True,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        1,
        _formatear_sr_hover(sr_izq, "SR izquierda"),
        0.5,
        color="#e91e63",
        simbolo="circle",
        color_borde="#8e123c",
    )

    asimetria = np.asarray(asimetria, dtype=float)
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=asimetria,
            mode="lines",
            line={"color": "#e67e22", "width": 2},
            name="ASYM09",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=2,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        2,
        _formatear_variable_hover(asimetria, "ASYM09", 2),
        0,
    )

    valores_asym = asimetria[np.isfinite(asimetria)]
    referencia_asym = 0 if valores_asym.size and valores_asym.min() < 0 else 50
    fig.add_hline(
        y=referencia_asym,
        row=2,
        col=1,
        line_color="rgba(60, 60, 60, 0.8)",
        line_width=1,
        line_dash="dash",
    )

    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=bis_izq,
            mode="lines",
            line={"color": "#1565c0", "width": 2},
            name="BIS izquierda",
            legendgroup="bis",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=3,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        3,
        _formatear_variable_hover(
            bis_izq,
            "BIS izquierda",
            1,
        ),
        0,
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=bis_der,
            mode="lines",
            line={"color": "#c62828", "width": 2},
            name="BIS derecha",
            legendgroup="bis",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=3,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        3,
        _formatear_variable_hover(
            bis_der,
            "BIS derecha",
            1,
        ),
        0,
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=emg_izq,
            mode="lines",
            line={"color": "#e91e63", "width": 2},
            name="EMG izquierda",
            legendgroup="emg",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=4,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        4,
        _formatear_variable_hover(
            emg_izq,
            "EMG izquierda",
            1,
            "dB",
        ),
        20,
    )
    fig.add_trace(
        go.Scatter(
            x=tiempo,
            y=emg_der,
            mode="lines",
            line={"color": "#6d4c41", "width": 2},
            name="EMG derecha",
            legendgroup="emg",
            connectgaps=False,
            hoverinfo="skip",
        ),
        row=4,
        col=1,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        4,
        _formatear_variable_hover(
            emg_der,
            "EMG derecha",
            1,
            "dB",
        ),
        20,
    )

    fig.add_trace(
        go.Heatmap(
            x=tiempo,
            y=frecuencias,
            z=matriz_norm_der.T,
            zmin=0,
            zmax=1,
            colorscale=COLORES_BIS,
            showscale=False,
            hoverinfo="skip",
            hoverongaps=False,
            name="DSA derecha",
        ),
        row=5,
        col=1,
    )
    añadir_curva(
        sef_der,
        5,
        "SEF derecha",
        "white",
        "rgba(0, 0, 0, 0.75)",
        "SEF",
        "sef",
        False,
    )
    añadir_curva(
        mef_der,
        5,
        "MEF derecha",
        "#9c27b0",
        "rgba(0, 0, 0, 0.7)",
        "MEF",
        "mef",
        False,
    )
    _añadir_hover_exacto(
        fig,
        tiempo,
        5,
        _formatear_sr_hover(sr_der, "SR derecha"),
        0.5,
        color="#e91e63",
        simbolo="circle",
        color_borde="#8e123c",
    )

    for fila in [1, 5]:
        for frecuencia in [4, 8, 13]:
            fig.add_hline(
                y=frecuencia,
                row=fila,
                col=1,
                line_dash="dash",
                line_color="rgba(80, 80, 80, 0.7)",
                line_width=1,
            )

    _añadir_etiquetas_bandas(fig, xref="x domain", yref="y")
    _añadir_etiquetas_bandas(fig, xref="x5 domain", yref="y5")
    _añadir_resumen_bandas(
        fig,
        resumen_bandas_izq,
        "Ratio alfa-delta izquierdo",
        x=1.07,
        y=0.93,
    )
    _añadir_resumen_bandas(
        fig,
        resumen_bandas_der,
        "Ratio alfa-delta derecho",
        x=1.07,
        y=0.34,
    )

    fig.update_layout(
        height=1450,
        margin={"l": 170, "r": 390, "t": 170, "b": 80},
        plot_bgcolor="white",
        hovermode="x unified",
        hoversubplots="axis",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.10,
            "xanchor": "left",
            "x": 0,
        },
        uirevision=(
            f"dsa-bilateral-{tiempo_inicio.isoformat()}-"
            f"{tiempo_fin.isoformat()}"
        ),
    )

    fig.update_yaxes(
        title_text="Frecuencia (Hz)",
        title_standoff=105,
        automargin=True,
        range=[0.5, 30],
        tickvals=[0.5, 4, 8, 13, 30],
        row=1,
        col=1,
    )
    fig.update_yaxes(title_text="ASYM09", row=2, col=1)
    if valores_asym.size:
        if valores_asym.min() < 0:
            fig.update_yaxes(range=[-100, 100], row=2, col=1)
        else:
            fig.update_yaxes(range=[0, 100], row=2, col=1)
    fig.update_yaxes(
        title_text="BIS",
        range=[0, 100],
        tickvals=[0, 20, 40, 60, 80, 100],
        row=3,
        col=1,
    )
    fig.update_yaxes(
        title_text="EMG (dB)",
        range=[20, 80],
        tickvals=[20, 30, 40, 50, 60, 70, 80],
        row=4,
        col=1,
    )
    fig.update_yaxes(
        title_text="Frecuencia (Hz)",
        title_standoff=105,
        automargin=True,
        range=[0.5, 30],
        tickvals=[0.5, 4, 8, 13, 30],
        row=5,
        col=1,
    )

    for fila in [1, 2, 3, 4, 5]:
        fig.update_xaxes(
            type="date",
            range=[tiempo_inicio, tiempo_fin],
            minallowed=tiempo_inicio,
            maxallowed=tiempo_fin,
            row=fila,
            col=1,
        )

    fig.update_xaxes(
        title_text="Tiempo",
        rangeslider={
            "visible": mostrar_controles_tiempo,
            "thickness": 0.06,
            "range": [tiempo_inicio, tiempo_fin],
        },
        row=5,
        col=1,
    )
    _aplicar_cursor_vertical_compartido(fig, [1, 2, 3, 4, 5])

    if modo_panoramico:
        fig.update_traces(hoverinfo="skip", hovertemplate=None)
        fig.update_layout(hovermode=False, dragmode=False)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)

    return fig
