import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from funciones_dsa import (
    alinear_spa_con_tiempo,
    preparar_dsa_con_mask,
    preparar_escala_color_dsa,
    construir_mascara_no_valida
)



# ------------------------------------------ UNILATERAL ------------------------------------------------------

def plot_dsa_pdf_con_spa(tiempo, dsa, df_spa, umbral_sqi=14, vmin=None, vmax=None, gamma=0.55,  aplicar_clip=False):
    
    """
    DSA vertical estilo PDF usando:
    - DSA del .f_a
    - SEF y MEF del .spa
    - máscara de tramos no válidos
    
    Si aplicar_clip=True y se pasan vmin/vmax, los valores se recortan visualmente a ese rango para imitar mejor la saturación de pantalla.
    """

    # 1) Alinear el .spa con el tiempo de la DSA
    df_merge = alinear_spa_con_tiempo(tiempo, df_spa, columnas=["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08"])

    # 2) Preparar la DSA con NaN en tramos no válidos
    dsa_plot, mask_total = preparar_dsa_con_mask(tiempo, dsa, df_merge, umbral_sqi=umbral_sqi, umbral_ceros=0.9)
    
    
    # 2.5) Recorte visual opcional
    if aplicar_clip and (vmin is not None) and (vmax is not None):
        dsa_plot = dsa_plot.clip(lower=vmin, upper=vmax)
    

    # 3) Preparar matriz y escala de color
    matriz, vmin, vmax, norm, cmap = preparar_escala_color_dsa(dsa_plot, vmin=vmin, vmax=vmax, gamma=gamma)

    # 4) Extraer curvas SEF y MEF
    sef = df_merge["SEF08"]
    mf = df_merge["MEDFRQ08"]

    # 5) Crear figura
    fig, ax = plt.subplots(figsize=(4.8, 10))

    # Límites reales de tiempo y frecuencia
    y0 = mdates.date2num(tiempo.iloc[0])
    y1 = mdates.date2num(tiempo.iloc[-1])
    x0 = dsa_plot.columns.min()
    x1 = dsa_plot.columns.max()

    # 6) Dibujar la DSA
    im = ax.imshow(
        matriz,
        aspect="auto",
        origin="upper",
        extent=[x0, x1, y1, y0],
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    # 7) Formato del eje
    ax.invert_xaxis()
    ax.yaxis_date()
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    ax.set_xlabel("Frecuencia")
    ax.set_ylabel("Tiempo")
    ax.set_title("DSA", loc="left", fontsize=9, pad=6)

    ax.set_xticks([30, 13, 8, 4])
    ax.set_xticklabels(["30Hz", "13Hz", "8Hz", "4Hz"], fontsize=8)

    for f in [13, 8, 4]:
        ax.axvline(f, color="gray", linestyle="--", linewidth=1, alpha=0.7)

    bandas = {
        "Beta":  (13 + 30) / 2,
        "Alpha": (8 + 13) / 2,
        "Theta": (4 + 8) / 2,
        "Delta": (0.5 + 4) / 2,
    }

    for nombre, xpos in bandas.items():
        ax.text(
            xpos, 1.01, nombre,
            transform=ax.get_xaxis_transform(),
            ha="center", va="bottom",
            fontsize=8, rotation=45
        )

    # 8) Dibujar SEF y MEF solo con datos válidos dentro del rango
    sef_plot = sef.copy()
    mf_plot = mf.copy()

    sef_plot[(sef_plot < 0.5) | (sef_plot > 30)] = np.nan
    mf_plot[(mf_plot < 0.5) | (mf_plot > 30)] = np.nan

    sef_plot.loc[mask_total.values] = np.nan
    mf_plot.loc[mask_total.values] = np.nan

    ax.plot(
        sef_plot,
        tiempo,
        color="white",
        linewidth=2.0,
        alpha=0.95,
        label="SEF"
    )

    ax.plot(
        mf_plot,
        tiempo,
        color="purple",
        linewidth=2.0,
        alpha=0.95,
        label="MEF"
    )
    
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.25, 0.92),
        frameon=True,
        facecolor="white",
        framealpha=0.85,
        fontsize=8,
        borderaxespad=0
    )

    # 9) Barra de color
    cbar = plt.colorbar(im, ax=ax, pad=0.03)
    cbar.set_ticks([vmin, vmax])
    cbar.set_ticklabels(["Min", "Max"])
    cbar.ax.tick_params(length=0)
    cbar.set_label("Intensidad espectral (dB)", rotation=90, labelpad=12)

    plt.tight_layout()
    plt.show() 
    
    return fig, ax
   

    
