import base64
import io

import numpy as np
import pandas as pd

from src.alineacion_temporal import (
    deduplicar_dataframe_temporal,
    deduplicar_tiempos,
)


SENTINELAS_BIS = [-327.7, -3276.0, -3276.8, -3276, -32767, -32768]


def _decode_upload_to_text(contents):
    """Convierte el contenido subido por Dash en texto."""
    _, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    return decoded.decode("latin1", errors="ignore")


def _crear_nombres_unicos(nombres):
    contador = {}
    nombres_unicos = []

    for nombre in nombres:
        nombre = nombre.strip() or "col_vacia"
        contador[nombre] = contador.get(nombre, 0) + 1
        sufijo = "" if contador[nombre] == 1 else f"_{contador[nombre]}"
        nombres_unicos.append(f"{nombre}{sufijo}")

    return nombres_unicos


def _seleccionar_columna(df, nombre, candidatos):
    for candidato in candidatos:
        if candidato in df.columns:
            return pd.to_numeric(df[candidato], errors="coerce")

    raise ValueError(
        f"El archivo .spa no contiene una columna compatible para {nombre}. "
        f"Se buscó: {', '.join(candidatos)}."
    )


def _seleccionar_columna_opcional(df, candidatos):
    for candidato in candidatos:
        if candidato in df.columns:
            return pd.to_numeric(df[candidato], errors="coerce")
    return pd.Series(np.nan, index=df.index, dtype=float)


def _cargar_spa_unilateral_desde_texto(texto):
    """
    Lee un .spa subido a Dash y devuelve las variables unilaterales
    estandarizadas que se usan para representar la DSA.

    En los archivos BIS Advanced se prioriza el canal combinado Ch 12,
    cuyos nombres quedan terminados en ``_3`` tras resolver duplicados.
    """
    lineas = texto.splitlines()

    if len(lineas) < 3:
        raise ValueError("El archivo .spa no contiene cabecera y datos suficientes.")

    df = pd.read_csv(
        io.StringIO(texto),
        sep="|",
        header=None,
        skiprows=2,
        engine="python",
    )
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all").reset_index(drop=True)

    nombres = [campo.strip() for campo in lineas[1].split("|")]
    nombres = nombres[: df.shape[1]]

    if len(nombres) != df.shape[1]:
        raise ValueError(
            "La cabecera del .spa no coincide con el número de columnas de datos."
        )

    df.columns = _crear_nombres_unicos(nombres)

    tiempo = pd.to_datetime(
        df["Time"].astype(str).str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    ).dt.floor("s")

    df_out = pd.DataFrame({"Time": tiempo})
    df_out["SpSmooth"] = _seleccionar_columna(
        df, "suavizado espectral", ["SpSmooth"]
    )
    df_out["LoFilter"] = _seleccionar_columna_opcional(
        df,
        ["LoFilter"],
    )
    df_out["SEF08"] = _seleccionar_columna(
        df, "SEF", ["SEF08_3", "SEF08"]
    )
    df_out["MEDFRQ08"] = _seleccionar_columna(
        df, "MEF", ["MEDFRQ08_3", "MEDFRQ08"]
    )
    df_out["SQI10"] = _seleccionar_columna(
        df, "SQI", ["SQI10_3", "SQI10"]
    )
    df_out["TOTPOW08"] = _seleccionar_columna(
        df, "potencia total", ["TOTPOW08_3", "TOTPOW08"]
    )
    df_out["DB13U01"] = _seleccionar_columna(
        df, "índice BIS", ["DB13U01_3", "DB13U01"]
    )
    df_out["EMGLOW01"] = _seleccionar_columna_opcional(
        df,
        ["EMGLOW01_3", "EMGLOW01"],
    )
    df_out["SR12"] = _seleccionar_columna_opcional(
        df,
        ["SR12_3", "SR12"],
    )

    columnas_numericas = [
        "SpSmooth",
        "LoFilter",
        "SEF08",
        "MEDFRQ08",
        "SQI10",
        "TOTPOW08",
        "DB13U01",
        "EMGLOW01",
        "SR12",
    ]
    df_out[columnas_numericas] = df_out[columnas_numericas].replace(
        SENTINELAS_BIS, np.nan
    )

    return df_out.dropna(subset=["Time"]).reset_index(drop=True)


def cargar_spa_unilateral_desde_upload(contents):
    return _cargar_spa_unilateral_desde_texto(_decode_upload_to_text(contents))


def cargar_spa_unilateral_desde_ruta(ruta):
    with open(ruta, "r", encoding="latin1", errors="ignore") as archivo:
        return _cargar_spa_unilateral_desde_texto(archivo.read())


