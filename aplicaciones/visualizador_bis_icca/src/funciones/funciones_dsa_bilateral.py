import pandas as pd
import numpy as np

from matplotlib.colors import PowerNorm



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



def preparar_timeline_spa(
    df_spa,
    columna_time="Time",
    resolver_duplicados="last",
    verbose=True
):
    """
    Crea la línea temporal de referencia a partir del archivo .spa.

    Esta timeline será la referencia común para:
    - raw .r2a/.r4a
    - DSA reconstruida
    - .f_a, si existe

    Devuelve:
    - timeline_spa: Serie temporal sin duplicados.
    """

    tiempos = pd.to_datetime(
        df_spa[columna_time].astype(str).str.strip(),
        errors="coerce"
    )

    df_time = pd.DataFrame({"Time": tiempos})
    df_time = df_time.dropna(subset=["Time"])

    if len(df_time) == 0:
        raise ValueError("No se encontraron tiempos válidos en el .spa.")

    n_duplicados = df_time["Time"].duplicated().sum()

    if n_duplicados > 0:
        if verbose:
            print(
                f"Aviso: el .spa contiene {n_duplicados} tiempos duplicados. "
                f"Estrategia usada: {resolver_duplicados}."
            )

        if resolver_duplicados == "last":
            df_time = (
                df_time
                .sort_values("Time")
                .drop_duplicates(subset="Time", keep="last")
                .reset_index(drop=True)
            )

        elif resolver_duplicados == "first":
            df_time = (
                df_time
                .sort_values("Time")
                .drop_duplicates(subset="Time", keep="first")
                .reset_index(drop=True)
            )

        else:
            raise ValueError("resolver_duplicados debe ser 'last' o 'first'.")

    else:
        df_time = df_time.reset_index(drop=True)

    timeline_spa = df_time["Time"].reset_index(drop=True)

    if verbose:
        print("=== Timeline .spa ===")
        print("Inicio .spa:", timeline_spa.iloc[0])
        print("Fin .spa:", timeline_spa.iloc[-1])
        print("N segundos .spa:", len(timeline_spa))

    return timeline_spa



def ajustar_dsa_a_timeline_spa(
    tiempo_dsa,
    dsa,
    timeline_spa,
    nombre="DSA",
    verbose=True
):
    """
    Ajusta una matriz DSA a la timeline oficial del .spa.

    Regla:
    - Si tiempo_dsa y timeline_spa coinciden, no modifica nada.
    - Si la DSA empieza antes que el .spa, se recorta.
    - Si la DSA empieza después que el .spa, se rellenan filas con NaN.
    - Si la DSA termina antes que el .spa, se rellenan filas con NaN.
    - Si la DSA termina después que el .spa, se recorta.

    Devuelve:
    - dsa_ajustada: DataFrame con la misma longitud que timeline_spa.
    """

    tiempo_dsa = pd.to_datetime(
        pd.Series(tiempo_dsa).astype(str).str.strip(),
        errors="coerce"
    ).reset_index(drop=True)

    timeline_spa = pd.to_datetime(
        pd.Series(timeline_spa).astype(str).str.strip(),
        errors="coerce"
    ).reset_index(drop=True)

    dsa = dsa.copy().reset_index(drop=True)

    # Asegurar que tiempo_dsa y dsa tengan la misma longitud
    n = min(len(tiempo_dsa), len(dsa))

    if len(tiempo_dsa) != len(dsa):
        if verbose:
            print(
                f"Aviso {nombre}: tiempo y DSA tienen longitudes distintas. "
                f"tiempo={len(tiempo_dsa)}, dsa={len(dsa)}. Se recorta a {n}."
            )

        tiempo_dsa = tiempo_dsa.iloc[:n].reset_index(drop=True)
        dsa = dsa.iloc[:n, :].reset_index(drop=True)

    # Caso ideal: misma longitud y mismos tiempos
    if len(tiempo_dsa) == len(timeline_spa) and (tiempo_dsa.values == timeline_spa.values).all():
        if verbose:
            print(f"{nombre}: ya coincide con la timeline del .spa. No se modifica.")

        return dsa

    # Reindexado por tiempo
    dsa.index = tiempo_dsa

    # Si hubiese tiempos duplicados en la DSA, conservar el último
    if dsa.index.duplicated().sum() > 0:
        if verbose:
            print(f"Aviso {nombre}: hay tiempos duplicados. Se conserva el último.")
        dsa = dsa[~dsa.index.duplicated(keep="last")]

    dsa_ajustada = dsa.reindex(timeline_spa)

    dsa_ajustada = dsa_ajustada.reset_index(drop=True)
    dsa_ajustada.columns = dsa.columns

    if verbose:
        print(f"=== Ajuste {nombre} a timeline .spa ===")
        print("Inicio DSA original:", tiempo_dsa.iloc[0])
        print("Fin DSA original:", tiempo_dsa.iloc[-1])
        print("Inicio .spa:", timeline_spa.iloc[0])
        print("Fin .spa:", timeline_spa.iloc[-1])
        print("Filas DSA original:", len(dsa))
        print("Filas timeline .spa:", len(timeline_spa))
        print("Filas DSA ajustada:", len(dsa_ajustada))
        print("Filas completamente NaN:", dsa_ajustada.isna().all(axis=1).sum())

    return dsa_ajustada



