import sys
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import struct

from funciones_aux import *


from matplotlib.colors import LinearSegmentedColormap, PowerNorm



def limpiar_spa_para_dsa(df_spa):
    
    """ 
    Coger el DF del .spa y asegurar que las columnas necesarias sean numéricas.
    
    """
    
    # Copiar el dF original para no modificar el original
    df = df_spa.copy()

    # Definir columnas necesarias para modificar la DSA: SEF, MEF, Calidad de la señal y Potencia total
    # Se utilizan para superponer las curvas y detectar tramos inválidos
    cols = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01"]
    
    # Va columna por columna para ver si está en la lista
    # Convertir los valores a numéricos
   
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    sentinelas = [-327.7, -3276.0, -3276.8, -3276]
    cols_presentes = [c for c in cols if c in df.columns]
    df[cols_presentes] = df[cols_presentes].replace(sentinelas, np.nan)

    return df



def construir_mascara_no_valida(df_spa, umbral_sqi=14):
    
    """ 
    Crea una máscara booleana que marca en qué filas la señal no debe considerarse válida.
    
    """
    # Extrae la columna SQI10 
    sqi = df_spa["SQI10"]
    
    # Extrae TOTPOW08 
    totpow = df_spa["TOTPOW08"]

    """ 
    Se alinean y convierten las filas a True/False: es True si: 
     - SQI10 < 14
     - TOTPOW08 es igual o muy próximo a -327.7
    Basta con que falle una condición para marcar la fila como no válida.
    
    Con números decimales a veces hay pequeñas diferencias de precisión.
    Así se aceptan valores muy cercanos a -327.7, no solo el idéntico.
    """
    mask_no_valida = (sqi < umbral_sqi) | (np.isclose(totpow, -327.7))
    
    return mask_no_valida
    
    
    
def crear_cmap_bis():
    
    """ 
    Crea un colormap personalizado parecido al del BIS
    
    """
    
    # colores
    # Rampa aproximada a la leyenda del monitor BIS
    colores_bis = [
        "#001a8f",  # azul oscuro
        "#004cff",  # azul
        "#00c8ff",  # cian
        "#46e6b2",  # verde-agua
        "#d7ef3c",  # amarillo verdoso
        "#ffe100",  # amarillo
        "#ff8c00",  # naranja
        "#d40000",  # rojo
    ]
    
    # Construcción de un colormapcontinuo a partir de esos colores 
    # Hace que el gradiente tenga 256 niveles de color transicionando entre los 8 definidos
    cmap = LinearSegmentedColormap.from_list("bis_like", colores_bis, N=256)
    
    # qué color usar para valores inválidos
    # cuando en el DF de la dsa haya una fila NaN se pinta de blanco
    cmap.set_bad(color="white")
    return cmap



def alinear_spa_con_tiempo(tiempo, df_spa, columnas=None):
    
    if columnas is None:
        columnas = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01"]

    df_spa = limpiar_spa_para_dsa(df_spa)

    cols = ["Time"] + [c for c in columnas if c in df_spa.columns]

    """
    Alinear el df del .spa con el df de la DSA por tiempo:
     - tiempo, dsa: variables que vienen del .f_a (instantes de tiempo y decibelios según frecuencia)
     - df_spa: DataFrame procedente del .spa. Lo hemos limpiado y quedan las columnas numéricas.
               Están los instantes de tiempo y los valores de los campos 
     
    df_aux: Creación de un dF auxiliar que contiene solo la serie temporal de la DSA
    df_merge: se hace una unión del DF de tiempo con las columnas limpias del dF del .spa
        - on: como las dos tienen las columnas de tiempo en común se fusionan por ahí
        - how="left": conserva todos los tiempos de la DSA, aunque en el .spa falte alguno
    """
    
    df_aux = pd.DataFrame({"Time": tiempo}).reset_index(drop=True)
    df_merge = df_aux.merge(
        df_spa[cols],   # <- aquí estaba el fallo
        on="Time",
        how="left"
    )

    return df_merge



def preparar_dsa_para_plot(tiempo, dsa, df_merge, umbral_sqi=14, umbral_ceros=0.9):
    
    # copiar la matriz de densidad espectral para modificarla. Se copia y convierte a float
    # van a entrar los NaN y hace falta float
    dsa_plot = dsa.copy().astype(float)

    
    # metemos el dF de unión con el tiempo de la dsa y los campos del spa
    # marca las filas que cumplen los requisitos como no válidas
    mask_no_valida = construir_mascara_no_valida(df_merge, umbral_sqi=umbral_sqi)

    """ 
    compara cada celda con el 0 y del true/false (1 y 0) se hace media por filas
    si la media es > a 0.9 (más del 90% son ceros) se marca esa fila como no válida
    
    Si una fila tiene casi todo a cero, probablemente no aporta información útil
    """
    porcentaje_ceros = (dsa_plot == 0).mean(axis=1)
    mask_ceros = porcentaje_ceros > 0.9

    
    """ 
    se calcula la diferencia entre cada tiempo y el anterior (la primera da NaT porque no tiene instante anterior) (se hace una columna)
    se convierten las diferencias a segundos numéricos
    
    si los segundos son >1 se vuelven True esos valores y el resto false (mete false el NaN del inicio)
    
    mira si hay huecos temporales en la grabación si de repente pasas de un segundo a un salto de varios 
    """
    delta_t = tiempo.diff().dt.total_seconds()
    mask_saltos = delta_t.gt(1).fillna(False)

    
    """
    unir las tres condiciones con un OR lógico
    una fila no es válida si :
     - mala calidad/valor no válido según .spa
     - casi todo ceros
     - salto temporal
    """
    mask_total = mask_no_valida | mask_ceros | mask_saltos

    
    # en las filas marcadas como no válidas se sustituyen los valores por NaN (que saldrán en blanco)
    dsa_plot.loc[mask_total.values, :] = np.nan

    return dsa_plot, mask_total



