import numpy as np
import pandas as pd


UMBRAL_ALERTA_RECORTE = 0.5


def deduplicar_tiempos(tiempos):
    """
    Normaliza marcas temporales al segundo y conserva la última aparición.

    La eliminación de duplicados se realiza antes de ordenar para que
    ``keep="last"`` represente realmente la segunda o última fila del archivo.
    """
    serie = pd.to_datetime(
        pd.Series(tiempos),
        errors="coerce",
    ).dt.floor("s")
    tabla = pd.DataFrame(
        {
            "Time": serie,
            "_orden_original": np.arange(len(serie)),
        }
    ).dropna(subset=["Time"])
    duplicados = int(tabla.duplicated(subset="Time", keep="last").sum())
    tabla = tabla.drop_duplicates(subset="Time", keep="last")
    tabla = tabla.sort_values("Time").reset_index(drop=True)
    return tabla["Time"], duplicados


def deduplicar_dataframe_temporal(df, columna="Time"):
    """Conserva la última fila de cada segundo y ordena el resultado."""
    tabla = df.copy().reset_index(drop=True)
    tabla[columna] = pd.to_datetime(
        tabla[columna],
        errors="coerce",
    ).dt.floor("s")
    tabla["_orden_original"] = np.arange(len(tabla))
    tabla = tabla.dropna(subset=[columna])
    tabla = tabla.drop_duplicates(subset=columna, keep="last")
    return (
        tabla.sort_values(columna)
        .drop(columns="_orden_original")
        .reset_index(drop=True)
    )


def _agrupar_tramos(tiempos):
    """Agrupa segundos consecutivos en intervalos cerrados."""
    tiempos = pd.Series(
        pd.to_datetime(pd.Series(tiempos), errors="coerce")
    ).dropna()
    if tiempos.empty:
        return []
    tiempos = tiempos.drop_duplicates().sort_values().reset_index(drop=True)
    cortes = tiempos.diff().dt.total_seconds().ne(1)
    grupos = cortes.cumsum()
    tramos = []
    for _grupo, valores in tiempos.groupby(grupos):
        inicio = valores.iloc[0]
        fin = valores.iloc[-1]
        tramos.append(
            {
                "inicio": inicio,
                "fin": fin,
                "segundos": int((fin - inicio).total_seconds()) + 1,
            }
        )
    return tramos


def crear_mascara_discontinuidades(timeline, tiempos_fuente):
    """
    Marca únicamente los segundos ausentes dentro de la timeline común.

    Por ejemplo, si una fuente pasa de 10:40:35 a 10:40:41, se invalidan
    10:40:36--10:40:40. El segundo 10:40:41 se conserva si sus criterios
    propios de calidad, como SQI, TOTPOW o pérdidas raw, son válidos.
    """
    timeline = pd.to_datetime(
        pd.Series(timeline),
        errors="coerce",
    ).dt.floor("s")
    tiempos, _duplicados = deduplicar_tiempos(tiempos_fuente)
    presentes = timeline.isin(pd.DatetimeIndex(tiempos))
    return pd.Series(
        ~presentes,
        dtype=bool,
    ).reset_index(drop=True)