def alinear_raw_a_timeline_spa(
    df_raw,
    ruta_ta,
    timeline_spa,
    fs=128,
    verbose=True
):
    """
    Alinea el EEG crudo al tamaño y tiempo del .spa.

    Regla:
    - La timeline del .spa manda.
    - Si el raw empieza antes que el .spa: se recorta el inicio.
    - Si el raw empieza después que el .spa: se añaden NaN al inicio.
    - Si el raw acaba antes que el .spa: se añaden NaN al final.
    - Si el raw acaba después que el .spa: se recorta el final.

    Devuelve:
    - df_raw_alineado
    - info_alineacion
    """

    inicio_raw = leer_inicio_ta(ruta_ta)

    timeline_spa = pd.to_datetime(
        pd.Series(timeline_spa).astype(str).str.strip(),
        errors="coerce"
    ).dropna().reset_index(drop=True)

    if len(timeline_spa) == 0:
        raise ValueError("timeline_spa no contiene tiempos válidos.")

    inicio_spa = timeline_spa.iloc[0]
    fin_spa = timeline_spa.iloc[-1]

    desfase_s = (inicio_spa - inicio_raw).total_seconds()

    n_segundos_spa = len(timeline_spa)
    muestras_objetivo = int(n_segundos_spa * fs)

    df_raw = df_raw.copy().reset_index(drop=True)
    columnas_raw = df_raw.columns.tolist()

    # ------------------------------------------------------------
    # Caso A: raw empieza antes o justo al inicio del spa
    # ------------------------------------------------------------
    if desfase_s >= 0:
        muestras_recorte_inicio = int(round(desfase_s * fs))

        inicio = muestras_recorte_inicio
        fin = inicio + muestras_objetivo

        df_raw_alineado = df_raw.iloc[inicio:fin].copy().reset_index(drop=True)

        muestras_nan_inicio = 0
        accion_inicio = "recorte_inicio" if muestras_recorte_inicio > 0 else "sin_recorte_inicio"

    # ------------------------------------------------------------
    # Caso B: raw empieza después del spa
    # ------------------------------------------------------------
    else:
        muestras_nan_inicio = int(round(abs(desfase_s) * fs))

        df_nan_inicio = pd.DataFrame(
            np.nan,
            index=np.arange(muestras_nan_inicio),
            columns=columnas_raw
        )

        df_raw_expandido = pd.concat(
            [df_nan_inicio, df_raw],
            ignore_index=True
        )

        df_raw_alineado = (
            df_raw_expandido
            .iloc[:muestras_objetivo]
            .copy()
            .reset_index(drop=True)
        )

        muestras_recorte_inicio = 0
        accion_inicio = "relleno_nan_inicio"

    # ------------------------------------------------------------
    # Ajuste final
    # ------------------------------------------------------------
    if len(df_raw_alineado) < muestras_objetivo:
        muestras_nan_final = muestras_objetivo - len(df_raw_alineado)

        df_nan_final = pd.DataFrame(
            np.nan,
            index=np.arange(muestras_nan_final),
            columns=columnas_raw
        )

        df_raw_alineado = pd.concat(
            [df_raw_alineado, df_nan_final],
            ignore_index=True
        )

        muestras_recorte_final = 0

    elif len(df_raw_alineado) > muestras_objetivo:
        muestras_recorte_final = len(df_raw_alineado) - muestras_objetivo
        df_raw_alineado = df_raw_alineado.iloc[:muestras_objetivo].reset_index(drop=True)
        muestras_nan_final = 0

    else:
        muestras_nan_final = 0
        muestras_recorte_final = 0

    # Reconstruir tiempo_s
    if "tiempo_s" in df_raw_alineado.columns:
        df_raw_alineado["tiempo_s"] = np.arange(len(df_raw_alineado)) / fs

    info = {
        "inicio_raw_ta": inicio_raw,
        "inicio_spa": inicio_spa,
        "fin_spa": fin_spa,
        "desfase_spa_menos_raw_s": desfase_s,
        "n_segundos_spa": n_segundos_spa,
        "muestras_objetivo": muestras_objetivo,
        "accion_inicio": accion_inicio,
        "muestras_recorte_inicio": muestras_recorte_inicio,
        "muestras_nan_inicio": muestras_nan_inicio,
        "muestras_recorte_final": muestras_recorte_final,
        "muestras_nan_final": muestras_nan_final,
        "fs": fs
    }

    if verbose:
        print("=== Alineación raw a timeline .spa ===")
        print("Inicio raw (.t_a):", inicio_raw)
        print("Inicio .spa:", inicio_spa)
        print("Fin .spa:", fin_spa)
        print("Desfase spa - raw:", desfase_s, "s")
        print("Acción inicio:", accion_inicio)
        print("Segundos objetivo .spa:", n_segundos_spa)
        print("Muestras objetivo:", muestras_objetivo)
        print("Muestras raw originales:", len(df_raw))
        print("Muestras recortadas inicio:", muestras_recorte_inicio)
        print("Muestras NaN inicio:", muestras_nan_inicio)
        print("Muestras recortadas final:", muestras_recorte_final)
        print("Muestras NaN final:", muestras_nan_final)
        print("Muestras raw alineado:", len(df_raw_alineado))
        print("Duración raw alineado:", len(df_raw_alineado) / fs, "s")

    return df_raw_alineado, info



