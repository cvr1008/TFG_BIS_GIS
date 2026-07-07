import numpy as np


BANDAS_EEG = [
    ("Delta", 0.5, 4.0),
    ("Theta", 4.0, 8.0),
    ("Alpha", 8.0, 13.0),
    ("Beta", 13.0, 30.0),
]


def calcular_densidad_espectral_media_bandas(matriz_db, frecuencias):
    """
    Calcula la densidad espectral media de cada banda EEG.

    La DSA contiene potencia integrada por bins de frecuencia. Se recupera la
    escala lineal, se divide por la anchura del bin para volver a densidad de
    potencia, se promedia sobre frecuencia y tiempo, y se convierte a dB al
    final. Así las bandas se comparan por intensidad media por Hz, sin que una
    banda más ancha tenga ventaja por contener más bins.
    """
    matriz_db = np.asarray(matriz_db, dtype=float)
    frecuencias = np.asarray(frecuencias, dtype=float)

    if matriz_db.ndim != 2:
        raise ValueError("La matriz DSA debe tener dos dimensiones.")
    if matriz_db.shape[1] != len(frecuencias):
        raise ValueError(
            "El número de frecuencias no coincide con las columnas de la DSA."
        )

    orden = np.argsort(frecuencias)
    frecuencias = frecuencias[orden]
    matriz_db = matriz_db[:, orden]
    paso_frecuencia = (
        float(np.nanmedian(np.diff(frecuencias)))
        if len(frecuencias) > 1
        else 1.0
    )
    if not np.isfinite(paso_frecuencia) or paso_frecuencia <= 0:
        raise ValueError("La separación entre frecuencias no es válida.")

    potencia_por_bin = np.power(10.0, matriz_db / 10.0)
    densidad = potencia_por_bin / paso_frecuencia

    valores_db = {}
    segundos_validos_banda = {}
    potencias_integradas = {}
    valores_lineales_banda = {}
    for indice, (_nombre, inferior, superior) in enumerate(BANDAS_EEG):
        if indice == len(BANDAS_EEG) - 1:
            mascara = (
                (frecuencias >= inferior) & (frecuencias <= superior)
            )
        else:
            mascara = (
                (frecuencias >= inferior) & (frecuencias < superior)
            )

        if not mascara.any():
            valores_db[_nombre] = np.nan
            segundos_validos_banda[_nombre] = 0
            potencias_integradas[_nombre] = np.nan
            valores_lineales_banda[_nombre] = None
            continue

        valores = densidad[:, mascara]
        potencia_banda = potencia_por_bin[:, mascara]
        valores_lineales_banda[_nombre] = potencia_banda
        filas_validas = np.isfinite(valores).all(axis=1)
        segundos_validos_banda[_nombre] = int(filas_validas.sum())
        potencias_integradas[_nombre] = (
            float(np.nansum(potencia_banda[filas_validas]))
            if filas_validas.any()
            else np.nan
        )
        densidad_media_lineal = (
            float(np.nanmean(valores[filas_validas]))
            if filas_validas.any()
            else np.nan
        )
        valores_db[_nombre] = (
            10.0 * np.log10(densidad_media_lineal)
            if np.isfinite(densidad_media_lineal)
            and densidad_media_lineal > 0
            else np.nan
        )

    filas_validas = np.isfinite(matriz_db).any(axis=1)
    total_validos = int(filas_validas.sum())
    valores_alpha = valores_lineales_banda.get("Alpha")
    valores_delta = valores_lineales_banda.get("Delta")
    if valores_alpha is not None and valores_delta is not None:
        filas_adr = (
            np.isfinite(valores_alpha).all(axis=1)
            & np.isfinite(valores_delta).all(axis=1)
        )
        potencia_alpha = float(np.sum(valores_alpha[filas_adr]))
        potencia_delta = float(np.sum(valores_delta[filas_adr]))
        segundos_validos_adr = int(filas_adr.sum())
    else:
        potencia_alpha = np.nan
        potencia_delta = np.nan
        segundos_validos_adr = 0
    ratio_alpha_delta = (
        potencia_alpha / potencia_delta
        if np.isfinite(potencia_alpha)
        and np.isfinite(potencia_delta)
        and potencia_delta > 0
        else np.nan
    )

    return {
        "valores_db": valores_db,
        "potencias_integradas": potencias_integradas,
        "ratio_alpha_delta": ratio_alpha_delta,
        "segundos_validos_adr": segundos_validos_adr,
        "segundos_validos_banda": segundos_validos_banda,
        "segundos_validos": total_validos,
        "segundos_totales": int(matriz_db.shape[0]),
        "paso_frecuencia_hz": paso_frecuencia,
        "criterio": "densidad_espectral_media",
    }


def lineas_densidad_bandas(resumen, bloques_minimos=4, bloques_maximos=12):
    """Devuelve solo el ratio alfa-delta para el recuadro de la figura."""
    ratio_alpha_delta = resumen.get("ratio_alpha_delta", np.nan)
    return [
        "ADR alfa/delta: "
        + (
            f"{ratio_alpha_delta:.3f}"
            if np.isfinite(ratio_alpha_delta)
            else "sin datos"
        )
    ]
