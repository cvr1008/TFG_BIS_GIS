"""
Validacion experimental de la referencia en dB de la DSA BIS.

Este script es independiente de la aplicacion Dash: reutiliza sus funciones
de lectura y procesamiento, pero no modifica el codigo definitivo.

Compara:
    A = 10 log10(potencia_bin_uV2 / (0.0001 uV RMS)^2)
    B = 10 log10(potencia_bin_uV2 / 0.0001 uV2)

Tambien compara la potencia total 0.5-30 Hz con TOTPOW08:
    TOTPOW = 10 log10(potencia_total_uV2 / 0.0001 uV2)
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


APP_DIR = Path(r"C:\Users\usuario\tfg_app")
DATA_DIR = Path(r"C:\Users\usuario\TFG_BIS_GIS\data\data_bis_advanced")
OUTPUT_DIR = Path(__file__).with_name("resultados_validacion_referencia_dsa")

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.lectura_fa import (  # noqa: E402
    cargar_fa_bilateral_completo_desde_ruta,
    cargar_fa_unilateral_desde_ruta,
)
from src.lectura_spa import (  # noqa: E402
    cargar_spa_bilateral_desde_ruta,
    cargar_spa_unilateral_desde_ruta,
    preparar_timeline_spa,
)
from src.reconstruccion import (  # noqa: E402
    MAPA_LOFILTER_HZ,
    PARAMETROS_RECONSTRUCCION,
    _alinear_spa,
    _calcular_indices_alineacion,
    _canal_alineado_uv,
    _crear_mascara,
    _crear_mascara_raw_para_canal,
    _extraer_filtro_lofilter,
    _extraer_suavizado_spsmooth,
    _filtrar_pasa_altos_causal,
    _leer_raw_intercalado_desde_ruta,
    _suavizar_y_desplazar,
    _welch_por_bloques,
    extraer_parametros_eeg_desde_ruta,
    leer_inicio_ta_desde_ruta,
)


REFERENCIA_DSA_AMPLITUD_UV_RMS = 0.0001
REFERENCIA_TOTPOW_UV2 = 0.0001
EPS = 1e-12

REGISTROS = [
    {
        "registro": "L03041035",
        "modo": "unilateral",
        "carpeta": DATA_DIR / "M-TA6m-03041035" / "DH03041035",
    },
    {
        "registro": "L05141322",
        "modo": "bilateral",
        "carpeta": DATA_DIR / "bilateral" / "L05141322",
    },
    {
        "registro": "L04301923",
        "modo": "bilateral",
        "carpeta": (
            DATA_DIR
            / "bilateral"
            / "M-Py5D-04301923"
            / "DH04301923"
        ),
    },
]


def _metricas(reconstruida, referencia):
    reconstruida = np.asarray(reconstruida, dtype=np.float64)
    referencia = np.asarray(referencia, dtype=np.float64)
    validas = np.isfinite(reconstruida) & np.isfinite(referencia)
    x = reconstruida[validas]
    y = referencia[validas]

    if x.size == 0:
        return {
            "n": 0,
            "pearson": np.nan,
            "mae_db": np.nan,
            "rmse_db": np.nan,
            "sesgo_db": np.nan,
            "sd_error_db": np.nan,
        }

    error = x - y
    pearson = np.corrcoef(x, y)[0, 1] if x.size > 1 else np.nan
    return {
        "n": int(x.size),
        "pearson": float(pearson),
        "mae_db": float(np.mean(np.abs(error))),
        "rmse_db": float(np.sqrt(np.mean(error**2))),
        "sesgo_db": float(np.mean(error)),
        "sd_error_db": float(np.std(error)),
    }


def _alinear_fa(tiempo_fa, dsa_fa, timeline_spa):
    tiempo = pd.to_datetime(pd.Series(tiempo_fa), errors="coerce").dt.floor("s")
    matriz = dsa_fa.copy().astype(float).reset_index(drop=True)
    n = min(len(tiempo), len(matriz))
    tiempo = tiempo.iloc[:n]
    matriz = matriz.iloc[:n, :]
    validas = tiempo.notna()
    matriz = matriz.loc[validas.to_numpy()].copy()
    matriz.index = pd.DatetimeIndex(tiempo.loc[validas])
    matriz = matriz[~matriz.index.duplicated(keep="last")]
    return matriz.reindex(pd.DatetimeIndex(timeline_spa)).reset_index(drop=True)


def _alinear_ventanas(matriz, frecuencias, tiempos_s, timeline_spa):
    columnas = [float(f) for f in frecuencias]
    df = pd.DataFrame(matriz, columns=columnas)
    df.insert(0, "tiempo_s", tiempos_s)

    primera = {"tiempo_s": 0.0}
    primera.update({columna: np.nan for columna in columnas})
    df = pd.concat([pd.DataFrame([primera]), df], ignore_index=True)

    inicio = pd.Timestamp(timeline_spa.iloc[0]).floor("s")
    tiempo = (
        inicio + pd.to_timedelta(df["tiempo_s"], unit="s")
    ).dt.floor("s")
    salida = df[columnas].copy()
    salida.index = tiempo
    salida = salida[~salida.index.duplicated(keep="last")]
    return salida.reindex(pd.DatetimeIndex(timeline_spa)).reset_index(drop=True)


def _mejor_fragmento(mascara_filas_validas, longitud=900):
    mascara = np.asarray(mascara_filas_validas, dtype=bool)
    if mascara.size <= longitud:
        return 0, mascara.size
    cuentas = np.convolve(
        mascara.astype(np.int32),
        np.ones(longitud, dtype=np.int32),
        mode="valid",
    )
    inicio = int(np.argmax(cuentas))
    return inicio, inicio + longitud


def _representar_fragmento(
    registro,
    lado,
    tiempo,
    frecuencias,
    fa,
    referencia_a,
    referencia_b,
    mascara_filas_validas,
):
    inicio, fin = _mejor_fragmento(mascara_filas_validas)
    tiempo = pd.to_datetime(pd.Series(tiempo)).iloc[inicio:fin]
    matrices = [
        (".f_a exportado", fa.iloc[inicio:fin].to_numpy(dtype=float)),
        ("Reconstruccion A: referencia DSA", referencia_a.iloc[inicio:fin].to_numpy(dtype=float)),
        ("Reconstruccion B: referencia TOTPOW", referencia_b.iloc[inicio:fin].to_numpy(dtype=float)),
    ]

    fig, ejes = plt.subplots(
        3,
        1,
        figsize=(16, 10),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    imagen = None
    x0 = mdates.date2num(tiempo.iloc[0])
    x1 = mdates.date2num(tiempo.iloc[-1])
    for eje, (titulo, matriz) in zip(ejes, matrices):
        imagen = eje.imshow(
            np.ma.masked_invalid(matriz.T),
            aspect="auto",
            origin="lower",
            interpolation="nearest",
            extent=[x0, x1, frecuencias[0], frecuencias[-1]],
            vmin=49,
            vmax=94,
            cmap="jet",
        )
        eje.set_title(titulo)
        eje.set_ylabel("Frecuencia (Hz)")
        eje.set_yticks([0.5, 4, 8, 13, 30])

    ejes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
    ejes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ejes[-1].set_xlabel("Tiempo")
    barra = fig.colorbar(imagen, ax=ejes, pad=0.015)
    barra.set_label("Potencia (dB)")
    fig.suptitle(f"{registro} - {lado}: misma escala 49-94 dB")
    destino = OUTPUT_DIR / f"fragmento_{registro}_{lado}.png"
    fig.savefig(destino, dpi=160)
    plt.close(fig)


def _cargar_registro(config):
    carpeta = config["carpeta"]
    nombre = config["registro"]
    modo = config["modo"]
    rutas = {
        "fa": carpeta / f"{nombre}.f_a",
        "spa": carpeta / f"{nombre}.spa",
        "raw": carpeta / f"{nombre}.{'r4a' if modo == 'bilateral' else 'r2a'}",
        "header": carpeta / f"{nombre}.h_a",
        "ta": carpeta / f"{nombre}.t_a",
    }
    faltan = [str(ruta) for ruta in rutas.values() if not ruta.exists()]
    if faltan:
        raise FileNotFoundError(f"Faltan archivos para {nombre}: {faltan}")

    if modo == "bilateral":
        df_spa = cargar_spa_bilateral_desde_ruta(rutas["spa"])
        tiempo_fa, frecuencias, fa_izq, fa_der = (
            cargar_fa_bilateral_completo_desde_ruta(rutas["fa"])
        )
        lados = [
            {
                "lado": "izquierda",
                "canal": 0,
                "sufijo": "izq",
                "fa": fa_izq,
            },
            {
                "lado": "derecha",
                "canal": 2,
                "sufijo": "der",
                "fa": fa_der,
            },
        ]
    else:
        df_spa = cargar_spa_unilateral_desde_ruta(rutas["spa"])
        tiempo_fa, frecuencias, fa = cargar_fa_unilateral_desde_ruta(
            rutas["fa"]
        )
        lados = [
            {
                "lado": "unilateral",
                "canal": 0,
                "sufijo": None,
                "fa": fa,
            }
        ]

    return rutas, df_spa, tiempo_fa, np.asarray(frecuencias), lados


def _procesar_lado(
    config,
    lado,
    rutas,
    df_spa,
    tiempo_fa,
    frecuencias_fa,
    raw,
    header,
    timeline_spa,
    info_alineacion,
    suavizado_s,
    filtro_hz,
    df_merge,
):
    parametros = dict(PARAMETROS_RECONSTRUCCION)
    parametros["filtro_pasa_altos_hz"] = filtro_hz
    shift_s = (
        parametros["shift_bilateral_s"]
        if config["modo"] == "bilateral"
        else parametros["shift_unilateral_s"]
    )

    senal = _canal_alineado_uv(
        raw,
        lado["canal"],
        header["pendiente"],
        header["offset"],
        info_alineacion,
    )
    senal = _filtrar_pasa_altos_causal(
        senal,
        header["fs"],
        filtro_hz,
        parametros["orden_filtro_pasa_altos"],
    )
    psd_uv2_hz, frecuencias, tiempos_s = _welch_por_bloques(
        senal,
        header["fs"],
        parametros["ventana_welch_s"],
        parametros["paso_welch_s"],
        parametros["fmin"],
        parametros["fmax"],
        parametros["paso_frecuencia"],
        "densidad",
        parametros["tiempo_referencia"],
    )

    if not np.allclose(frecuencias, frecuencias_fa):
        raise ValueError("Las frecuencias Welch y .f_a no coinciden.")

    ancho_bin_hz = float(parametros["paso_frecuencia"])
    potencia_bin_uv2 = psd_uv2_hz * ancho_bin_hz
    dsa_a = 10 * np.log10(
        (potencia_bin_uv2 + EPS)
        / (REFERENCIA_DSA_AMPLITUD_UV_RMS**2)
    )
    dsa_b = 10 * np.log10(
        (potencia_bin_uv2 + EPS)
        / REFERENCIA_TOTPOW_UV2
    )
    diferencia_directa = dsa_a - dsa_b
    if not np.allclose(diferencia_directa, 40.0, atol=1e-10):
        raise AssertionError("A y B no difieren exactamente 40 dB.")

    potencia_total_uv2 = np.sum(potencia_bin_uv2, axis=1)
    totpow_db = 10 * np.log10(
        (potencia_total_uv2 + EPS) / REFERENCIA_TOTPOW_UV2
    )

    dsa_a = _alinear_ventanas(
        dsa_a,
        frecuencias,
        tiempos_s,
        timeline_spa,
    )
    dsa_b = _alinear_ventanas(
        dsa_b,
        frecuencias,
        tiempos_s,
        timeline_spa,
    )
    totpow = _alinear_ventanas(
        totpow_db[:, None],
        np.asarray([0.0]),
        tiempos_s,
        timeline_spa,
    )

    sufijo = lado["sufijo"]
    columna_sqi = f"SQI10_{sufijo}" if sufijo else "SQI10"
    columna_totpow = f"TOTPOW08_{sufijo}" if sufijo else "TOTPOW08"

    mascara_raw, _ = _crear_mascara_raw_para_canal(
        raw,
        lado["canal"],
        info_alineacion,
        parametros,
        tiempos_s,
        timeline_spa,
    )
    mascara_base = _crear_mascara(
        timeline_spa,
        dsa_a,
        df_merge[columna_sqi],
        df_merge[columna_totpow],
        parametros["umbral_sqi"],
        parametros["umbral_ceros"],
    ) | mascara_raw

    dsa_a = _suavizar_y_desplazar(
        dsa_a,
        suavizado_s,
        shift_s,
        mascara_inicial=mascara_base,
    )
    dsa_b = _suavizar_y_desplazar(
        dsa_b,
        suavizado_s,
        shift_s,
        mascara_inicial=mascara_base,
    )
    totpow = _suavizar_y_desplazar(
        totpow,
        suavizado_s,
        shift_s,
        mascara_inicial=mascara_base,
    )

    mascara_final = (
        mascara_base.reset_index(drop=True)
        | dsa_a.isna().all(axis=1).reset_index(drop=True)
    )
    dsa_a.loc[mascara_final.to_numpy(), :] = np.nan
    dsa_b.loc[mascara_final.to_numpy(), :] = np.nan
    totpow.loc[mascara_final.to_numpy(), :] = np.nan

    fa = _alinear_fa(tiempo_fa, lado["fa"], timeline_spa)
    mascara_fa = (
        fa.isna().all(axis=1)
        | ((fa == 0).mean(axis=1) > parametros["umbral_ceros"])
    )
    mascara_comun = mascara_final | mascara_fa
    fa.loc[mascara_comun.to_numpy(), :] = np.nan
    dsa_a.loc[mascara_comun.to_numpy(), :] = np.nan
    dsa_b.loc[mascara_comun.to_numpy(), :] = np.nan

    metricas_a = _metricas(dsa_a, fa)
    metricas_b = _metricas(dsa_b, fa)
    diferencia_ab = dsa_a.to_numpy(dtype=float) - dsa_b.to_numpy(dtype=float)
    diferencia_ab = diferencia_ab[np.isfinite(diferencia_ab)]

    totpow_spa = pd.to_numeric(
        df_merge[columna_totpow],
        errors="coerce",
    ).to_numpy(dtype=float)
    totpow_calc = totpow.iloc[:, 0].to_numpy(dtype=float)
    validas_totpow = (
        ~mascara_final.to_numpy()
        & np.isfinite(totpow_calc)
        & np.isfinite(totpow_spa)
    )
    metricas_totpow = _metricas(
        totpow_calc[validas_totpow],
        totpow_spa[validas_totpow],
    )

    filas_validas = (
        np.isfinite(fa.to_numpy(dtype=float)).any(axis=1)
        & np.isfinite(dsa_a.to_numpy(dtype=float)).any(axis=1)
    )
    _representar_fragmento(
        config["registro"],
        lado["lado"],
        timeline_spa,
        frecuencias,
        fa,
        dsa_a,
        dsa_b,
        filas_validas,
    )

    fa_valores = fa.to_numpy(dtype=float)
    fa_valores = fa_valores[np.isfinite(fa_valores)]
    resultado = {
        "registro": config["registro"],
        "modo": config["modo"],
        "lado": lado["lado"],
        "canal_raw": lado["canal"] + 1,
        "filas_spa": len(timeline_spa),
        "spsmooth_s": suavizado_s,
        "shift_s": shift_s,
        "lofilter_hz": filtro_hz,
        "fa_media_db": float(np.mean(fa_valores)),
        "fa_min_db": float(np.min(fa_valores)),
        "fa_max_db": float(np.max(fa_valores)),
        "fa_factor_almacenamiento": 100,
        "diferencia_a_b_media_db": float(np.mean(diferencia_ab)),
        "diferencia_a_b_sd_db": float(np.std(diferencia_ab)),
        "diferencia_a_b_max_desvio_40_db": float(
            np.max(np.abs(diferencia_ab - 40.0))
        ),
    }
    for prefijo, metricas in [
        ("a", metricas_a),
        ("b", metricas_b),
        ("totpow", metricas_totpow),
    ]:
        for clave, valor in metricas.items():
            resultado[f"{prefijo}_{clave}"] = valor
    return resultado


def procesar_registro(config):
    print(f"\nProcesando {config['registro']} ({config['modo']})...")
    (
        rutas,
        df_spa,
        tiempo_fa,
        frecuencias_fa,
        lados,
    ) = _cargar_registro(config)
    header = extraer_parametros_eeg_desde_ruta(rutas["header"])
    inicio_raw = leer_inicio_ta_desde_ruta(rutas["ta"])
    raw = _leer_raw_intercalado_desde_ruta(
        rutas["raw"],
        header["num_canales"],
    )
    timeline_spa = preparar_timeline_spa(df_spa)
    info_alineacion = _calcular_indices_alineacion(
        inicio_raw,
        timeline_spa,
        header["fs"],
        len(raw),
    )
    _, suavizado_s = _extraer_suavizado_spsmooth(df_spa)
    _, filtro_hz, _ = _extraer_filtro_lofilter(
        df_spa,
        PARAMETROS_RECONSTRUCCION[
            "filtro_pasa_altos_predeterminado_hz"
        ],
    )
    df_merge = _alinear_spa(timeline_spa, df_spa)

    resultados = []
    for lado in lados:
        print(f"  Lado {lado['lado']}...")
        resultados.append(
            _procesar_lado(
                config,
                lado,
                rutas,
                df_spa,
                tiempo_fa,
                frecuencias_fa,
                raw,
                header,
                timeline_spa,
                info_alineacion,
                suavizado_s,
                filtro_hz,
                df_merge,
            )
        )
    return resultados


def _crear_resumen_por_registro(detalle):
    numericas = [
        "a_pearson",
        "a_mae_db",
        "a_rmse_db",
        "a_sesgo_db",
        "b_pearson",
        "b_mae_db",
        "b_rmse_db",
        "b_sesgo_db",
        "diferencia_a_b_media_db",
        "totpow_pearson",
        "totpow_mae_db",
        "totpow_rmse_db",
        "totpow_sesgo_db",
    ]
    resumen = (
        detalle.groupby(["registro", "modo"], as_index=False)[numericas]
        .mean(numeric_only=True)
    )
    return resumen


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    resultados = []
    for config in REGISTROS:
        resultados.extend(procesar_registro(config))

    detalle = pd.DataFrame(resultados)
    resumen = _crear_resumen_por_registro(detalle)
    detalle.to_csv(
        OUTPUT_DIR / "metricas_por_registro_y_lado.csv",
        index=False,
        encoding="utf-8-sig",
    )
    resumen.to_csv(
        OUTPUT_DIR / "metricas_resumen_por_registro.csv",
        index=False,
        encoding="utf-8-sig",
    )

    columnas_mostrar = [
        "registro",
        "modo",
        "lado",
        "a_pearson",
        "a_mae_db",
        "a_rmse_db",
        "a_sesgo_db",
        "b_pearson",
        "b_mae_db",
        "b_rmse_db",
        "b_sesgo_db",
        "diferencia_a_b_media_db",
        "totpow_pearson",
        "totpow_mae_db",
        "totpow_rmse_db",
        "totpow_sesgo_db",
    ]
    texto = detalle[columnas_mostrar].round(4).to_string(index=False)
    (OUTPUT_DIR / "resumen_metricas.txt").write_text(
        texto,
        encoding="utf-8",
    )
    print("\n" + texto)
    print(f"\nResultados guardados en: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
