import pandas as pd
import numpy as np

from matplotlib.colors import PowerNorm
import struct


from funciones_dsa import (
    obtener_hora_inicio_desde_spa,
    crear_cmap_bis
)


def leer_r4a(archivo_r4a, escala_uv,
    offset, 
    fs=128):
    """
    Lee un archivo .r4a del BIS bilateral.

    Estructura:
    - 4 canales
    - int16 little-endian
    - canales intercalados: ch1, ch2, ch3, ch4, ch1, ch2, ch3, ch4...
    - escala: 0.0511 µV/step
    """

    datos = np.fromfile(archivo_r4a, dtype="<i2")

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
    
    canal_1_uV = canal_1_raw * escala_uv + offset
    canal_2_uV = canal_2_raw * escala_uv + offset
    canal_3_uV = canal_3_raw * escala_uv + offset
    canal_4_uV = canal_4_raw * escala_uv + offset
    

    df_eeg = pd.DataFrame({
        "tiempo_s": tiempo_s,

        "canal_1_raw": canal_1_raw,
        "canal_2_raw": canal_2_raw,
        "canal_3_raw": canal_3_raw,
        "canal_4_raw": canal_4_raw,

        "canal_1_uV": canal_1_uV,
        "canal_2_uV": canal_2_uV,
        "canal_3_uV": canal_3_uV,
        "canal_4_uV": canal_4_uV
    })

    return df_eeg



def leer_inicio_ta(ruta_ta):
    """
    Lee el archivo .t_a y devuelve la fecha/hora de inicio real
    del archivo de ondas crudas.

    El .t_a suele contener una única línea tipo:
        04/03/2010 17:47:21
    """

    with open(ruta_ta, "r", encoding="latin1") as f:
        linea = f.readline().strip()

    inicio_raw = pd.to_datetime(
        linea,
        dayfirst=False,
        errors="coerce"
    )

    if pd.isna(inicio_raw):
        # Segundo intento por si viniera en formato europeo
        inicio_raw = pd.to_datetime(
            linea,
            dayfirst=True,
            errors="coerce"
        )

    if pd.isna(inicio_raw):
        raise ValueError(
            f"No se pudo interpretar la fecha/hora del archivo .t_a: {linea}"
        )

    return inicio_raw


# -------------------------------------------- archivo spa -------------------------------------------------

def limpiar_spa_bilateral(df_spa):
    """
    Limpia y estandariza el .spa para modo bilateral.
    Genera columnas separadas para lado izquierdo y derecho.
    """

    df, _ = obtener_hora_inicio_desde_spa(df_spa)
    df = df.reset_index(drop=True)

    columnas_izq = [
        "SR12", "SEF08", "MEDFRQ08", "BISBIT00", "DB13U01",
        "DB11U04", "B34U05", "TOTPOW08", "EMGLOW01",
        "SQI10", "IMPEDNCE", "ARTF2", "BURST", "ST"
    ]

    columnas_der = [
        "SR12_3", "SEF08_3", "MEDFRQ08_3", "BISBIT00_3", "DB13U01_3",
        "DB11U04_3", "B34U05_3", "TOTPOW08_3", "EMGLOW01_3",
        "SQI10_3", "IMPEDNCE_3", "ARTF2_3", "BURST_3", "ST_3"
    ]

    df_out = pd.DataFrame()
    df_out["Time"] = df["Time"]
    df_out["SpSmooth"] = df["SpSmooth"]

    for col in columnas_izq:
        col_out = f"{col}_izq"

        if col in df.columns:
            df_out[col_out] = pd.to_numeric(df[col], errors="coerce")
        else:
            df_out[col_out] = np.nan
            print(f"Advertencia: no se encontró la columna izquierda {col}")

    for col in columnas_der:
        base = col.replace("_3", "")
        col_out = f"{base}_der"

        if col in df.columns:
            df_out[col_out] = pd.to_numeric(df[col], errors="coerce")
        else:
            df_out[col_out] = np.nan
            print(f"Advertencia: no se encontró la columna derecha {col}")

    if "ASYM09" in df.columns:
        df_out["ASYM09"] = pd.to_numeric(df["ASYM09"], errors="coerce")
    else:
        df_out["ASYM09"] = np.nan
        print("Advertencia: no se encontró la columna ASYM09")

    sentinelas = [-327.7, -3276.0, -3276.8, -3276, -32767, -32768]
    cols_num = [c for c in df_out.columns if c != "Time"]
    df_out[cols_num] = df_out[cols_num].replace(sentinelas, np.nan)

    df_out["modo_spa"] = "bilateral"

    return df_out