def preparar_escala_color_dsa(dsa_plot, vmin=None, vmax=None, gamma=0.55):
    
    # convierte el DataFrame en una matriz de numPy
    matriz = dsa_plot.values

    # se crea una matriz del mismo tamaño con true/false (si es un valor finito normal o no)
    # se guardan en un vector solo los valores que sean reales (los true)
    vals = matriz[np.isfinite(matriz)]
    
    
    # se calculan los percentiles con los valores del vector
    if vmin is None:
        vmin = np.nanpercentile(vals, 2)
    if vmax is None:
        vmax = np.nanpercentile(vals, 99.5)

        
    """ 
    se controla cómo se reparten los colores sobre los valores de la DSA
     - PowerNorm: transformación no lineal. Reparte los colores con una potencia controlada por gamma.
                  normalización = ((x - vmin) / (vmax - vmin)) ^ gamma
                 
     - gamma: cambia la forma en que los valores intermedios se distribuyen entre vmin y vmax
              gamma = 1: normalización lineal, no hay cambios
              gamma < 1 (0.55): hace que los valores intermedios suban visualmente en la escala
              gamma > 1 (1.2): comprime los intermedios hacia abajo y predominan más los tonos bajos
    
     - vmin: valor mínimo referencia. Lo que sea igual o por debajo va al extremo
     - vmax: valor máximo referencia. Lo que sea igual o por encima va al extremo
    """
    norm = PowerNorm(gamma=gamma, vmin=vmin, vmax=vmax)
    
    # crear el colormap con los colores tipo BIS y blanco para el NaN
    cmap = crear_cmap_bis()

    return matriz, vmin, vmax, norm, cmap



def plot_dsa_pdf_con_spa(tiempo, dsa, df_spa, umbral_sqi=14, vmin=None, vmax=None, gamma=0.55):
    
    """
    DSA vertical estilo PDF usando:
    - DSA del .f_a
    - SEF y MEF del .spa
    - máscara de tramos no válidos
    """

    # 1) Alinear el .spa con el tiempo de la DSA
    df_merge = alinear_spa_con_tiempo(tiempo, df_spa, columnas=["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08"])

    # 2) Preparar la DSA con NaN en tramos no válidos
    dsa_plot, mask_total = preparar_dsa_para_plot(tiempo, dsa, df_merge, umbral_sqi=umbral_sqi, umbral_ceros=0.9)

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
    mask_sef = sef.notna() & (sef >= 0.5) & (sef <= 30)
    mask_mf = mf.notna() & (mf >= 0.5) & (mf <= 30)

    ax.plot(
        sef[mask_sef], tiempo[mask_sef],
        color="white", linewidth=2.0, alpha=0.95, label="SEF"
    )

    ax.plot(
        mf[mask_mf], tiempo[mask_mf],
        color="purple", linewidth=2.0, alpha=0.95, label="MEF"
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
    
    
    
def figura_dsa_y_variables_alineadas(
    tiempo,
    dsa,
    df_spa,
    umbral_sqi=14,
    vmin=None,
    vmax=None,
    gamma=0.55,
    incluir=("EMGLOW01", "BURST", "DB13U01")
):
    """
    Figura conjunta con:
    - DSA horizontal arriba
    - variables debajo
    - ejes temporales perfectamente alineados con sharex=True
    """

    # 1) Alinear .spa con el tiempo de la DSA
    df_merge = alinear_spa_con_tiempo(
        tiempo,
        df_spa,
        columnas=["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01"]
    )

    # 2) Preparar DSA con máscara de invalidez
    dsa_plot, mask_total = preparar_dsa_para_plot(
        tiempo,
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
    mask_sef = sef.notna() & (sef >= 0.5) & (sef <= 30)
    mask_mf = mf.notna() & (mf >= 0.5) & (mf <= 30)

    ax_dsa.plot(
        tiempo[mask_sef], sef[mask_sef],
        color="white", linewidth=2.0, label="SEF"
    )
    ax_dsa.plot(
        tiempo[mask_mf], mf[mask_mf],
        color="#7a1fa2", linewidth=2.0, label="MEF"
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