def recortar_raw_segun_ta_y_spa(
    df_raw,
    ruta_ta,
    df_spa,
    columna_time="Time",
    fs=128,
    resolver_duplicados="last",
    verbose=True
):
    """
    Alinea el EEG crudo con la línea temporal del .spa usando el .t_a.

    Regla principal:
    - El .spa manda en tamaño y línea temporal.
    - El raw se recorta o se rellena con NaN para ajustarse al .spa.
    - Si el raw empieza antes que el .spa, se recorta el inicio.
    - Si el raw empieza después que el .spa, se añaden NaN al inicio.
    - Si el raw acaba antes que el .spa, se añaden NaN al final.
    - Si el raw acaba después que el .spa, se recorta el final.

    Devuelve:
    - df_raw_alineado
    - timeline_spa
    - info_alineacion
    """

    # ------------------------------------------------------------
    # 1. Crear timeline del .spa
    # ------------------------------------------------------------

    timeline_spa = preparar_timeline_spa(
        df_spa=df_spa,
        columna_time=columna_time,
        resolver_duplicados=resolver_duplicados,
        verbose=verbose
    )

    # ------------------------------------------------------------
    # 2. Alinear raw a esa timeline
    # ------------------------------------------------------------

    df_raw_alineado, info_alineacion = alinear_raw_a_timeline_spa(
        df_raw=df_raw,
        ruta_ta=ruta_ta,
        timeline_spa=timeline_spa,
        fs=fs,
        verbose=verbose
    )

    return df_raw_alineado, timeline_spa, info_alineacion


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