def _cargar_spa_bilateral_desde_texto(texto):
    """
    Lee las variables bilaterales del .spa.

    Siguiendo la estructura VISTA usada por las funciones del proyecto:
    - hemisferio izquierdo: primer bloque de canal;
    - hemisferio derecho: tercer bloque, columnas terminadas en ``_3``;
    - asimetría: ASYM09 del primer bloque.
    """
    lineas = texto.splitlines()

    if len(lineas) < 3:
        raise ValueError("El archivo .spa no contiene cabecera y datos suficientes.")

    df = pd.read_csv(
        io.StringIO(texto),
        sep="|",
        header=None,
        skiprows=2,
        engine="python",
    )
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all").reset_index(drop=True)

    nombres = [campo.strip() for campo in lineas[1].split("|")]
    nombres = nombres[: df.shape[1]]

    if len(nombres) != df.shape[1]:
        raise ValueError(
            "La cabecera del .spa no coincide con el número de columnas de datos."
        )

    df.columns = _crear_nombres_unicos(nombres)

    tiempo = pd.to_datetime(
        df["Time"].astype(str).str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    ).dt.floor("s")

    df_out = pd.DataFrame({"Time": tiempo})
    df_out["SpSmooth"] = _seleccionar_columna(
        df, "suavizado espectral", ["SpSmooth"]
    )
    df_out["LoFilter"] = _seleccionar_columna_opcional(
        df,
        ["LoFilter"],
    )

    variables = [
        "SEF08",
        "MEDFRQ08",
        "SQI10",
        "TOTPOW08",
        "DB13U01",
        "EMGLOW01",
        "SR12",
    ]
    for variable in variables:
        df_out[f"{variable}_izq"] = _seleccionar_columna(
            df,
            f"{variable} izquierdo",
            [variable],
        )
        df_out[f"{variable}_der"] = _seleccionar_columna(
            df,
            f"{variable} derecho",
            [f"{variable}_3"],
        )

    df_out["ASYM09"] = _seleccionar_columna(
        df,
        "asimetría ASYM09",
        ["ASYM09"],
    )

    columnas_numericas = [c for c in df_out.columns if c != "Time"]
    df_out[columnas_numericas] = df_out[columnas_numericas].replace(
        SENTINELAS_BIS,
        np.nan,
    )

    return df_out.dropna(subset=["Time"]).reset_index(drop=True)


def cargar_spa_bilateral_desde_upload(contents):
    return _cargar_spa_bilateral_desde_texto(_decode_upload_to_text(contents))


def cargar_spa_bilateral_desde_ruta(ruta):
    with open(ruta, "r", encoding="latin1", errors="ignore") as archivo:
        return _cargar_spa_bilateral_desde_texto(archivo.read())


def alinear_spa_con_tiempo_dsa(tiempo, df_spa):
    """Alinea las variables del .spa con cada segundo presente en la DSA."""
    df_spa = (
        df_spa.sort_values("Time")
        .drop_duplicates(subset="Time", keep="last")
        .reset_index(drop=True)
    )

    df_tiempo = pd.DataFrame(
        {"Time": pd.to_datetime(pd.Series(tiempo), errors="coerce").dt.floor("s")}
    )

    return df_tiempo.merge(
        df_spa,
        on="Time",
        how="left",
        validate="many_to_one",
    )


def preparar_timeline_spa(
    df_spa,
    resolver_duplicados="last",
):
    """
    Crea la línea temporal oficial a partir del .spa.

    Reproduce la regla de las funciones bilaterales del proyecto: el .spa
    manda y cada segundo aparece una sola vez.
    """
    if resolver_duplicados != "last":
        raise ValueError(
            "La timeline común conserva siempre la última aparición."
        )
    tiempos, _duplicados = deduplicar_tiempos(df_spa["Time"])
    if tiempos.empty:
        raise ValueError("No se encontraron tiempos válidos en el .spa.")
    return tiempos