def extraer_lado_spa_bilateral(df_spa_bilat, lado="izq", verbose=True):
    """
    Extrae un lado del .spa bilateral y lo convierte a nombres estándar.
    """

    if lado not in ["izq", "der"]:
        raise ValueError("lado debe ser 'izq' o 'der'")

    df = pd.DataFrame()
    df["Time"] = df_spa_bilat["Time"]

    variables = [
        "SR12", "SEF08", "MEDFRQ08", "BISBIT00", "DB13U01",
        "DB11U04", "B34U05", "TOTPOW08", "EMGLOW01",
        "SQI10", "IMPEDNCE", "ARTF2", "BURST", "ST"
    ]

    for var in variables:
        col_lado = f"{var}_{lado}"

        if col_lado in df_spa_bilat.columns:
            df[var] = df_spa_bilat[col_lado]
        else:
            df[var] = np.nan
            if verbose:
                print(f"Advertencia: no se encontró {col_lado}")

    if "ASYM09" in df_spa_bilat.columns:
        df["ASYM09"] = df_spa_bilat["ASYM09"]

    df["modo_spa"] = f"bilateral_{lado}"

    return df



def obtener_inicio_spa(df_spa, columna_time="Time"):
    """
    Obtiene la primera fecha/hora válida de la columna Time del .spa.

    Se aplica strip() para eliminar espacios invisibles al inicio o al final,
    ya que los campos del .spa pueden tener longitud fija y venir rellenados.
    """

    tiempos_raw = df_spa[columna_time].astype(str).str.strip()

    tiempos_spa = pd.to_datetime(
        tiempos_raw,
        dayfirst=False,
        errors="coerce"
    )

    # Segundo intento por si el formato viniera en día/mes/año
    if tiempos_spa.isna().mean() > 0.5:
        tiempos_spa = pd.to_datetime(
            tiempos_raw,
            dayfirst=True,
            errors="coerce"
        )

    tiempos_spa = tiempos_spa.dropna()

    if len(tiempos_spa) == 0:
        raise ValueError(
            f"No se encontró ninguna fecha/hora válida en la columna {columna_time} del .spa."
        )

    return tiempos_spa.iloc[0]



