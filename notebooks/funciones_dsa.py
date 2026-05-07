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

from scipy.stats import pearsonr, spearmanr


from scipy.signal import welch
from matplotlib.colors import LinearSegmentedColormap, PowerNorm




def limpiar_spa_para_dsa(df_spa):
    
    """ 
    Coger el DF del .spa y asegurar que las columnas necesarias sean numéricas.
    
    """
    
    # Copiar el dF original para no modificar el original
    df = df_spa.copy()

    # Definir columnas necesarias para modificar la DSA: SEF, MEF, Calidad de la señal y Potencia total
    # Se utilizan para superponer las curvas y detectar tramos inválidos
    cols = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01", "ASYM09"]
    
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
        columnas = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01", "ASYM09"]

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
        df_spa[cols],   
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
    
    
    
def plot_dsa_horizontal(dsa_plot_hor, tiempo, sef_hor=None, mf_hor=None, titulo="DSA horizontal", xlabel="Tiempo", ylabel="Frecuencia (Hz)", mostrar=True):
    """
    Dibuja una DSA horizontal con:
    - mapa de calor
    - curvas SEF y MEF
    - nombres de bandas (Delta, Theta, Alpha, Beta)
    - barra de color

    Parámetros
    ----------
    dsa_plot_hor : DataFrame
        DataFrame con tiempo en filas y frecuencias en columnas.
    tiempo : array-like o Serie
        Vector temporal del eje X.
    sef_hor : array-like o Serie, opcional
        Curva SEF.
    mf_hor : array-like o Serie, opcional
        Curva MEF.
    titulo : str
        Título de la figura.
    xlabel : str
        Etiqueta eje X.
    ylabel : str
        Etiqueta eje Y.
    mostrar : bool
        Si True, hace plt.show().

    Devuelve
    --------
    fig, ax, ax_band, cax
    """

    # 1) Escala de color
    _, vmin, vmax, norm, cmap = preparar_escala_color_dsa(dsa_plot_hor)

    # Para horizontal: filas = frecuencia, columnas = tiempo
    matriz_hor = dsa_plot_hor.T.values

    # 2) Crear figura
    fig = plt.figure(figsize=(20, 8), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[20, 1.5, 0.8], wspace=0.08)

    ax = fig.add_subplot(gs[0, 0])       # DSA
    ax_band = fig.add_subplot(gs[0, 1])  # bandas
    cax = fig.add_subplot(gs[0, 2])      # colorbar

    # 3) Límites reales de ejes
    x0 = mdates.date2num(tiempo.iloc[0] if hasattr(tiempo, "iloc") else tiempo[0])
    x1 = mdates.date2num(tiempo.iloc[-1] if hasattr(tiempo, "iloc") else tiempo[-1])
    y0 = dsa_plot_hor.columns.min()
    y1 = dsa_plot_hor.columns.max()

    # 4) Dibujar DSA
    im = ax.imshow(
        matriz_hor,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    # 5) Curvas SEF y MEF
    if sef_hor is not None:
        mask_sef_hor = sef_hor.notna() & (sef_hor >= 0.5) & (sef_hor <= 30)
        ax.plot(
            tiempo[mask_sef_hor],
            sef_hor[mask_sef_hor],
            color="white",
            linewidth=2.0,
            label="SEF"
        )

    if mf_hor is not None:
        mask_mf_hor = mf_hor.notna() & (mf_hor >= 0.5) & (mf_hor <= 30)
        ax.plot(
            tiempo[mask_mf_hor],
            mf_hor[mask_mf_hor],
            color="#7a1fa2",
            linewidth=2.0,
            label="MEF"
        )

    if (sef_hor is not None) or (mf_hor is not None):
        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0,
            frameon=True,
            facecolor="white",
            framealpha=0.8,
            fontsize=9
        )

    # 6) Formato de ejes
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.setp(ax.get_xticklabels(), rotation=45)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)

    # 7) Líneas separadoras de bandas
    for f in [4, 8, 13]:
        ax.axhline(f, color="gray", linestyle="--", linewidth=1, alpha=0.7)

    # 8) Eje lateral con nombres de bandas
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

    # 9) Barra de color
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_ticks([vmin, vmax])
    cbar.set_ticklabels(["Min", "Max"])
    cbar.ax.tick_params(length=0)
    cbar.set_label("Intensidad espectral (dB)", rotation=90, labelpad=12)

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
    dsa_plot, mask_total = preparar_dsa_para_plot(tiempo, 
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




# ------------------------------- Funciones de EEG a DSA Unilateral ----------------------------------------

def leer_r2a(ruta_archivo, fs=128, escala_uv=0.0511):
    """
    Lee un archivo .r2a del BIS.

    Estructura:
    - 2 canales
    - int16 little-endian
    - canales intercalados: ch1, ch2, ch1, ch2...
    - escala: 0.0511 µV/step
    """

    datos = np.fromfile(ruta_archivo, dtype="<i2")

    if len(datos) % 2 != 0:
        datos = datos[:-1]

    datos = datos.reshape(-1, 2)

    canal_1_raw = datos[:, 0]
    canal_2_raw = datos[:, 1]

    canal_1_uV = canal_1_raw * escala_uv
    canal_2_uV = canal_2_raw * escala_uv

    tiempo_s = np.arange(len(canal_1_uV)) / fs

    df_eeg = pd.DataFrame({
        "tiempo_s": tiempo_s,
        "canal_1_raw": canal_1_raw,
        "canal_2_raw": canal_2_raw,
        "canal_1_uV": canal_1_uV,
        "canal_2_uV": canal_2_uV
    })

    return df_eeg



def crear_matriz_dsa_fft_welch_desde_eeg(
    df_eeg,
    fs=128,
    canal="canal_1_uV",
    ventana_seg=2,
    paso_seg=1,
    fmin=0.5,
    fmax=30.0,
    paso_freq=0.5,
    modo="db",
    tiempo_referencia="centro"
):
    """
    Crea una matriz tiempo-frecuencia para DSA desde EEG crudo mediante FFT/Welch.

    Salida:
    - df_dsa: DataFrame con columna tiempo_s y columnas 0.5 ... 30.0
    - frecuencias: array de frecuencias usadas

    modo:
    - "db": potencia en decibelios
    - "potencia": potencia espectral en µV²
    - "densidad": densidad espectral en µV²/Hz
    - "amplitud": amplitud espectral estimada en µV

    tiempo_referencia:
    - "inicio": etiqueta cada fila con el inicio de la ventana
    - "centro": etiqueta cada fila con el centro de la ventana
    - "final": etiqueta cada fila con el final de la ventana
    """

    x = df_eeg[canal].to_numpy(dtype=float)

    nperseg = int(ventana_seg * fs)      # 2 s * 128 Hz = 256 muestras
    paso = int(paso_seg * fs)            # 1 s * 128 Hz = 128 muestras
    nfft = int(fs / paso_freq)           # 128 / 0.5 = 256

    tiempos = []
    espectros = []

    for inicio in range(0, len(x) - nperseg + 1, paso):
        fin = inicio + nperseg
        segmento = x[inicio:fin]

        scaling = "density" if modo in ["densidad", "db_densidad"] else "spectrum"

        f, pxx = welch(
            segmento,
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=0,
            nfft=nfft,
            detrend="constant",
            scaling=scaling
        )

        mascara = (f >= fmin) & (f <= fmax)
        f_sel = f[mascara]
        pxx_sel = pxx[mascara]

        if modo == "db":
            valores = 10 * np.log10(pxx_sel + 1e-12)
        elif modo == "db_densidad":
            valores = 10 * np.log10(pxx_sel + 1e-12)
        elif modo in ["potencia", "densidad"]:
            valores = pxx_sel
        elif modo == "amplitud":
            valores = np.sqrt(pxx_sel)
        else:
            raise ValueError("modo debe ser 'db', 'db_densidad', 'potencia', 'densidad' o 'amplitud'")

        if tiempo_referencia == "inicio":
            tiempo_s = inicio / fs
        elif tiempo_referencia == "centro":
            tiempo_s = (inicio + nperseg / 2) / fs
        elif tiempo_referencia == "final":
            tiempo_s = fin / fs
        else:
            raise ValueError("tiempo_referencia debe ser 'inicio', 'centro' o 'final'")

        tiempos.append(tiempo_s)
        espectros.append(valores)

    df_dsa = pd.DataFrame(
        espectros,
        columns=[f"{freq:.1f}" for freq in f_sel]
    )

    df_dsa.insert(0, "tiempo_s", tiempos)

    return df_dsa, f_sel


def obtener_hora_inicio_desde_spa(df_spa, columna_tiempo="Time"):
    """
    Convierte la columna Time del .spa a datetime, redondea al segundo y devuelve:
    - df_spa preparado
    - hora_inicio
    
    No solamente hay queçobtener hora_inicio, también el df_spa que se usará después tenga Time en formato datetime para que el merge funcione bien.
    """

    df = df_spa.copy()

    if columna_tiempo not in df.columns:
        raise ValueError(f"El DataFrame del .spa no contiene la columna '{columna_tiempo}'.")

    df[columna_tiempo] = pd.to_datetime(
        df[columna_tiempo],
        errors="coerce"
    ).dt.floor("s")

    df = df.dropna(subset=[columna_tiempo])

    if df.empty:
        raise ValueError("No hay tiempos válidos en el .spa.")

    hora_inicio = df[columna_tiempo].min()

    return df, hora_inicio


def adaptar_dsa_reconstruida_para_plot(df_dsa, frecuencias, hora_inicio, insertar_fila_inicial_nan=False):
    """
    Convierte la DSA reconstruida desde EEG crudo al formato esperado
    por las funciones de visualización.

    Entrada:
    - df_dsa: DataFrame con columna tiempo_s y columnas de frecuencia.
    - frecuencias: array con frecuencias.
    - hora_inicio: Timestamp del inicio del registro.
    - insertar_fila_inicial_nan:
        Si True, añade una primera fila en tiempo_s = 0 con NaN.
        Esto es útil cuando la DSA se calculó con tiempo_referencia='centro'
        y la primera estimación real cae 1 segundo después del inicio.

    Salida:
    - tiempo: Serie datetime.
    - dsa: DataFrame solo con columnas espectrales.
    """

    hora_inicio = pd.Timestamp(hora_inicio).floor("s")

    columnas_freq = [f"{f:.1f}" for f in frecuencias]

    columnas_faltantes = [col for col in columnas_freq if col not in df_dsa.columns]
    if columnas_faltantes:
        raise ValueError(f"Faltan columnas de frecuencia en df_dsa: {columnas_faltantes[:5]}...")

    df = df_dsa.copy()

    if insertar_fila_inicial_nan:
        primera_fila = {"tiempo_s": 0.0}

        for col in columnas_freq:
            primera_fila[col] = np.nan

        df = pd.concat(
            [pd.DataFrame([primera_fila]), df],
            ignore_index=True
        )

    tiempo = pd.Series(hora_inicio + pd.to_timedelta(df["tiempo_s"], unit="s"), name="Time").dt.floor("s")

    dsa = df[columnas_freq].copy()

    return tiempo, dsa


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


# -------------------------------------- Funciones de EEG a DSA Bilateral --------------------------------------


def leer_r4a(ruta_archivo, fs=128, escala_uv=0.0511):
    """
    Lee un archivo .r4a del BIS bilateral.

    Estructura:
    - 4 canales
    - int16 little-endian
    - canales intercalados: ch1, ch2, ch3, ch4, ch1, ch2, ch3, ch4...
    - escala: 0.0511 µV/step
    """

    datos = np.fromfile(ruta_archivo, dtype="<i2")

    # Asegurar que el número de valores sea múltiplo de 4
    resto = len(datos) % 4
    if resto != 0:
        datos = datos[:-resto]

    datos = datos.reshape(-1, 4)

    canal_1_raw = datos[:, 0]
    canal_2_raw = datos[:, 1]
    canal_3_raw = datos[:, 2]
    canal_4_raw = datos[:, 3]

    tiempo_s = np.arange(len(canal_1_raw)) / fs

    df_eeg = pd.DataFrame({
        "tiempo_s": tiempo_s,

        "canal_1_raw": canal_1_raw,
        "canal_2_raw": canal_2_raw,
        "canal_3_raw": canal_3_raw,
        "canal_4_raw": canal_4_raw,

        "canal_1_uV": canal_1_raw * escala_uv,
        "canal_2_uV": canal_2_raw * escala_uv,
        "canal_3_uV": canal_3_raw * escala_uv,
        "canal_4_uV": canal_4_raw * escala_uv
    })

    return df_eeg



def preparar_escala_color_dsa_bilateral(dsa_plot_1, dsa_plot_2, gamma=0.55):
    """
    Prepara una escala de color común para dos matrices DSA bilaterales.

    Entrada:
    - dsa_plot_1: DSA del canal 1, con NaN en zonas no válidas.
    - dsa_plot_2: DSA del canal 3, con NaN en zonas no válidas.

    Salida:
    - matriz_1
    - matriz_2
    - vmin
    - vmax
    - norm
    - cmap
    """

    matriz_1 = dsa_plot_1.values
    matriz_2 = dsa_plot_2.values

    vals_1 = matriz_1[np.isfinite(matriz_1)]
    vals_2 = matriz_2[np.isfinite(matriz_2)]

    vals = np.concatenate([vals_1, vals_2])

    vmin = np.nanpercentile(vals, 2)
    vmax = np.nanpercentile(vals, 99.5)

    norm = PowerNorm(gamma=gamma, vmin=vmin, vmax=vmax)
    cmap = crear_cmap_bis()

    return matriz_1, matriz_2, vmin, vmax, norm, cmap


def plot_dsa_bilateral_con_sef_mef(
    tiempo,
    frecuencias,
    matriz_ch1,
    matriz_ch3,
    norm,
    cmap,
    df_merge=None,
    titulo_ch1="DSA bilateral - Canal 1",
    titulo_ch3="DSA bilateral - Canal 3",
    etiqueta_colorbar="Potencia espectral (dB)",
    mostrar_sef=True,
    mostrar_mef=True
):
    """
    Dibuja dos DSA bilaterales:
    - canal 1
    - canal 3

    Ambas se representan con la misma escala de color.
    """

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(15, 9),
        sharex=True,
        sharey=True
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
    axes[0].set_ylim(np.min(frecuencias), np.max(frecuencias))

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
    axes[1].set_ylim(np.min(frecuencias), np.max(frecuencias))

    if df_merge is not None:
        if mostrar_sef and "SEF08" in df_merge.columns:
            axes[0].plot(
                tiempo,
                df_merge["SEF08"],
                color="white",
                linewidth=1.5,
                label="SEF"
            )

            axes[1].plot(
                tiempo,
                df_merge["SEF08"],
                color="white",
                linewidth=1.5,
                label="SEF"
            )

        if mostrar_mef and "MEDFRQ08" in df_merge.columns:
            axes[0].plot(
                tiempo,
                df_merge["MEDFRQ08"],
                color="purple",
                linewidth=1.5,
                label="MEF"
            )

            axes[1].plot(
                tiempo,
                df_merge["MEDFRQ08"],
                color="purple",
                linewidth=1.5,
                label="MEF"
            )

        axes[0].legend(loc="upper right")
        axes[1].legend(loc="upper right")

    cbar = fig.colorbar(
        im2,
        ax=axes,
        orientation="vertical",
        fraction=0.025,
        pad=0.02
    )

    cbar.set_label(etiqueta_colorbar)

    fig.suptitle("DSA bilateral reconstruida desde EEG crudo .r4a", fontsize=14)

    plt.tight_layout()
    plt.show()
    
    
    
# --------------------------------- Funciones calibración ------------------------------------------------


def preparar_matrices_para_comparacion(dsa_1, dsa_2):
    """
    Asegura que las dos DSA tengan:
    - mismas columnas
    - misma longitud
    - columnas en el mismo orden
    """

    dsa_1 = dsa_1.copy()
    dsa_2 = dsa_2.copy()

    # Convertir nombres de columnas a float para evitar diferencias tipo "0.5" vs 0.5
    dsa_1.columns = [float(c) for c in dsa_1.columns]
    dsa_2.columns = [float(c) for c in dsa_2.columns]

    columnas_comunes = sorted(set(dsa_1.columns).intersection(set(dsa_2.columns)))

    n = min(len(dsa_1), len(dsa_2))

    dsa_1 = dsa_1.iloc[:n][columnas_comunes]
    dsa_2 = dsa_2.iloc[:n][columnas_comunes]

    return dsa_1, dsa_2


def zscore_global(df):
    """
    Normaliza toda la matriz con media y desviación típica global, ignorando NaN.
    """
    # convierte la DSA a matriz numérica
    matriz = df.to_numpy(dtype=float)

    # media y desviación típica ignorando NaN
    media = np.nanmean(matriz)
    std = np.nanstd(matriz)

    # aplica la fórmula
    matriz_z = (matriz - media) / std

    return pd.DataFrame(matriz_z, index=df.index, columns=df.columns)


def comparar_dsa_global(dsa_1, dsa_2):
    """
    Calcula métricas globales entre dos matrices DSA.
    Compara solo posiciones donde ambas matrices tienen valores válidos.
    """

    A = dsa_1.to_numpy(dtype=float)
    B = dsa_2.to_numpy(dtype=float)

    mask = np.isfinite(A) & np.isfinite(B)

    A_valid = A[mask]
    B_valid = B[mask]

    if len(A_valid) == 0:
        raise ValueError("No hay valores válidos comunes para comparar.")

    mae = np.mean(np.abs(A_valid - B_valid))
    rmse = np.sqrt(np.mean((A_valid - B_valid) ** 2))
    bias = np.mean(B_valid - A_valid)

    pearson = pearsonr(A_valid, B_valid)[0]
    spearman = spearmanr(A_valid, B_valid)[0]

    return {
        "n_valores_comparados": len(A_valid),
        "MAE": mae,
        "RMSE": rmse,
        "bias_B_menos_A": bias,
        "Pearson": pearson,
        "Spearman": spearman
    }


def correlacion_por_frecuencia(dsa_1, dsa_2):
    """
    Calcula la correlación entre ambas DSA para cada frecuencia.
    """

    resultados = []

    for col in dsa_1.columns:
        a = dsa_1[col].to_numpy(dtype=float)
        b = dsa_2[col].to_numpy(dtype=float)

        mask = np.isfinite(a) & np.isfinite(b)

        if mask.sum() > 2:
            r = pearsonr(a[mask], b[mask])[0]
        else:
            r = np.nan

        resultados.append({
            "frecuencia_Hz": col,
            "correlacion": r
        })

    return pd.DataFrame(resultados)


def correlacion_por_tiempo(dsa_1, dsa_2, tiempo=None):
    """
    Calcula la correlación fila a fila.
    Cada fila representa un instante temporal.
    """

    resultados = []

    for i in range(len(dsa_1)):
        a = dsa_1.iloc[i].to_numpy(dtype=float)
        b = dsa_2.iloc[i].to_numpy(dtype=float)

        mask = np.isfinite(a) & np.isfinite(b)

        if mask.sum() > 2:
            r = pearsonr(a[mask], b[mask])[0]
        else:
            r = np.nan

        resultados.append(r)

    df = pd.DataFrame({"correlacion": resultados})

    if tiempo is not None:
        df.insert(0, "Time", tiempo.iloc[:len(df)].values)

    return df


def probar_suavizado_y_shifts(
    dsa_eeg,
    dsa_fa,
    ventanas_suavizado=(5, 10, 15, 25, 30, 40, 60, 80),
    shifts=range(-60, 61)
):
    resultados = []

    for w in ventanas_suavizado:
        dsa_eeg_suav = dsa_eeg.rolling(
            window=w,
            min_periods=1,
            center=False
        ).mean()

        for shift in shifts:

            if shift < 0:
                A = dsa_eeg_suav.iloc[-shift:].reset_index(drop=True)
                B = dsa_fa.iloc[:len(A)].reset_index(drop=True)

            elif shift > 0:
                A = dsa_eeg_suav.iloc[:-shift].reset_index(drop=True)
                B = dsa_fa.iloc[shift:].reset_index(drop=True)

            else:
                A = dsa_eeg_suav.reset_index(drop=True)
                B = dsa_fa.reset_index(drop=True)

            n = min(len(A), len(B))
            A = A.iloc[:n]
            B = B.iloc[:n]

            A_z = zscore_global(A)
            B_z = zscore_global(B)

            met = comparar_dsa_global(A_z, B_z)

            resultados.append({
                "suavizado_s": w,
                "shift_s": shift,
                "Pearson": met["Pearson"],
                "Spearman": met["Spearman"],
                "MAE": met["MAE"],
                "RMSE": met["RMSE"]
            })

    return pd.DataFrame(resultados)