def plot_dsa_con_sef_mef(
    tiempo, frecuencias, matriz, norm, cmap, df_merge=None,
    titulo="DSA reconstruida desde EEG crudo",
    etiqueta_colorbar="Potencia espectral (dB)",
    mostrar_sef=True,
    mostrar_mef=True,
    mostrar=True,
    mask_total=None
):
    """
    Dibuja la DSA y superpone las curvas SEF y MEF si están disponibles.

    Parámetros:
    - tiempo: Serie datetime de la DSA.
    - frecuencias: array de frecuencias.
    - matriz: matriz DSA con forma tiempo x frecuencia.
    - norm: normalización de color.
    - cmap: mapa de color.
    - df_merge: DataFrame alineado con tiempo que contiene SEF08 y MEDFRQ08.
    """

    
    frecuencias = np.asarray(frecuencias, dtype=float)
    
    # Asegurar eje temporal compatible con matplotlib
    x0 = mdates.date2num(tiempo.iloc[0] if hasattr(tiempo, "iloc") else tiempo[0])
    x1 = mdates.date2num(tiempo.iloc[-1] if hasattr(tiempo, "iloc") else tiempo[-1])

    y0 = np.min(frecuencias)
    y1 = np.max(frecuencias)

    # Matriz para horizontal: filas = frecuencia, columnas = tiempo
    matriz_hor = matriz.T

    # Figura con 3 zonas: DSA, bandas, colorbar
    fig = plt.figure(figsize=(20,8), constrained_layout=True)
    gs = fig.add_gridspec(
        1,
        3,
        width_ratios=[20, 1.5, 0.8],
        wspace=0.08
    )

    ax = fig.add_subplot(gs[0, 0])
    ax_band = fig.add_subplot(gs[0, 1])
    cax = fig.add_subplot(gs[0, 2])

    # DSA
    im = ax.imshow(
        matriz_hor,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    # SEF y MEF
    if df_merge is not None:

        if mostrar_sef and "SEF08" in df_merge.columns:
            sef_plot = df_merge["SEF08"].copy()

            # Fuera del rango visible → NaN
            sef_plot[(sef_plot < y0) | (sef_plot > y1)] = np.nan

            # Donde la DSA está en blanco → NaN
            if mask_total is not None:
                sef_plot.loc[np.asarray(mask_total)] = np.nan

            ax.plot(
                tiempo,
                sef_plot,
                color="white",
                linewidth=2.0,
                label="SEF"
            )

        if mostrar_mef and "MEDFRQ08" in df_merge.columns:
            mef_plot = df_merge["MEDFRQ08"].copy()

            # Fuera del rango visible → NaN
            mef_plot[(mef_plot < y0) | (mef_plot > y1)] = np.nan

            # Donde la DSA está en blanco → NaN
            if mask_total is not None:
                mef_plot.loc[np.asarray(mask_total)] = np.nan

            ax.plot(
                tiempo,
                mef_plot,
                color="#7a1fa2",
                linewidth=2.0,
                label="MEF"
            )
            

    # Leyenda
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0,
            frameon=True,
            facecolor="white",
            framealpha=0.8,
            fontsize=9
        )

    # Formato eje X
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.setp(ax.get_xticklabels(), rotation=45)

    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Frecuencia (Hz)")
    ax.set_title(titulo)
    ax.set_ylim(y0, y1)

    # Líneas separadoras de bandas
    for f in [4, 8, 13]:
        ax.axhline(
            f,
            color="gray",
            linestyle="--",
            linewidth=1,
            alpha=0.7
        )

    # Eje lateral con nombres de bandas
    ax_band.set_ylim(y0, y1)
    ax_band.set_xlim(0, 1)
    ax_band.axis("off")

    bandas = {
        "Delta": (0.5 + 4) / 2,
        "Theta": (4 + 8) / 2,
        "Alpha": (8 + 13) / 2,
        "Beta":  (13 + 30) / 2,
    }

    for nombre, ypos in bandas.items():
        ax_band.text(
            0.05,
            ypos,
            nombre,
            va="center",
            ha="left",
            fontsize=9
        )

    # Barra de color
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label(etiqueta_colorbar, rotation=90, labelpad=12)
    

    if mostrar:
        plt.show()

    return fig, ax, ax_band, cax