def _resumen_fuente(nombre, tiempos, inicio_comun, fin_comun, duplicados=0):
    """
    Ejecuta la lógica asociada a resumen fuente.

    Parámetros
    ----------
    nombre : Any
        Valor de entrada utilizado por la función.

    tiempos : Any
        Valor de entrada utilizado por la función.

    inicio_comun : Any
        Valor de entrada utilizado por la función.

    fin_comun : Any
        Valor de entrada utilizado por la función.

    duplicados : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    inicio_fuente = tiempos.iloc[0]
    fin_fuente = tiempos.iloc[-1]
    total = int((fin_fuente - inicio_fuente).total_seconds()) + 1
    retenidos = int((fin_comun - inicio_comun).total_seconds()) + 1
    eliminados = total - retenidos
    proporcion = eliminados / total if total else 1.0

    tramos_recortados = []
    if inicio_fuente < inicio_comun:
        tramos_recortados.append(
            {
                "inicio": inicio_fuente,
                "fin": inicio_comun - pd.Timedelta(seconds=1),
                "segundos": int(
                    (inicio_comun - inicio_fuente).total_seconds()
                ),
                "posicion": "inicio",
            }
        )
    if fin_fuente > fin_comun:
        tramos_recortados.append(
            {
                "inicio": fin_comun + pd.Timedelta(seconds=1),
                "fin": fin_fuente,
                "segundos": int(
                    (fin_fuente - fin_comun).total_seconds()
                ),
                "posicion": "final",
            }
        )

    dentro = tiempos[
        (tiempos >= inicio_comun) & (tiempos <= fin_comun)
    ]
    timeline_completa = pd.Series(
        pd.date_range(inicio_comun, fin_comun, freq="s")
    )
    huecos = timeline_completa[
        ~timeline_completa.isin(pd.DatetimeIndex(dentro))
    ]
    tramos_huecos = _agrupar_tramos(huecos)
    segundos_huecos = int(sum(tramo["segundos"] for tramo in tramos_huecos))

    if not tramos_recortados:
        forma_recorte = "sin_recorte"
    elif len(tramos_recortados) == 1:
        forma_recorte = "bloque_continuo"
    else:
        forma_recorte = "dos_bloques_extremos"

    return {
        "nombre": nombre,
        "inicio": inicio_fuente,
        "fin": fin_fuente,
        "segundos_originales": int(total),
        "segundos_retenidos": int(retenidos),
        "segundos_eliminados": int(eliminados),
        "proporcion_eliminada": float(proporcion),
        "duplicados_eliminados": int(duplicados),
        "alerta_recorte": bool(proporcion >= UMBRAL_ALERTA_RECORTE),
        "forma_recorte": forma_recorte,
        "tramos_recortados": tramos_recortados,
        "numero_tramos_recortados": len(tramos_recortados),
        "segundos_observados_intervalo_comun": int(len(dentro)),
        "segundos_huecos_internos": segundos_huecos,
        "tramos_huecos_internos": tramos_huecos,
        "numero_tramos_huecos_internos": len(tramos_huecos),
        "discontinuidad_interna": bool(tramos_huecos),
    }


def calcular_timeline_comun(
    inicio_raw,
    numero_muestras_raw,
    fs,
    tiempos_spa,
    tiempos_fa=None,
):
    """
    Calcula la intersección temporal de raw, .spa y, si existe, .f_a.

    El raw se limita primero al último segundo completo. La timeline resultante
    no prolonga ninguna fuente fuera de su cobertura temporal real.
    """
    fs = int(fs)
    if fs <= 0:
        raise ValueError("La frecuencia de muestreo no es válida.")

    segundos_raw = int(numero_muestras_raw) // fs
    muestras_residuales = int(numero_muestras_raw) % fs
    if segundos_raw <= 0:
        raise ValueError("La onda cruda no contiene ningún segundo completo.")

    inicio_raw = pd.Timestamp(inicio_raw).floor("s")
    tiempos_raw = pd.Series(
        pd.date_range(
            inicio_raw,
            periods=segundos_raw,
            freq="s",
        )
    )
    spa, duplicados_spa = deduplicar_tiempos(tiempos_spa)
    if spa.empty:
        raise ValueError("El .spa no contiene tiempos válidos.")

    fuentes = {
        "raw": (tiempos_raw, 0),
        "spa": (spa, duplicados_spa),
    }
    fa = None
    if tiempos_fa is not None:
        fa, duplicados_fa = deduplicar_tiempos(tiempos_fa)
        if fa.empty:
            raise ValueError("El .f_a no contiene tiempos válidos.")
        fuentes["fa"] = (fa, duplicados_fa)

    inicio_comun = max(tiempos.iloc[0] for tiempos, _ in fuentes.values())
    fin_comun = min(tiempos.iloc[-1] for tiempos, _ in fuentes.values())
    if inicio_comun > fin_comun:
        raise ValueError(
            "La onda cruda, el .spa y el .f_a no comparten ningún "
            "intervalo temporal."
        )

    timeline = pd.Series(
        pd.date_range(inicio_comun, fin_comun, freq="s"),
        name="Time",
    )
    resumen = {
        nombre: _resumen_fuente(
            nombre,
            tiempos,
            inicio_comun,
            fin_comun,
            duplicados=duplicados,
        )
        for nombre, (tiempos, duplicados) in fuentes.items()
    }
    alertas = [
        datos
        for datos in resumen.values()
        if datos["alerta_recorte"]
    ]

    return {
        "timeline": timeline,
        "inicio": inicio_comun,
        "fin": fin_comun,
        "segundos": int(len(timeline)),
        "fuentes": resumen,
        "alertas": alertas,
        "muestras_residuales_raw": muestras_residuales,
        "segundos_raw_completos": segundos_raw,
        "tiempos_spa": spa,
        "tiempos_fa": fa,
    }