def recortar_raw_segun_ta_y_spa(
    df_raw,
    ruta_ta,
    df_spa,
    columna_time="Time",
    fs=128,
    verbose=True
):
    """
    Alinea el EEG crudo con el archivo .spa usando el .t_a.

    Casos:
    - Si el raw empieza antes que el .spa:
        se recortan muestras iniciales del raw.
    - Si el .spa empieza antes que el raw:
        se añaden muestras NaN al inicio del raw, porque esos segundos
        no existen en el archivo crudo.

    Devuelve:
    - df_raw_alineado: raw con duración igual al .spa.
    """

    inicio_raw = leer_inicio_ta(ruta_ta)
    inicio_spa = obtener_inicio_spa(df_spa, columna_time=columna_time)

    desfase_s = (inicio_spa - inicio_raw).total_seconds()

    n_segundos_spa = len(df_spa)
    muestras_objetivo = int(n_segundos_spa * fs)

    df_raw = df_raw.copy().reset_index(drop=True)

    # Guardar columnas originales
    columnas_raw = df_raw.columns.tolist()

    # ------------------------------------------------------------
    # Caso 1: el raw empieza antes que el .spa
    # ------------------------------------------------------------
    if desfase_s >= 0:

        muestras_recorte_inicio = int(round(desfase_s * fs))

        inicio = muestras_recorte_inicio
        fin = inicio + muestras_objetivo

        df_raw_alineado = df_raw.iloc[inicio:fin].copy().reset_index(drop=True)

        accion = "recorte_inicio"
        muestras_nan_inicio = 0
        muestras_recortadas_inicio = muestras_recorte_inicio

    # ------------------------------------------------------------
    # Caso 2: el .spa empieza antes que el raw
    # ------------------------------------------------------------
    else:

        segundos_faltantes_inicio = abs(desfase_s)
        muestras_nan_inicio = int(round(segundos_faltantes_inicio * fs))

        # Crear bloque NaN inicial con las mismas columnas
        df_nan_inicio = pd.DataFrame(
            np.nan,
            index=np.arange(muestras_nan_inicio),
            columns=columnas_raw
        )

        # Concatenar NaN inicial + raw real
        df_raw_expandido = pd.concat(
            [df_nan_inicio, df_raw],
            ignore_index=True
        )

        # Recortar a la duración del .spa
        df_raw_alineado = df_raw_expandido.iloc[:muestras_objetivo].copy().reset_index(drop=True)

        accion = "relleno_nan_inicio"
        muestras_recortadas_inicio = 0

    # ------------------------------------------------------------
    # Si aun así falta señal al final, rellenar con NaN
    # ------------------------------------------------------------

    if len(df_raw_alineado) < muestras_objetivo:

        muestras_faltantes_final = muestras_objetivo - len(df_raw_alineado)

        df_nan_final = pd.DataFrame(
            np.nan,
            index=np.arange(muestras_faltantes_final),
            columns=columnas_raw
        )

        df_raw_alineado = pd.concat(
            [df_raw_alineado, df_nan_final],
            ignore_index=True
        )

    else:
        muestras_faltantes_final = 0

    # ------------------------------------------------------------
    # Reconstruir tiempo_s si existe o si quieres tenerlo actualizado
    # ------------------------------------------------------------

    if "tiempo_s" in df_raw_alineado.columns:
        df_raw_alineado["tiempo_s"] = np.arange(len(df_raw_alineado)) / fs

    # ------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------

    if verbose:
        print("=== Alineación temporal raw vs spa ===")
        print("Inicio raw (.t_a):", inicio_raw)
        print("Inicio .spa:", inicio_spa)
        print("Desfase spa - raw:", desfase_s, "s")
        print("Acción aplicada:", accion)
        print("Filas .spa:", n_segundos_spa)
        print("Muestras objetivo:", muestras_objetivo)
        print("Muestras raw originales:", len(df_raw))
        print("Muestras recortadas al inicio:", muestras_recortadas_inicio)
        print("Muestras NaN añadidas al inicio:", muestras_nan_inicio)
        print("Muestras NaN añadidas al final:", muestras_faltantes_final)
        print("Muestras raw alineado:", len(df_raw_alineado))
        print("Duración raw alineado:", len(df_raw_alineado) / fs, "s")

    return df_raw_alineado


# -------------------------------------------------------------------------------------------------------

def preparar_escala_color_dsa_bilateral(
    dsa_plot_1,
    dsa_plot_2,
    vmin=None,
    vmax=None,
    gamma=0.55,
    percentil_min=2,
    percentil_max=99.5
):
    """
    Prepara una escala de color común para dos matrices DSA bilaterales.

    Si vmin y vmax se pasan manualmente, usa esos valores.
    Si no, calcula vmin/vmax con percentiles conjuntos de ambas matrices.

    Devuelve:
    - matriz_1
    - matriz_2
    - vmin
    - vmax
    - norm
    - cmap
    """

    matriz_1 = dsa_plot_1.to_numpy(dtype=float)
    matriz_2 = dsa_plot_2.to_numpy(dtype=float)

    vals_1 = matriz_1[np.isfinite(matriz_1)]
    vals_2 = matriz_2[np.isfinite(matriz_2)]

    vals = np.concatenate([vals_1, vals_2])

    if len(vals) == 0:
        raise ValueError(
            "No hay valores válidos en ninguna de las dos DSA bilaterales."
        )

    if vmin is None:
        vmin = np.nanpercentile(vals, percentil_min)

    if vmax is None:
        vmax = np.nanpercentile(vals, percentil_max)

    norm = PowerNorm(
        gamma=gamma,
        vmin=vmin,
        vmax=vmax
    )

    cmap = crear_cmap_bis()

    # Importante si la función crear_cmap_bis no lo hace ya
    try:
        cmap.set_bad("white")
    except Exception:
        pass

    return matriz_1, matriz_2, vmin, vmax, norm, cmap