def figura_dsa_y_variables_alineadas(tiempo, dsa, df_spa, umbral_sqi=14, vmin=None, vmax=None, gamma=0.55, incluir=("EMGLOW01", "BURST", "DB13U01")):
    
    """
    Figura conjunta con:
    - DSA horizontal arriba
    - variables debajo
    - ejes temporales perfectamente alineados con sharex=True
    """

    # 1) Alinear .spa con el tiempo de la DSA
    df_merge = alinear_spa_con_tiempo(tiempo, df_spa,
        columnas=["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01"]
    )

    # 2) Preparar DSA con máscara de invalidez
    dsa_plot, mask_total = preparar_dsa_con_mask(tiempo, 
        dsa,
        df_merge,
        umbral_sqi=umbral_sqi,
        umbral_ceros=0.9
    )
    
    

    # 3) Preparar escala de color
    _, vmin, vmax, norm, cmap = preparar_escala_color_dsa(
        dsa_plot,
        vmin=vmin,
        vmax=vmax,
        gamma=gamma
    )

    # Para horizontal: filas = frecuencia, columnas = tiempo
    matriz = dsa_plot.T.values

    # 4) Variables principales
    sef = df_merge["SEF08"] if "SEF08" in df_merge.columns else pd.Series(index=df_merge.index, dtype=float)
    mf = df_merge["MEDFRQ08"] if "MEDFRQ08" in df_merge.columns else pd.Series(index=df_merge.index, dtype=float)

    # 5) Enmascarar variables inferiores
    # Mejor usar solo la máscara clínica para no borrar demasiado
    mask_clinica = construir_mascara_no_valida(df_merge, umbral_sqi=umbral_sqi)

    vars_plot = df_merge.copy()
    for col in ["SEF08", "MEDFRQ08", "EMGLOW01", "BURST", "DB13U01"]:
        if col in vars_plot.columns:
            vars_plot.loc[mask_clinica.values, col] = np.nan

    # 6) Crear figura
    n_vars = len(incluir)
    fig = plt.figure(figsize=(15, 5 + 2.5 * n_vars), constrained_layout=True)

    gs = fig.add_gridspec(
        nrows=1 + n_vars,
        ncols=3,
        width_ratios=[20, 1.5, 0.9],
        height_ratios=[4] + [1] * n_vars,
        wspace=0.05,
        hspace=0.05
    )

    ax_dsa = fig.add_subplot(gs[0, 0])
    ax_band = fig.add_subplot(gs[0, 1])
    cax = fig.add_subplot(gs[0, 2])

    axes_vars = []
    for i in range(n_vars):
        ax = fig.add_subplot(gs[i + 1, 0], sharex=ax_dsa)
        axes_vars.append(ax)

        ax_dummy_band = fig.add_subplot(gs[i + 1, 1])
        ax_dummy_band.axis("off")

        ax_dummy_cbar = fig.add_subplot(gs[i + 1, 2])
        ax_dummy_cbar.axis("off")

    # 7) Dibujar DSA horizontal
    x0 = mdates.date2num(tiempo.iloc[0])
    x1 = mdates.date2num(tiempo.iloc[-1])
    y0 = dsa_plot.columns.min()
    y1 = dsa_plot.columns.max()

    im = ax_dsa.imshow(
        matriz,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    # 8) Curvas SEF y MEF
    sef_plot = sef.copy()
    mf_plot = mf.copy()

    sef_plot[(sef_plot < 0.5) | (sef_plot > 30)] = np.nan
    mf_plot[(mf_plot < 0.5) | (mf_plot > 30)] = np.nan

    sef_plot.loc[mask_total.values] = np.nan
    mf_plot.loc[mask_total.values] = np.nan

    
    ax_dsa.plot(
        tiempo,
        sef_plot,
        color="white",
        linewidth=2.0,
        alpha=0.95,
        label="SEF"
    )

    ax_dsa.plot(
        tiempo,
        mf_plot,
        color="purple",
        linewidth=2.0,
        alpha=0.95,
        label="MEF"
    )
    
    
    ax_dsa.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
        frameon=True,
        facecolor="white",
        framealpha=0.8,
        fontsize=9
    )

    for f in [4, 8, 13]:
        ax_dsa.axhline(f, color="gray", linestyle="--", linewidth=1, alpha=0.7)

    ax_dsa.set_ylabel("Frecuencia (Hz)")
    ax_dsa.set_title("DSA horizontal")

    # 9) Nombres de bandas
    ax_band.set_ylim(y0, y1)
    ax_band.set_xlim(0, 1)
    ax_band.axis("off")

    bandas = {
        "Delta": (0.5 + 4) / 2,
        "Theta": (4 + 8) / 2,
        "Alpha": (8 + 13) / 2,
        "Beta":  (13 + 30) / 2,
    }

    for nombre, ypos in bandas.items():
        ax_band.text(0.05, ypos, nombre, va="center", ha="left", fontsize=9)

    # 10) Colorbar
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_ticks([vmin, vmax])
    cbar.set_ticklabels(["Min", "Max"])
    cbar.ax.tick_params(length=0)
    cbar.set_label("Intensidad espectral (dB)", rotation=90, labelpad=12)

    # 11) Variables inferiores
    etiquetas = {
        "EMGLOW01": "EMG",
        "BURST": "BURST",
        "DB13U01": "DB13U01",
        "SEF08": "SEF",
        "MEDFRQ08": "MEF",
    }

    limites_y = {
        "SEF08": (0, 30),
        "MEDFRQ08": (0, 30),
        "EMGLOW01": (0, 100),
        "BURST": (0, 100),
        "DB13U01": (0, 100),
    }

    for ax, col in zip(axes_vars, incluir):
        if col in vars_plot.columns and vars_plot[col].notna().sum() > 0:
            ax.plot(vars_plot["Time"], vars_plot[col], linewidth=1.5)

            if col in limites_y:
                ax.set_ylim(limites_y[col])

        ax.set_ylabel(etiquetas.get(col, col))
        ax.grid(True, axis="y", alpha=0.25)

    # 12) Formato temporal compartido
    ax_dsa.xaxis_date()
    ax_dsa.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    for ax in [ax_dsa] + axes_vars:
        ax.set_xlim(tiempo.iloc[0], tiempo.iloc[-1])

    plt.setp(ax_dsa.get_xticklabels(), visible=False)

    for ax in axes_vars[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)

    axes_vars[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.setp(axes_vars[-1].get_xticklabels(), rotation=45)
    axes_vars[-1].set_xlabel("Tiempo")

    return fig, [ax_dsa] + axes_vars



# ---------------------------BILATERAL------------------------------------------------------

def plot_dsa_bilateral_con_sef_mef(
    tiempo,
    frecuencias,
    matriz_ch1,
    matriz_ch3,
    norm,
    cmap,
    df_merge_izq=None,
    df_merge_der=None,
    mask_izq=None,
    mask_der=None,
    titulo_ch1="DSA bilateral - Canal 1",
    titulo_ch3="DSA bilateral - Canal 3",
    etiqueta_colorbar="Potencia espectral (dB)",
    mostrar_sef=True,
    mostrar_mef=True,
    mostrar=True
):
    """
    Dibuja dos DSA bilaterales:
    - canal/lado izquierdo
    - canal/lado derecho

    Ambas se representan con la misma escala de color.
    """

    frecuencias = np.asarray(frecuencias, dtype=float)
    y0 = np.min(frecuencias)
    y1 = np.max(frecuencias)

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(20, 10),
        sharex=True,
        sharey=True,
        constrained_layout=True
    )

    im1 = axes[0].pcolormesh(
        tiempo,
        frecuencias,
        matriz_ch1.T,
        shading="auto",
        cmap=cmap,
        norm=norm
    )

    axes[0].set_title(titulo_ch1)
    axes[0].set_ylabel("Frecuencia (Hz)")
    axes[0].set_ylim(y0, y1)

    im2 = axes[1].pcolormesh(
        tiempo,
        frecuencias,
        matriz_ch3.T,
        shading="auto",
        cmap=cmap,
        norm=norm
    )

    axes[1].set_title(titulo_ch3)
    axes[1].set_ylabel("Frecuencia (Hz)")
    axes[1].set_xlabel("Tiempo")
    axes[1].set_ylim(y0, y1)

    for ax in axes:
        for f in [4, 8, 13]:
            ax.axhline(f, color="gray", linestyle="--", linewidth=1, alpha=0.7)

    if df_merge_izq is not None:
        if mostrar_sef and "SEF08" in df_merge_izq.columns:
            sef_izq = df_merge_izq["SEF08"].copy()
            sef_izq[(sef_izq < y0) | (sef_izq > y1)] = np.nan

            if mask_izq is not None:
                sef_izq.loc[np.asarray(mask_izq)] = np.nan

            axes[0].plot(tiempo, sef_izq, color="white", linewidth=1.5, label="SEF")

        if mostrar_mef and "MEDFRQ08" in df_merge_izq.columns:
            mef_izq = df_merge_izq["MEDFRQ08"].copy()
            mef_izq[(mef_izq < y0) | (mef_izq > y1)] = np.nan

            if mask_izq is not None:
                mef_izq.loc[np.asarray(mask_izq)] = np.nan

            axes[0].plot(tiempo, mef_izq, color="purple", linewidth=1.5, label="MEF")

    if df_merge_der is not None:
        if mostrar_sef and "SEF08" in df_merge_der.columns:
            sef_der = df_merge_der["SEF08"].copy()
            sef_der[(sef_der < y0) | (sef_der > y1)] = np.nan

            if mask_der is not None:
                sef_der.loc[np.asarray(mask_der)] = np.nan

            axes[1].plot(tiempo, sef_der, color="white", linewidth=1.5, label="SEF")

        if mostrar_mef and "MEDFRQ08" in df_merge_der.columns:
            mef_der = df_merge_der["MEDFRQ08"].copy()
            mef_der[(mef_der < y0) | (mef_der > y1)] = np.nan

            if mask_der is not None:
                mef_der.loc[np.asarray(mask_der)] = np.nan

            axes[1].plot(tiempo, mef_der, color="purple", linewidth=1.5, label="MEF")

    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc="upper right")

    axes[1].xaxis_date()
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.setp(axes[1].get_xticklabels(), rotation=45)

    cbar = fig.colorbar(
        im2,
        ax=axes,
        orientation="vertical",
        fraction=0.025,
        pad=0.02
    )

    cbar.set_label(etiqueta_colorbar)

    fig.suptitle("DSA bilateral reconstruida desde EEG crudo .r4a", fontsize=14)

    if mostrar:
        plt.show()

    return fig, axes