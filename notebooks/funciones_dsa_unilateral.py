import pandas as pd
import numpy as np

from funciones_dsa import obtener_hora_inicio_desde_spa


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


def limpiar_spa_unilateral(df_spa):
    """
    Limpia y estandariza el .spa para modo unilateral.

    Usa las variables procesadas del canal recomendado por el fabricante:
    columnas acabadas en _3.
    """

    df, _ = obtener_hora_inicio_desde_spa(df_spa)
    df = df.reset_index(drop=True)

    mapeo = {
        "SEF08": "SEF08_3",
        "MEDFRQ08": "MEDFRQ08_3",
        "SQI10": "SQI10_3",
        "TOTPOW08": "TOTPOW08_3",
        "EMGLOW01": "EMGLOW01_3",
        "SR12": "SR12_3",
        "ST": "ST",
        "DB13U01": "DB13U01_3",
        "ARTF2": "ARTF2_3",
    }

    df_out = pd.DataFrame()
    df_out["Time"] = df["Time"]

    for nombre_estandar, nombre_original in mapeo.items():
        if nombre_original in df.columns:
            df_out[nombre_estandar] = pd.to_numeric(df[nombre_original], errors="coerce")
        else:
            df_out[nombre_estandar] = np.nan
            print(f"Advertencia: no se encontró la columna {nombre_original}")

    # Compatibilidad con funciones antiguas que esperan BURST
    df_out["BURST"] = df_out["SR12"]

    sentinelas = [-327.7, -3276.0, -3276.8, -3276, -32767, -32768]
    cols_num = [c for c in df_out.columns if c != "Time"]
    df_out[cols_num] = df_out[cols_num].replace(sentinelas, np.nan)

    return df_out