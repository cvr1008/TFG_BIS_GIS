import base64
import io
from threading import Lock

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.figure import Figure

from src.bandas import (
    calcular_densidad_espectral_media_bandas,
    lineas_densidad_bandas,
)
from src.figuras import (
    BANDAS_EEG,
    COLORES_BIS,
    DSA_FA_VMAX_DB,
    DSA_FA_VMIN_DB,
)


_LOCK_MATPLOTLIB = Lock()


def _crear_cmap():
    colores = [color for _, color in COLORES_BIS]
    posiciones = [posicion for posicion, _ in COLORES_BIS]
    cmap = LinearSegmentedColormap.from_list(
        "bis_dsa",
        list(zip(posiciones, colores)),
    )
    cmap.set_bad("white")
    return cmap


def _configurar_eje_dsa(ax, titulo):
    ax.set_title(titulo)
    ax.set_ylabel("Frecuencia (Hz)")
    ax.set_ylim(0.5, 30)
    ax.set_yticks([0.5, 4, 8, 13, 30])

    for frecuencia in [4, 8, 13]:
        ax.axhline(
            frecuencia,
            color="gray",
            linestyle="--",
            linewidth=0.8,
            alpha=0.7,
        )

    for nombre, inferior, superior in BANDAS_EEG:
        ax.text(
            -0.025,
            (inferior + superior) / 2,
            nombre,
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=8,
            fontweight="bold",
        )


def _dibujar_dsa(ax, tiempo, frecuencias, matriz, cmap, norm):
    x0 = mdates.date2num(tiempo.iloc[0])
    x1 = mdates.date2num(tiempo.iloc[-1])
    return ax.imshow(
        np.ma.masked_invalid(np.asarray(matriz, dtype=float).T),
        aspect="auto",
        origin="lower",
        extent=[x0, x1, float(frecuencias[0]), float(frecuencias[-1])],
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
        resample=False,
    )


def _dibujar_curvas(ax, tiempo, sef, mef, mostrar_leyenda=True):
    ax.plot(
        tiempo,
        np.asarray(sef, dtype=float),
        color="white",
        linewidth=1.4,
        label="SEF",
        path_effects=[
            pe.Stroke(linewidth=2.8, foreground="black"),
            pe.Normal(),
        ],
    )
    ax.plot(
        tiempo,
        np.asarray(mef, dtype=float),
        color="#9c27b0",
        linewidth=1.4,
        label="MEF",
    )
    if mostrar_leyenda:
        ax.legend(loc="upper right", framealpha=0.85)


def _dibujar_bis(ax, tiempo, bis_izq, bis_der=None):
    ax.plot(
        tiempo,
        np.asarray(bis_izq, dtype=float),
        color="#1565c0",
        linewidth=1.2,
        label="BIS" if bis_der is None else "BIS izquierda",
    )
    if bis_der is not None:
        ax.plot(
            tiempo,
            np.asarray(bis_der, dtype=float),
            color="#c62828",
            linewidth=1.2,
            label="BIS derecha",
        )
    ax.set_title("Índice BIS")
    ax.set_ylabel("BIS")
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")


def _dibujar_emg(ax, tiempo, emg_izq, emg_der=None):
    ax.plot(
        tiempo,
        np.asarray(emg_izq, dtype=float),
        color="#e91e63",
        linewidth=1.2,
        label="EMG" if emg_der is None else "EMG izquierda",
    )
    if emg_der is not None:
        ax.plot(
            tiempo,
            np.asarray(emg_der, dtype=float),
            color="#6d4c41",
            linewidth=1.2,
            label="EMG derecha",
        )
    ax.set_title("Electromiograma frontal (EMGLOW01)")
    ax.set_ylabel("EMG (dB)")
    ax.set_ylim(20, 80)
    ax.set_yticks([20, 30, 40, 50, 60, 70, 80])
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")


def _formatear_tiempo(ax):
    localizador = mdates.AutoDateLocator(minticks=5, maxticks=10)
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M"))
    ax.set_xlabel("Tiempo")


def _figura_a_data_url(fig):
    buffer = io.BytesIO()
    FigureCanvasAgg(fig).print_png(buffer)
    contenido = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{contenido}"


def _dibujar_resumen_bandas(fig, resumen, titulo, x, y):
    texto = f"{titulo}\n\n" + "\n".join(lineas_densidad_bandas(resumen))
    fig.text(
        x,
        y,
        texto,
        ha="left",
        va="top",
        fontsize=10,
        family="monospace",
        color="#20384f",
        bbox={
            "boxstyle": "round,pad=0.7",
            "facecolor": "#f7f9fb",
            "edgecolor": "#8ea3b7",
            "alpha": 0.98,
        },
    )