def ajustar_dsa_a_timeline_spa(
    tiempo_dsa,
    dsa,
    timeline_spa,
):
    """
    Reindexa una DSA sobre la timeline del .spa.

    Los segundos que solo están en el .spa se rellenan con NaN y los que
    quedan fuera de su intervalo se recortan.
    """
    tiempo_dsa = pd.to_datetime(
        pd.Series(tiempo_dsa).astype(str).str.strip(),
        errors="coerce",
    ).dt.floor("s")
    timeline_spa = pd.to_datetime(
        pd.Series(timeline_spa).astype(str).str.strip(),
        errors="coerce",
    ).dt.floor("s")
    dsa = dsa.copy().astype(float).reset_index(drop=True)

    n = min(len(tiempo_dsa), len(dsa))
    tiempo_dsa = tiempo_dsa.iloc[:n].reset_index(drop=True)
    dsa = dsa.iloc[:n, :].reset_index(drop=True)

    validos = tiempo_dsa.notna()
    tiempo_dsa = tiempo_dsa.loc[validos].reset_index(drop=True)
    dsa = dsa.loc[validos.values, :].reset_index(drop=True)
    dsa.index = tiempo_dsa

    if dsa.index.duplicated().any():
        dsa = dsa[~dsa.index.duplicated(keep="last")]

    columnas = dsa.columns
    dsa_ajustada = dsa.reindex(timeline_spa)
    dsa_ajustada = dsa_ajustada.reset_index(drop=True)
    dsa_ajustada.columns = columnas
    return dsa_ajustada


def preparar_dsa_unilateral_con_spa(
    tiempo,
    dsa,
    df_spa,
    umbral_sqi=15,
    umbral_ceros=0.9,
    mask_comun=None,
    timeline_comun=None,
):
    """
    Alinea .f_a y .spa y aplica los mismos criterios básicos de validez
    usados por las figuras Matplotlib del proyecto.
    """
    timeline_spa = (
        pd.to_datetime(pd.Series(timeline_comun), errors="coerce")
        .dt.floor("s")
        .reset_index(drop=True)
        if timeline_comun is not None
        else preparar_timeline_spa(
            df_spa,
            resolver_duplicados="last",
        )
    )
    dsa_plot = ajustar_dsa_a_timeline_spa(tiempo, dsa, timeline_spa)
    tiempo = timeline_spa.reset_index(drop=True)
    df_spa_unico = deduplicar_dataframe_temporal(df_spa, "Time")
    df_merge = pd.DataFrame({"Time": tiempo}).merge(
        df_spa_unico,
        on="Time",
        how="left",
        validate="one_to_one",
    )

    columnas_spa = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08"]
    if not df_merge[columnas_spa].notna().any(axis=None):
        raise ValueError(
            "Los archivos .f_a y .spa no comparten ningún instante temporal."
        )

    sqi = pd.to_numeric(df_merge["SQI10"], errors="coerce")
    totpow = pd.to_numeric(df_merge["TOTPOW08"], errors="coerce")

    mask_spa = (sqi < umbral_sqi) | totpow.isna()
    mask_ceros = (dsa_plot == 0).mean(axis=1) > umbral_ceros
    mask_saltos = tiempo.diff().dt.total_seconds().gt(1).fillna(False)
    mask_nan = dsa_plot.isna().all(axis=1)

    if mask_comun is None:
        mask_total = (
            mask_spa.reset_index(drop=True)
            | mask_ceros.reset_index(drop=True)
            | mask_saltos.reset_index(drop=True)
            | mask_nan.reset_index(drop=True)
        )
    else:
        mask_total = pd.Series(
            mask_comun,
            dtype=bool,
        ).reset_index(drop=True)
        if len(mask_total) != len(tiempo):
            raise ValueError(
                "La máscara común unilateral no coincide con la timeline .spa."
            )

    dsa_plot.loc[mask_total.values, :] = np.nan

    for columna in ["SEF08", "MEDFRQ08"]:
        valores = pd.to_numeric(df_merge[columna], errors="coerce")
        valores[(valores < 0.5) | (valores > 30)] = np.nan
        valores.loc[mask_total.values] = np.nan
        df_merge[columna] = valores

    bis = pd.to_numeric(df_merge["DB13U01"], errors="coerce")
    bis[(bis < 0) | (bis > 100)] = np.nan
    bis.loc[mask_total.values] = np.nan
    df_merge["DB13U01"] = bis

    emg = pd.to_numeric(df_merge["EMGLOW01"], errors="coerce")
    emg[(emg < 0) | (emg > 100)] = np.nan
    emg.loc[mask_total.values] = np.nan
    df_merge["EMGLOW01"] = emg

    sr = pd.to_numeric(df_merge["SR12"], errors="coerce")
    sr[(sr < 0) | (sr > 100)] = np.nan
    sr.loc[mask_total.values] = np.nan
    df_merge["SR12"] = sr

    return dsa_plot, df_merge, mask_total


def _preparar_lado_bilateral(
    tiempo,
    dsa,
    df_merge,
    sufijo,
    umbral_sqi,
    umbral_ceros,
    mask_comun=None,
):
    dsa_plot = dsa.copy().astype(float).reset_index(drop=True)
    sqi = pd.to_numeric(df_merge[f"SQI10_{sufijo}"], errors="coerce")
    totpow = pd.to_numeric(df_merge[f"TOTPOW08_{sufijo}"], errors="coerce")

    mask_spa = (sqi < umbral_sqi) | totpow.isna()
    mask_ceros = (dsa_plot == 0).mean(axis=1) > umbral_ceros
    mask_saltos = tiempo.diff().dt.total_seconds().gt(1).fillna(False)
    mask_nan = dsa_plot.isna().all(axis=1)

    if mask_comun is None:
        mask_total = (
            mask_spa.reset_index(drop=True)
            | mask_ceros.reset_index(drop=True)
            | mask_saltos.reset_index(drop=True)
            | mask_nan.reset_index(drop=True)
        )
    else:
        mask_total = pd.Series(
            mask_comun,
            dtype=bool,
        ).reset_index(drop=True)
        if len(mask_total) != len(tiempo):
            raise ValueError(
                "La máscara común bilateral no coincide con la timeline .spa."
            )
    dsa_plot.loc[mask_total.values, :] = np.nan

    curvas = {}
    for variable in [
        "SEF08",
        "MEDFRQ08",
        "DB13U01",
        "EMGLOW01",
        "SR12",
    ]:
        valores = pd.to_numeric(
            df_merge[f"{variable}_{sufijo}"],
            errors="coerce",
        ).copy()
        if variable in {"DB13U01", "EMGLOW01", "SR12"}:
            valores[(valores < 0) | (valores > 100)] = np.nan
        else:
            valores[(valores < 0.5) | (valores > 30)] = np.nan
        valores.loc[mask_total.values] = np.nan
        curvas[variable] = valores

    return dsa_plot, curvas, mask_total


def preparar_dsa_bilateral_con_spa(
    tiempo,
    dsa_izq,
    dsa_der,
    df_spa,
    umbral_sqi=15,
    umbral_ceros=0.9,
    mask_izq_comun=None,
    mask_der_comun=None,
    timeline_comun=None,
):
    """
    Ajusta ambas DSA a la timeline oficial del .spa y aplica las máscaras.
    """
    timeline_spa = (
        pd.to_datetime(pd.Series(timeline_comun), errors="coerce")
        .dt.floor("s")
        .reset_index(drop=True)
        if timeline_comun is not None
        else preparar_timeline_spa(
            df_spa,
            resolver_duplicados="last",
        )
    )
    dsa_izq = ajustar_dsa_a_timeline_spa(tiempo, dsa_izq, timeline_spa)
    dsa_der = ajustar_dsa_a_timeline_spa(tiempo, dsa_der, timeline_spa)

    if not np.isfinite(dsa_izq.to_numpy()).any():
        raise ValueError(
            "La DSA izquierda y el .spa no comparten ningún instante temporal."
        )
    if not np.isfinite(dsa_der.to_numpy()).any():
        raise ValueError(
            "La DSA derecha y el .spa no comparten ningún instante temporal."
        )

    df_spa_unico = deduplicar_dataframe_temporal(df_spa, "Time")
    df_merge = pd.DataFrame({"Time": timeline_spa}).merge(
        df_spa_unico,
        on="Time",
        how="left",
        validate="one_to_one",
    )
    tiempo_comun = timeline_spa.reset_index(drop=True)

    columnas_spa = [
        "SEF08_izq",
        "MEDFRQ08_izq",
        "SQI10_izq",
        "TOTPOW08_izq",
        "SEF08_der",
        "MEDFRQ08_der",
        "SQI10_der",
        "TOTPOW08_der",
        "DB13U01_izq",
        "DB13U01_der",
        "ASYM09",
    ]
    if not df_merge[columnas_spa].notna().any(axis=None):
        raise ValueError(
            "Los archivos .f_a y .spa no comparten ningún instante temporal."
        )

    dsa_plot_izq, curvas_izq, mask_izq = _preparar_lado_bilateral(
        tiempo_comun,
        dsa_izq,
        df_merge,
        "izq",
        umbral_sqi,
        umbral_ceros,
        mask_comun=mask_izq_comun,
    )
    dsa_plot_der, curvas_der, mask_der = _preparar_lado_bilateral(
        tiempo_comun,
        dsa_der,
        df_merge,
        "der",
        umbral_sqi,
        umbral_ceros,
        mask_comun=mask_der_comun,
    )

    asimetria = pd.to_numeric(df_merge["ASYM09"], errors="coerce").copy()
    asimetria.loc[(mask_izq | mask_der).values] = np.nan

    return (
        tiempo_comun,
        dsa_plot_izq,
        dsa_plot_der,
        curvas_izq,
        curvas_der,
        asimetria,
        mask_izq,
        mask_der,
    )