def crear_panoramica_estatica(registro):
    """
    Representa el registro completo sin reducir ni promediar instantes.

    La salida es un PNG en memoria para que la panorámica no exponga valores
    consultables que la resolución física de la pantalla no puede distinguir.
    """
    tiempo = pd.to_datetime(
        pd.Series(registro["tiempo"]),
        errors="coerce",
    ).reset_index(drop=True)
    frecuencias = np.asarray(registro["frecuencias"], dtype=float)
    cmap = _crear_cmap()
    norm = Normalize(vmin=DSA_FA_VMIN_DB, vmax=DSA_FA_VMAX_DB, clip=True)
    es_reconstruida = registro.get("origen") == "reconstruida"

    with _LOCK_MATPLOTLIB:
        if registro["modo"] == "bilateral":
            fig = Figure(figsize=(23, 16), dpi=130)
            ax_izq, ax_asym, ax_bis, ax_emg, ax_der = fig.subplots(
                nrows=5,
                ncols=1,
                sharex=True,
                gridspec_kw={"height_ratios": [3, 1, 1, 1, 3]},
            )
            fig.subplots_adjust(
                left=0.08,
                right=0.79,
                top=0.93,
                bottom=0.08,
                hspace=0.24,
            )

            imagen = _dibujar_dsa(
                ax_izq,
                tiempo,
                frecuencias,
                registro["matriz_izq"],
                cmap,
                norm,
            )
            _configurar_eje_dsa(ax_izq, "Hemisferio izquierdo")
            _dibujar_curvas(
                ax_izq,
                tiempo,
                registro["sef_izq"],
                registro["mef_izq"],
            )

            asimetria = np.asarray(registro["asimetria"], dtype=float)
            ax_asym.plot(
                tiempo,
                asimetria,
                color="#e67e22",
                linewidth=1.2,
                label="ASYM09",
            )
            validos = asimetria[np.isfinite(asimetria)]
            referencia = 0 if validos.size and validos.min() < 0 else 50
            ax_asym.axhline(
                referencia,
                color="black",
                linestyle="--",
                linewidth=0.8,
                alpha=0.7,
            )
            ax_asym.set_title("Asimetría bilateral (ASYM09)")
            ax_asym.set_ylabel("ASYM09")
            ax_asym.grid(True, alpha=0.25)
            ax_asym.legend(loc="upper right")

            _dibujar_bis(
                ax_bis,
                tiempo,
                registro["bis_izq"],
                registro["bis_der"],
            )
            _dibujar_emg(
                ax_emg,
                tiempo,
                registro["emg_izq"],
                registro["emg_der"],
            )

            _dibujar_dsa(
                ax_der,
                tiempo,
                frecuencias,
                registro["matriz_der"],
                cmap,
                norm,
            )
            _configurar_eje_dsa(ax_der, "Hemisferio derecho")
            _dibujar_curvas(
                ax_der,
                tiempo,
                registro["sef_der"],
                registro["mef_der"],
                mostrar_leyenda=False,
            )
            _formatear_tiempo(ax_der)

            eje_color = fig.add_axes([0.82, 0.18, 0.014, 0.64])
            colorbar = fig.colorbar(imagen, cax=eje_color)
            colorbar.set_label("Potencia (dB)")
            colorbar.set_ticks([DSA_FA_VMIN_DB, DSA_FA_VMAX_DB])
            _dibujar_resumen_bandas(
                fig,
                calcular_densidad_espectral_media_bandas(
                    registro["matriz_izq"],
                    frecuencias,
                ),
                "Ratio alfa-delta izquierdo",
                0.86,
                0.78,
            )
            _dibujar_resumen_bandas(
                fig,
                calcular_densidad_espectral_media_bandas(
                    registro["matriz_der"],
                    frecuencias,
                ),
                "Ratio alfa-delta derecho",
                0.86,
                0.43,
            )
            titulo = (
                "DSA bilateral reconstruida completa"
                if es_reconstruida
                else "DSA bilateral completa"
            )
            fig.suptitle(titulo, fontsize=16)
        else:
            fig = Figure(figsize=(23, 12), dpi=130)
            ax, ax_bis, ax_emg = fig.subplots(
                nrows=3,
                ncols=1,
                sharex=True,
                gridspec_kw={"height_ratios": [4, 1, 1]},
            )
            fig.subplots_adjust(
                left=0.08,
                right=0.79,
                top=0.92,
                bottom=0.10,
                hspace=0.20,
            )
            imagen = _dibujar_dsa(
                ax,
                tiempo,
                frecuencias,
                registro["matriz"],
                cmap,
                norm,
            )
            titulo = (
                "DSA unilateral reconstruida completa"
                if es_reconstruida
                else "DSA unilateral completa"
            )
            _configurar_eje_dsa(ax, titulo)
            _dibujar_curvas(
                ax,
                tiempo,
                registro["sef"],
                registro["mef"],
            )
            _dibujar_bis(ax_bis, tiempo, registro["bis"])
            _dibujar_emg(ax_emg, tiempo, registro["emg"])
            _formatear_tiempo(ax_emg)
            eje_color = fig.add_axes([0.82, 0.20, 0.014, 0.64])
            colorbar = fig.colorbar(imagen, cax=eje_color)
            colorbar.set_label("Potencia (dB)")
            colorbar.set_ticks([DSA_FA_VMIN_DB, DSA_FA_VMAX_DB])
            _dibujar_resumen_bandas(
                fig,
                calcular_densidad_espectral_media_bandas(
                    registro["matriz"],
                    frecuencias,
                ),
                "Ratio alfa-delta",
                0.86,
                0.72,
            )

        return _figura_a_data_url(fig)
