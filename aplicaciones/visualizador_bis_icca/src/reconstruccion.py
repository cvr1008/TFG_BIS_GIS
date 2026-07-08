import base64
import struct

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfilt, sosfilt_zi, welch

from src.alineacion_temporal import (
    calcular_timeline_comun,
    crear_mascara_discontinuidades,
    deduplicar_dataframe_temporal,
)
from src.lectura_fa import cargar_tiempos_fa_desde_ruta


PARAMETROS_RECONSTRUCCION = {
    "ventana_welch_s": 2,
    "paso_welch_s": 1,
    "solapamiento_ventanas_s": 1,
    "fmin": 0.5,
    "fmax": 30.0,
    "paso_frecuencia": 0.5,
    "modo_welch": "densidad",
    "tiempo_referencia": "centro",
    "umbral_sqi": 15,
    "aplicar_mascara_ceros_raw": True,
    "umbral_ceros_raw": 0.5,
    "excluir_invalidos_suavizado": True,
    "referencia_amplitud_uv_rms": 0.0001,
    "combinacion_unilateral": "canal_1",
    "combinacion_bilateral": "canal_1_izquierda_canal_3_derecha",
    "filtro_pasa_altos_predeterminado_hz": 0.25,
    "orden_filtro_pasa_altos": 1,
    "shift_unilateral_s": 10,
    "shift_bilateral_s": 6,
}

MAPA_SPSMOOTH_SEGUNDOS = {
    0: 0,
    1: 5,
    2: 10,
    3: 30,
    4: 60,
}

MAPA_LOFILTER_HZ = {
    0: 0.25,
    1: 1.0,
    2: 2.0,
    3: 2.5,
}
# En el .spa, LoFilter codifica el corte inferior y se aplica como pasa-altos.


def _decodificar_upload_bytes(contents):
    """
    Decodifica upload bytes.

    Parámetros
    ----------
    contents : Any
        Contenido codificado recibido desde la interfaz.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    if not contents or "," not in contents:
        raise ValueError("El archivo subido no contiene datos válidos.")
    _, contenido = contents.split(",", 1)
    return base64.b64decode(contenido)


def extraer_parametros_eeg_desde_upload(contents_header):
    """
    Extrae parametros eeg desde upload.

    Parámetros
    ----------
    contents_header : Any
        Contenido codificado de la cabecera.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    datos = _decodificar_upload_bytes(contents_header)
    return _extraer_parametros_eeg(datos)


def extraer_parametros_eeg_desde_ruta(ruta_header):
    """
    Extrae parametros eeg desde ruta.

    Parámetros
    ----------
    ruta_header : Any
        Ruta utilizada por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    with open(ruta_header, "rb") as archivo:
        return _extraer_parametros_eeg(archivo.read())


def _extraer_parametros_eeg(datos):
    """
    Extrae parametros eeg.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    if len(datos) < 770:
        raise ValueError("El archivo .h_a es demasiado corto.")

    num_canales = struct.unpack_from("<h", datos, 178)[0]
    fs = struct.unpack_from("<i", datos, 186)[0]
    pendiente = struct.unpack_from("<f", datos, 702)[0]
    offset = struct.unpack_from("<f", datos, 766)[0]

    if num_canales not in {2, 4}:
        raise ValueError(
            f"El archivo .h_a indica {num_canales} canales; se esperaban 2 o 4."
        )
    if fs <= 0:
        raise ValueError("La frecuencia de muestreo del .h_a no es válida.")

    return {
        "num_canales": int(num_canales),
        "fs": int(fs),
        "pendiente": float(pendiente),
        "offset": float(offset),
    }


def leer_inicio_ta_desde_upload(contents_ta):
    """
    Lee inicio ta desde upload.

    Parámetros
    ----------
    contents_ta : Any
        Contenido codificado del archivo de inicio.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    texto = _decodificar_upload_bytes(contents_ta).decode(
        "latin1",
        errors="ignore",
    )
    return _interpretar_inicio_ta(texto)


def leer_inicio_ta_desde_ruta(ruta_ta):
    """
    Lee inicio ta desde ruta.

    Parámetros
    ----------
    ruta_ta : Any
        Ruta utilizada por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    with open(ruta_ta, "r", encoding="latin1", errors="ignore") as archivo:
        return _interpretar_inicio_ta(archivo.read())


def _interpretar_inicio_ta(texto):
    """
    Interpreta inicio ta.

    Parámetros
    ----------
    texto : Any
        Texto que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    linea = texto.splitlines()[0].strip() if texto.splitlines() else ""
    inicio = pd.to_datetime(linea, dayfirst=False, errors="coerce")
    if pd.isna(inicio):
        inicio = pd.to_datetime(linea, dayfirst=True, errors="coerce")
    if pd.isna(inicio):
        raise ValueError(
            f"No se pudo interpretar la fecha/hora del archivo .t_a: {linea}"
        )
    return pd.Timestamp(inicio).floor("s")


def _leer_raw_intercalado(contents_raw, num_canales):
    """
    Lee raw intercalado.

    Parámetros
    ----------
    contents_raw : Any
        Contenido codificado de la onda cruda.

    num_canales : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    datos = np.frombuffer(
        _decodificar_upload_bytes(contents_raw),
        dtype="<i2",
    )
    return _dar_forma_raw(datos, num_canales)


def _leer_raw_intercalado_desde_ruta(ruta_raw, num_canales):
    """
    Lee raw intercalado desde ruta.

    Parámetros
    ----------
    ruta_raw : Any
        Ruta utilizada por la función.

    num_canales : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    datos = np.fromfile(ruta_raw, dtype="<i2")
    return _dar_forma_raw(datos, num_canales)


def _dar_forma_raw(datos, num_canales):
    """
    Ejecuta la lógica asociada a dar forma raw.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    num_canales : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    resto = len(datos) % num_canales
    if resto:
        datos = datos[:-resto]
    if datos.size == 0:
        raise ValueError("El archivo de ondas crudas está vacío.")
    return datos.reshape(-1, num_canales)


def _extraer_suavizado_spsmooth(df_spa):
    """
    Extrae suavizado spsmooth.

    Parámetros
    ----------
    df_spa : Any
        DataFrame utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    if "SpSmooth" not in df_spa.columns:
        raise ValueError("El archivo .spa no contiene la columna SpSmooth.")

    valores = pd.to_numeric(df_spa["SpSmooth"], errors="coerce").dropna()
    if valores.empty:
        raise ValueError("SpSmooth no contiene valores numéricos válidos.")

    codigo = int(valores.mode().iloc[0])
    if codigo not in MAPA_SPSMOOTH_SEGUNDOS:
        raise ValueError(f"El código SpSmooth {codigo} no está reconocido.")
    return codigo, MAPA_SPSMOOTH_SEGUNDOS[codigo]


def _extraer_filtro_lofilter(df_spa, valor_predeterminado):
    """
    Leer el código real que hay en la columna LoFilter del .spa. 
    """
    if "LoFilter" not in df_spa.columns:
        return None, float(valor_predeterminado), "predeterminado"

    valores = pd.to_numeric(df_spa["LoFilter"], errors="coerce").dropna()
    if valores.empty:
        return None, float(valor_predeterminado), "predeterminado"

    codigo = int(valores.mode().iloc[0])
    if codigo not in MAPA_LOFILTER_HZ:
        raise ValueError(f"El código LoFilter {codigo} no está reconocido.")
    return codigo, MAPA_LOFILTER_HZ[codigo], "spa"


def _calcular_indices_alineacion(
    inicio_raw,
    timeline_spa,
    fs,
    numero_muestras_raw,
):
    """
    Calcula indices alineacion.

    Parámetros
    ----------
    inicio_raw : Any
        Valor de entrada utilizado por la función.

    timeline_spa : Any
        Valor de entrada utilizado por la función.

    fs : Any
        Valor de entrada utilizado por la función.

    numero_muestras_raw : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    inicio_spa = timeline_spa.iloc[0]
    desfase_s = (inicio_spa - inicio_raw).total_seconds()
    indice_raw_inicial = int(round(desfase_s * fs))
    muestras_objetivo = int(len(timeline_spa) * fs)

    origen_inicio = max(0, indice_raw_inicial)
    destino_inicio = max(0, -indice_raw_inicial)
    disponibles_raw = max(0, numero_muestras_raw - origen_inicio)
    disponibles_destino = max(0, muestras_objetivo - destino_inicio)
    muestras_copiadas = min(disponibles_raw, disponibles_destino)

    return {
        "inicio_raw_ta": inicio_raw,
        "inicio_spa": inicio_spa,
        "fin_spa": timeline_spa.iloc[-1],
        "desfase_spa_menos_raw_s": desfase_s,
        "indice_raw_inicial": indice_raw_inicial,
        "muestras_objetivo": muestras_objetivo,
        "origen_inicio": origen_inicio,
        "destino_inicio": destino_inicio,
        "muestras_copiadas": muestras_copiadas,
        "muestras_raw": numero_muestras_raw,
        "fs": fs,
    }


def _canal_alineado_uv(
    raw,
    canal,
    pendiente,
    offset,
    info_alineacion,
):
    """
    Ejecuta la lógica asociada a canal alineado uv.

    Parámetros
    ----------
    raw : Any
        Valor de entrada utilizado por la función.

    canal : Any
        Valor de entrada utilizado por la función.

    pendiente : Any
        Valor de entrada utilizado por la función.

    offset : Any
        Valor de entrada utilizado por la función.

    info_alineacion : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    señal = np.full(
        info_alineacion["muestras_objetivo"],
        np.nan,
        dtype=np.float64,
    )
    cantidad = info_alineacion["muestras_copiadas"]
    if cantidad:
        origen = info_alineacion["origen_inicio"]
        destino = info_alineacion["destino_inicio"]
        valores = raw[origen : origen + cantidad, canal].astype(np.float64)
        señal[destino : destino + cantidad] = valores * pendiente + offset
    return señal


def _detectar_perdidas_raw_por_segundo(
    raw,
    canal,
    info_alineacion,
    umbral_ceros,
):
    """
    Detecta perdidas raw por segundo.

    Parámetros
    ----------
    raw : Any
        Valor de entrada utilizado por la función.

    canal : Any
        Valor de entrada utilizado por la función.

    info_alineacion : Any
        Valor de entrada utilizado por la función.

    umbral_ceros : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    fs = int(info_alineacion["fs"])
    muestras_objetivo = int(info_alineacion["muestras_objetivo"])
    if muestras_objetivo % fs:
        raise ValueError(
            "La longitud alineada de la onda cruda no contiene segundos completos."
        )

    muestras_cero = np.zeros(muestras_objetivo, dtype=bool)
    muestras_presentes = np.zeros(muestras_objetivo, dtype=bool)
    cantidad = int(info_alineacion["muestras_copiadas"])
    if cantidad:
        origen = int(info_alineacion["origen_inicio"])
        destino = int(info_alineacion["destino_inicio"])
        valores = raw[origen : origen + cantidad, canal]
        muestras_cero[destino : destino + cantidad] = valores == 0
        muestras_presentes[destino : destino + cantidad] = True

    ceros_por_segundo = muestras_cero.reshape(-1, fs).mean(axis=1)
    segundo_incompleto = ~muestras_presentes.reshape(-1, fs).all(axis=1)
    mascara = (ceros_por_segundo >= float(umbral_ceros)) | segundo_incompleto
    diagnostico = {
        "canal": int(canal + 1),
        "segundos_con_ceros": int((ceros_por_segundo > 0).sum()),
        "segundos_ceros_elevados": int(
            (ceros_por_segundo >= float(umbral_ceros)).sum()
        ),
        "segundos_incompletos": int(segundo_incompleto.sum()),
        "proporcion_maxima_ceros": float(ceros_por_segundo.max(initial=0.0)),
    }
    return pd.Series(mascara, dtype=bool), diagnostico


def _proyectar_mascara_raw_a_timeline_dsa(
    mascara_segundos,
    tiempos_s,
    timeline_spa,
    fs,
    ventana_seg,
    paso_seg,
):
    """
    Ejecuta la lógica asociada a proyectar mascara raw a timeline dsa.

    Parámetros
    ----------
    mascara_segundos : Any
        Máscara booleana utilizada para seleccionar o excluir datos.

    tiempos_s : Any
        Valor de entrada utilizado por la función.

    timeline_spa : Any
        Valor de entrada utilizado por la función.

    fs : Any
        Valor de entrada utilizado por la función.

    ventana_seg : Any
        Valor de entrada utilizado por la función.

    paso_seg : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    mascara_segundos = np.asarray(mascara_segundos, dtype=bool)
    muestras_invalidas = np.repeat(mascara_segundos, int(fs))
    nperseg = int(ventana_seg * fs)
    paso = int(paso_seg * fs)
    inicios = np.arange(
        0,
        len(muestras_invalidas) - nperseg + 1,
        paso,
        dtype=np.int64,
    )

    acumulada = np.concatenate(
        ([0], np.cumsum(muestras_invalidas, dtype=np.int64))
    )
    mascara_ventanas = (
        acumulada[inicios + nperseg] - acumulada[inicios]
    ) > 0
    if len(mascara_ventanas) != len(tiempos_s):
        raise ValueError(
            "La máscara de pérdidas raw no coincide con las ventanas Welch."
        )

    inicio = pd.Timestamp(timeline_spa.iloc[0]).floor("s")
    tiempo_ventanas = (
        inicio + pd.to_timedelta(tiempos_s, unit="s")
    ).floor("s")
    mascara = pd.Series(mascara_ventanas, index=tiempo_ventanas)
    if mascara.index.duplicated().any():
        mascara = mascara[~mascara.index.duplicated(keep="last")]
    return (
        mascara.reindex(pd.DatetimeIndex(timeline_spa), fill_value=False)
        .reset_index(drop=True)
        .astype(bool)
    )


def _crear_mascara_raw_para_canal(
    raw,
    canal,
    info_alineacion,
    parametros,
    tiempos_s,
    timeline_spa,
):
    """
    Crea mascara raw para canal.

    Parámetros
    ----------
    raw : Any
        Valor de entrada utilizado por la función.

    canal : Any
        Valor de entrada utilizado por la función.

    info_alineacion : Any
        Valor de entrada utilizado por la función.

    parametros : Any
        Valor de entrada utilizado por la función.

    tiempos_s : Any
        Valor de entrada utilizado por la función.

    timeline_spa : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not parametros["aplicar_mascara_ceros_raw"]:
        return pd.Series(False, index=range(len(timeline_spa))), {
            "canal": int(canal + 1),
            "aplicada": False,
            "segundos_con_ceros": 0,
            "segundos_ceros_elevados": 0,
            "segundos_incompletos": 0,
            "proporcion_maxima_ceros": 0.0,
            "ventanas_welch_afectadas": 0,
        }

    mascara_segundos, diagnostico = _detectar_perdidas_raw_por_segundo(
        raw,
        canal,
        info_alineacion,
        parametros["umbral_ceros_raw"],
    )
    mascara_dsa = _proyectar_mascara_raw_a_timeline_dsa(
        mascara_segundos,
        tiempos_s,
        timeline_spa,
        info_alineacion["fs"],
        parametros["ventana_welch_s"],
        parametros["paso_welch_s"],
    )
    diagnostico.update(
        {
            "aplicada": True,
            "ventanas_welch_afectadas": int(mascara_dsa.sum()),
        }
    )
    return mascara_dsa, diagnostico


def _welch_por_bloques(
    señal,
    fs,
    ventana_seg,
    paso_seg,
    fmin,
    fmax,
    paso_frecuencia,
    modo,
    tiempo_referencia,
    tamaño_bloque=2048,
):
    """
    Ejecuta la lógica asociada a welch por bloques.

    Parámetros
    ----------
    señal : Any
        Valor de entrada utilizado por la función.

    fs : Any
        Valor de entrada utilizado por la función.

    ventana_seg : Any
        Valor de entrada utilizado por la función.

    paso_seg : Any
        Valor de entrada utilizado por la función.

    fmin : Any
        Valor de entrada utilizado por la función.

    fmax : Any
        Valor de entrada utilizado por la función.

    paso_frecuencia : Any
        Valor de entrada utilizado por la función.

    modo : Any
        Valor de entrada utilizado por la función.

    tiempo_referencia : Any
        Valor de entrada utilizado por la función.

    tamaño_bloque : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    nperseg = int(ventana_seg * fs)
    paso = int(paso_seg * fs)
    nfft = int(fs / paso_frecuencia)
    if nperseg <= 0 or paso <= 0 or nfft <= 0:
        raise ValueError("Los parámetros temporales de Welch no son válidos.")
    if len(señal) < nperseg:
        raise ValueError("La señal cruda es más corta que una ventana Welch.")
    if modo not in {"densidad", "potencia"}:
        raise ValueError("El modo Welch debe ser 'densidad' o 'potencia'.")

    inicios = np.arange(0, len(señal) - nperseg + 1, paso, dtype=np.int64)
    indices_ventana = np.arange(nperseg, dtype=np.int64)
    salida = None
    frecuencias_seleccionadas = None

    for bloque_inicio in range(0, len(inicios), tamaño_bloque):
        bloque_inicios = inicios[bloque_inicio : bloque_inicio + tamaño_bloque]
        segmentos = señal[bloque_inicios[:, None] + indices_ventana]
        frecuencias, potencia = welch(
            segmentos,
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=0,
            nfft=nfft,
            detrend="constant",
            scaling="density" if modo == "densidad" else "spectrum",
            axis=-1,
        )

        if frecuencias_seleccionadas is None:
            mascara = (frecuencias >= fmin) & (frecuencias <= fmax)
            frecuencias_seleccionadas = frecuencias[mascara]
            salida = np.empty(
                (len(inicios), int(mascara.sum())),
                dtype=np.float64,
            )

        salida[
            bloque_inicio : bloque_inicio + len(bloque_inicios)
        ] = potencia[:, mascara]

    if tiempo_referencia == "inicio":
        tiempos_s = inicios / fs
    elif tiempo_referencia == "centro":
        tiempos_s = (inicios + nperseg / 2) / fs
    elif tiempo_referencia == "final":
        tiempos_s = (inicios + nperseg) / fs
    else:
        raise ValueError(
            "tiempo_referencia debe ser 'inicio', 'centro' o 'final'."
        )

    return salida, frecuencias_seleccionadas, tiempos_s


def _reconstruir_lado(
    raw,
    canales,
    parametros_header,
    info_alineacion,
    parametros,
):
    """
    Reconstruye lado.

    Parámetros
    ----------
    raw : Any
        Valor de entrada utilizado por la función.

    canales : Any
        Valor de entrada utilizado por la función.

    parametros_header : Any
        Valor de entrada utilizado por la función.

    info_alineacion : Any
        Valor de entrada utilizado por la función.

    parametros : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    acumulada = None
    frecuencias = None
    tiempos_s = None

    for canal in canales:
        señal = _canal_alineado_uv(
            raw,
            canal,
            parametros_header["pendiente"],
            parametros_header["offset"],
            info_alineacion,
        )
        señal = _filtrar_pasa_altos_causal(
            señal,
            parametros_header["fs"],
            parametros["filtro_pasa_altos_hz"],
            parametros["orden_filtro_pasa_altos"],
        )
        potencia, frecuencias, tiempos_s = _welch_por_bloques(
            señal=señal,
            fs=parametros_header["fs"],
            ventana_seg=parametros["ventana_welch_s"],
            paso_seg=parametros["paso_welch_s"],
            fmin=parametros["fmin"],
            fmax=parametros["fmax"],
            paso_frecuencia=parametros["paso_frecuencia"],
            modo=parametros["modo_welch"],
            tiempo_referencia=parametros["tiempo_referencia"],
        )
        if acumulada is None:
            acumulada = potencia
        else:
            acumulada += potencia

    potencia_media = acumulada / len(canales)
    return _convertir_potencia_a_db(
        potencia_media,
        parametros,
    ), frecuencias, tiempos_s


def _convertir_potencia_a_db(potencia, parametros):
    """
    Ejecuta la lógica asociada a convertir potencia a db.

    Parámetros
    ----------
    potencia : Any
        Valor de entrada utilizado por la función.

    parametros : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    potencia = np.asarray(potencia, dtype=np.float64).copy()
    if parametros["modo_welch"] == "densidad":
        # Welch returns uV^2/Hz. Each DSA column covers a 0.5 Hz bin, so
        # integrate the density before comparing it with an RMS power reference.
        potencia *= parametros["paso_frecuencia"]
    referencia_amplitud = parametros["referencia_amplitud_uv_rms"]
    return 10 * np.log10(
        (potencia + 1e-12)
        / (referencia_amplitud ** 2)
    )


def _filtrar_pasa_altos_causal(señal, fs, frecuencia_hz, orden):
    """
    Aplica un filtro Butterworth pasa-altos causal a una señal temporal.

    El filtro atenúa las componentes por debajo de 'frecuencia_hz' antes de la aplicación de la FFT:
     - deriva lenta de la línea base
     - componentes de muy baja frecuencia
    
    La señal se procesa de forma causal mediante 'sosfilt', usa solamente muestras presentes y anteriores.
    Los valores no finitos (NaN e inf) no se filtran. Se mantienen los huecos y divide la señal en bloques válidos para evitar que el filtro propague discontinuidades a través de zonas sin datos. 

    Parámetros:
     - señal: array-like
              señal electroencefalográfica digital temporal, representada como una secuencia de muestras discretas en microvoltios.
     - fs:  float
            frecuencia de muestreo de la señal, en Hz.
     - frecuencia_hz: float
                      frecuencia de corte del filtro pasa - alta, en Hz.
                      Si es <=0 no se filtra la señal y se devuelve una copia de la misma.
                      En el proyecto esta frecuencia viene de LoFilter: 0,25, 1, 2 o 2,5 Hz.
     - orden: int
              orden del filtro Butterworth. 
              Controla lo abruptas que son las transiciones entre las frecuencias que se atenúan y las que se conservan.
              Un filtro de primer orden tiene una transición suave: no elimina de golpe todo lo que queda por debajo del corte, sino que lo atenúa progresivamente.

    Devuelve:
     - salida: ndarray
               Señal filtrada, con la misma longitud que la señal de entrada y expresada también en microvoltios. Las muestras no válidas permanecen como huecos.
    """

    # Convierte la entrada a un array NumPy en coma flotante. 
    # Para representar decimales y NaN.
    señal = np.asarray(señal, dtype=np.float64)

    # Si la frecuencia de corte es 0 o negativa, no tiene sentido aplicar un pasa-altos. 
    # Devuelve la señal sin modificar.
    if frecuencia_hz <= 0:
        return señal.copy()

    """
    Diseño del filtro Butterworth:
     - int(orden): orden del filtro Butterworth. Aquí el orden es 1. 
     - float(frecuencia_hz): las componentes por debajo de esta frecuencia se atenúan y las componentes por encima se conservan más.
     - btype="highpass": el filtro es pasa-altos
     - fs=float(fs): frecuencia de muestro de la señal en Hz. Permite que la frecuencia de corte se interprete en Hz.
     - output="sos": formato en el que SciPy devuelve el filtro. Significa secciones de segundo orden (second-order sections). 
                     
    """
    sos = butter( 
        int(orden),
        float(frecuencia_hz),
        btype="highpass",
        fs=float(fs),
        output="sos",
    )

    # Crea una salida llena de NaN. 
    # Por defecto, todo lo que no pueda filtrarse se mantiene como ausente.
    salida = np.full_like(señal, np.nan)

    # Busca las posiciones donde la señal tiene valores válidos.
    indices_validos = np.flatnonzero(np.isfinite(señal))

    # Si no hay ningún dato válido, devuelve todo NaN
    if not indices_validos.size:
        return salida

    # Detecta saltos entre índices válidos. Separa la señal en bloques continuos (antes y después de un tramo en NaN)
    cortes = np.flatnonzero(np.diff(indices_validos) > 1) + 1

    # Se filtra cada bloque válido por separado
    for bloque in np.split(indices_validos, cortes):
        
        if not bloque.size: # bloque.size indica cuántos elementos tiene ese bloque
            continue # si el bloque está vacío, se salta y pasa al siguiente

        # toma las muestras válidas del bloque
        segmento = señal[bloque]

        # Calcula el estado inicial del filtro suponiendo que antes del bloque
        # la señal era constante e igual a la primera muestra del segmento.
        zi = sosfilt_zi(sos) * segmento[0]

        # Aplica el filtro causal al segmento. Devuelve la señal filtrada y
        # el estado final del filtro (que aquí ignoramos porque filtramos los bloques independientemente)
        filtrado, _ = sosfilt(sos, segmento, zi=zi)

        # Inserta el segmento filtrado en la señal de salida en las mismas posiciones que en la señal de entrada
        salida[bloque] = filtrado
    return salida


def _ajustar_reconstruida_a_timeline(
    matriz,
    frecuencias,
    tiempos_s,
    timeline_spa,
):
    """
    Ejecuta la lógica asociada a ajustar reconstruida a timeline.

    Parámetros
    ----------
    matriz : Any
        Valor de entrada utilizado por la función.

    frecuencias : Any
        Valor de entrada utilizado por la función.

    tiempos_s : Any
        Valor de entrada utilizado por la función.

    timeline_spa : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    columnas = [float(frecuencia) for frecuencia in frecuencias]
    df = pd.DataFrame(matriz, columns=columnas)
    df.insert(0, "tiempo_s", tiempos_s)

    inicio = pd.Timestamp(timeline_spa.iloc[0]).floor("s")
    tiempo = (
        inicio + pd.to_timedelta(df["tiempo_s"], unit="s")
    ).dt.floor("s")
    dsa = df[columnas].copy()
    dsa.index = tiempo
    if dsa.index.duplicated().any():
        dsa = dsa[~dsa.index.duplicated(keep="last")]
    return dsa.reindex(timeline_spa).reset_index(drop=True)


def _alinear_spa(timeline_spa, df_spa):
    """
    Alinea spa.

    Parámetros
    ----------
    timeline_spa : Any
        Valor de entrada utilizado por la función.

    df_spa : Any
        DataFrame utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    df_spa_unico = deduplicar_dataframe_temporal(df_spa, "Time")
    return pd.DataFrame({"Time": timeline_spa}).merge(
        df_spa_unico,
        on="Time",
        how="left",
        validate="one_to_one",
    )



def _calcular_tiempos_ventanas(
    numero_muestras,
    fs,
    ventana_seg,
    paso_seg,
    tiempo_referencia,
):
    """
    Calcula tiempos ventanas.

    Parámetros
    ----------
    numero_muestras : Any
        Valor de entrada utilizado por la función.

    fs : Any
        Valor de entrada utilizado por la función.

    ventana_seg : Any
        Valor de entrada utilizado por la función.

    paso_seg : Any
        Valor de entrada utilizado por la función.

    tiempo_referencia : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    nperseg = int(ventana_seg * fs)
    paso = int(paso_seg * fs)
    inicios = np.arange(
        0,
        numero_muestras - nperseg + 1,
        paso,
        dtype=np.int64,
    )
    if tiempo_referencia == "inicio":
        return inicios / fs
    if tiempo_referencia == "centro":
        return (inicios + nperseg / 2) / fs
    if tiempo_referencia == "final":
        return (inicios + nperseg) / fs
    raise ValueError(
        "tiempo_referencia debe ser 'inicio', 'centro' o 'final'."
    )


def _calcular_mascara_final_comun(
    mascara_base,
    ventana_s,
    shift_s,
    excluir_invalidos_suavizado,
):
    """
    Proyecta sobre la salida suavizada qué segundos pueden contener DSA.

    La máscara base procede únicamente del .spa, la onda cruda y la
    disponibilidad temporal de las ventanas. No depende de si se dibuja
    el .f_a o la reconstrucción.
    """
    mascara_base = pd.Series(mascara_base, dtype=bool).reset_index(drop=True)
    if excluir_invalidos_suavizado:
        disponibilidad = (~mascara_base).astype(int)
    else:
        disponibilidad = pd.Series(
            1,
            index=mascara_base.index,
            dtype=int,
        )

    if ventana_s > 1:
        disponibilidad = (
            disponibilidad.rolling(
                window=int(ventana_s),
                min_periods=1,
                center=False,
            ).sum()
            > 0
        )
    else:
        disponibilidad = disponibilidad.astype(bool)

    desplazada = pd.Series(
        False,
        index=mascara_base.index,
        dtype=bool,
    )
    if shift_s > 0:
        desplazada.iloc[shift_s:] = disponibilidad.iloc[:-shift_s].to_numpy()
    elif shift_s < 0:
        desplazada.iloc[:shift_s] = disponibilidad.iloc[-shift_s:].to_numpy()
    else:
        desplazada.iloc[:] = disponibilidad.to_numpy()

    return mascara_base | ~desplazada


def _calcular_mascaras_comunes(
    modo,
    raw,
    header,
    info_alineacion,
    timeline_spa,
    df_merge,
    tiempos_s,
    suavizado_s,
    parametros,
    tiempos_spa,
    tiempos_fa=None,
):
    """Calcula las máscaras únicas del registro a partir de raw y .spa."""
    inicio = pd.Timestamp(timeline_spa.iloc[0]).floor("s")
    tiempo_ventanas = (
        inicio + pd.to_timedelta(tiempos_s, unit="s")
    ).floor("s")
    disponibilidad_ventanas = pd.Series(
        True,
        index=pd.DatetimeIndex(tiempo_ventanas),
        dtype=bool,
    )
    if disponibilidad_ventanas.index.duplicated().any():
        disponibilidad_ventanas = disponibilidad_ventanas[
            ~disponibilidad_ventanas.index.duplicated(keep="last")
        ]
    disponibilidad_ventanas = (
        disponibilidad_ventanas.reindex(
            pd.DatetimeIndex(timeline_spa),
            fill_value=False,
        )
        .reset_index(drop=True)
        .astype(bool)
    )
    mascara_sin_ventana = ~disponibilidad_ventanas
    mascara_discontinuidad_spa = crear_mascara_discontinuidades(
        timeline_spa,
        tiempos_spa,
    )
    mascara_discontinuidad_fa = (
        crear_mascara_discontinuidades(
            timeline_spa,
            tiempos_fa,
        )
        if tiempos_fa is not None
        else pd.Series(False, index=range(len(timeline_spa)), dtype=bool)
    )
    mascara_discontinuidades = (
        mascara_discontinuidad_spa
        | mascara_discontinuidad_fa
    )
    shift_s = int(
        parametros[
            "shift_bilateral_s"
            if modo == "bilateral"
            else "shift_unilateral_s"
        ]
    )

    lados = (
        {
            "izquierda": (0, "SQI10_izq", "TOTPOW08_izq"),
            "derecha": (2, "SQI10_der", "TOTPOW08_der"),
        }
        if modo == "bilateral"
        else {
            "unilateral": (0, "SQI10", "TOTPOW08"),
        }
    )
    mascaras_entrada = {}
    mascaras_finales = {}
    diagnosticos_raw = {}

    for nombre, (canal, columna_sqi, columna_totpow) in lados.items():
        mascara_raw, diagnostico_raw = _crear_mascara_raw_para_canal(
            raw,
            canal,
            info_alineacion,
            parametros,
            tiempos_s,
            timeline_spa,
        )
        sqi = pd.to_numeric(
            df_merge[columna_sqi],
            errors="coerce",
        ).reset_index(drop=True)
        totpow = pd.to_numeric(
            df_merge[columna_totpow],
            errors="coerce",
        ).reset_index(drop=True)
        mascara_spa = (sqi < parametros["umbral_sqi"]) | totpow.isna()
        mascara_base = (
            mascara_spa
            | mascara_raw.reset_index(drop=True)
            | mascara_discontinuidades
            | mascara_sin_ventana
        ).astype(bool)
        mascara_final = _calcular_mascara_final_comun(
            mascara_base,
            suavizado_s,
            shift_s,
            parametros["excluir_invalidos_suavizado"],
        )

        mascaras_entrada[nombre] = mascara_base
        mascaras_finales[nombre] = mascara_final
        diagnosticos_raw[nombre] = diagnostico_raw

    return {
        "entrada_suavizado": mascaras_entrada,
        "final": mascaras_finales,
        "diagnostico_ceros_raw": diagnosticos_raw,
        "discontinuidades_spa": mascara_discontinuidad_spa,
        "discontinuidades_fa": mascara_discontinuidad_fa,
        "shift_s": shift_s,
    }


def _suavizar_y_desplazar(
    dsa,
    ventana_s,
    shift_s,
    mascara_inicial=None,
):
    """
    Ejecuta la lógica asociada a suavizar y desplazar.

    Parámetros
    ----------
    dsa : Any
        Valor de entrada utilizado por la función.

    ventana_s : Any
        Valor de entrada utilizado por la función.

    shift_s : Any
        Valor de entrada utilizado por la función.

    mascara_inicial : Any
        Máscara booleana utilizada para seleccionar o excluir datos.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    trabajo = dsa.copy()
    if mascara_inicial is not None:
        mascara_inicial = pd.Series(mascara_inicial).reset_index(drop=True)
        if len(mascara_inicial) != len(trabajo):
            raise ValueError(
                "La máscara inicial no coincide con la longitud de la DSA."
            )
        trabajo.loc[mascara_inicial.astype(bool).to_numpy(), :] = np.nan

    if ventana_s > 1:
        suavizada = trabajo.rolling(
            window=int(ventana_s),
            min_periods=1,
            center=False,
        ).mean()
    else:
        suavizada = trabajo

    desplazada = pd.DataFrame(
        np.nan,
        index=suavizada.index,
        columns=suavizada.columns,
    )
    if shift_s > 0:
        desplazada.iloc[shift_s:, :] = suavizada.iloc[:-shift_s, :].to_numpy()
    elif shift_s < 0:
        desplazada.iloc[:shift_s, :] = suavizada.iloc[-shift_s:, :].to_numpy()
    else:
        desplazada.iloc[:, :] = suavizada.to_numpy()
    return desplazada


def _preparar_curva(valores, mask):
    """
    Prepara curva.

    Parámetros
    ----------
    valores : Any
        Valores que se van a procesar.

    mask : Any
        Máscara booleana utilizada para seleccionar o excluir datos.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    curva = pd.to_numeric(valores, errors="coerce").copy()
    curva[(curva < 0.5) | (curva > 30)] = np.nan
    curva.loc[mask.values] = np.nan
    return curva.to_numpy(dtype=float)


def _preparar_bis(valores, mask):
    """
    Prepara bis.

    Parámetros
    ----------
    valores : Any
        Valores que se van a procesar.

    mask : Any
        Máscara booleana utilizada para seleccionar o excluir datos.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    bis = pd.to_numeric(valores, errors="coerce").copy()
    bis[(bis < 0) | (bis > 100)] = np.nan
    bis.loc[mask.values] = np.nan
    return bis.to_numpy(dtype=float)


def _preparar_variable_0_100(valores, mask):
    """
    Prepara variable 0 100.

    Parámetros
    ----------
    valores : Any
        Valores que se van a procesar.

    mask : Any
        Máscara booleana utilizada para seleccionar o excluir datos.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    variable = pd.to_numeric(valores, errors="coerce").copy()
    variable[(variable < 0) | (variable > 100)] = np.nan
    variable.loc[mask.values] = np.nan
    return variable.to_numpy(dtype=float)


def reconstruir_desde_uploads(
    modo,
    contents_header,
    contents_ta,
    contents_raw,
    df_spa,
    parametros=None,
):
    """
    Reconstruye desde uploads.

    Parámetros
    ----------
    modo : Any
        Valor de entrada utilizado por la función.

    contents_header : Any
        Contenido codificado de la cabecera.

    contents_ta : Any
        Contenido codificado del archivo de inicio.

    contents_raw : Any
        Contenido codificado de la onda cruda.

    df_spa : Any
        DataFrame utilizado por la función.

    parametros : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    header = extraer_parametros_eeg_desde_upload(contents_header)
    inicio_raw = leer_inicio_ta_desde_upload(contents_ta)
    raw = _leer_raw_intercalado(contents_raw, header["num_canales"])
    return _reconstruir_desde_datos(
        modo,
        header,
        inicio_raw,
        raw,
        df_spa,
        parametros=parametros,
    )


def reconstruir_desde_rutas(
    modo,
    ruta_header,
    ruta_ta,
    ruta_raw,
    df_spa,
    parametros=None,
    ruta_fa=None,
):
    """
    Reconstruye desde rutas.

    Parámetros
    ----------
    modo : Any
        Valor de entrada utilizado por la función.

    ruta_header : Any
        Ruta utilizada por la función.

    ruta_ta : Any
        Ruta utilizada por la función.

    ruta_raw : Any
        Ruta utilizada por la función.

    df_spa : Any
        DataFrame utilizado por la función.

    parametros : Any
        Valor de entrada utilizado por la función.

    ruta_fa : Any
        Ruta utilizada por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    header = extraer_parametros_eeg_desde_ruta(ruta_header)
    inicio_raw = leer_inicio_ta_desde_ruta(ruta_ta)
    raw = _leer_raw_intercalado_desde_ruta(
        ruta_raw,
        header["num_canales"],
    )
    return _reconstruir_desde_datos(
        modo,
        header,
        inicio_raw,
        raw,
        df_spa,
        parametros=parametros,
        tiempos_fa=(
            cargar_tiempos_fa_desde_ruta(ruta_fa)
            if ruta_fa
            else None
        ),
    )


def calcular_mascaras_comunes_desde_rutas(
    modo,
    ruta_header,
    ruta_ta,
    ruta_raw,
    df_spa,
    parametros=None,
    ruta_fa=None,
):
    """Calcula la máscara del registro sin reconstruir el espectro."""
    parametros_finales = dict(PARAMETROS_RECONSTRUCCION)
    if parametros:
        parametros_finales.update(dict(parametros))

    header = extraer_parametros_eeg_desde_ruta(ruta_header)
    inicio_raw = leer_inicio_ta_desde_ruta(ruta_ta)
    raw = _leer_raw_intercalado_desde_ruta(
        ruta_raw,
        header["num_canales"],
    )
    canales_esperados = 4 if modo == "bilateral" else 2
    if header["num_canales"] != canales_esperados:
        raise ValueError(
            f"El modo {modo} requiere {canales_esperados} canales, pero el "
            f".h_a indica {header['num_canales']}."
        )

    cobertura = calcular_timeline_comun(
        inicio_raw=inicio_raw,
        numero_muestras_raw=len(raw),
        fs=header["fs"],
        tiempos_spa=df_spa["Time"],
        tiempos_fa=(
            cargar_tiempos_fa_desde_ruta(ruta_fa)
            if ruta_fa
            else None
        ),
    )
    timeline_spa = cobertura["timeline"]
    info_alineacion = _calcular_indices_alineacion(
        inicio_raw,
        timeline_spa,
        header["fs"],
        len(raw),
    )
    _codigo_spsmooth, suavizado_s = _extraer_suavizado_spsmooth(df_spa)
    df_merge = _alinear_spa(timeline_spa, df_spa)
    tiempos_s = _calcular_tiempos_ventanas(
        info_alineacion["muestras_objetivo"],
        header["fs"],
        parametros_finales["ventana_welch_s"],
        parametros_finales["paso_welch_s"],
        parametros_finales["tiempo_referencia"],
    )
    resultado = _calcular_mascaras_comunes(
        modo,
        raw,
        header,
        info_alineacion,
        timeline_spa,
        df_merge,
        tiempos_s,
        suavizado_s,
        parametros_finales,
        cobertura["tiempos_spa"],
        cobertura["tiempos_fa"],
    )
    resultado["timeline"] = timeline_spa
    resultado["cobertura_temporal"] = cobertura
    return resultado


def _reconstruir_desde_datos(
    modo,
    header,
    inicio_raw,
    raw,
    df_spa,
    parametros=None,
    tiempos_fa=None,
):
    """
    Reconstruye desde datos.

    Parámetros
    ----------
    modo : Any
        Valor de entrada utilizado por la función.

    header : Any
        Valor de entrada utilizado por la función.

    inicio_raw : Any
        Valor de entrada utilizado por la función.

    raw : Any
        Valor de entrada utilizado por la función.

    df_spa : Any
        DataFrame utilizado por la función.

    parametros : Any
        Valor de entrada utilizado por la función.

    tiempos_fa : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    parametros_finales = dict(PARAMETROS_RECONSTRUCCION)
    if parametros:
        parametros_usuario = dict(parametros)
        if (
            "referencia_potencia" in parametros_usuario
            and "referencia_amplitud_uv_rms" not in parametros_usuario
        ):
            parametros_usuario["referencia_amplitud_uv_rms"] = (
                parametros_usuario.pop("referencia_potencia")
            )
        parametros_finales.update(parametros_usuario)

    canales_esperados = 4 if modo == "bilateral" else 2
    if header["num_canales"] != canales_esperados:
        raise ValueError(
            f"El modo {modo} requiere {canales_esperados} canales, pero el "
            f".h_a indica {header['num_canales']}."
        )

    cobertura_temporal = calcular_timeline_comun(
        inicio_raw=inicio_raw,
        numero_muestras_raw=len(raw),
        fs=header["fs"],
        tiempos_spa=df_spa["Time"],
        tiempos_fa=tiempos_fa,
    )
    timeline_spa = cobertura_temporal["timeline"]
    info_alineacion = _calcular_indices_alineacion(
        inicio_raw,
        timeline_spa,
        header["fs"],
        len(raw),
    )
    codigo_spsmooth, suavizado_s = _extraer_suavizado_spsmooth(df_spa)
    codigo_lofilter, filtro_pasa_altos_hz, origen_lofilter = (
        _extraer_filtro_lofilter(
            df_spa,
            parametros_finales["filtro_pasa_altos_predeterminado_hz"],
        )
    )
    parametros_finales["filtro_pasa_altos_hz"] = filtro_pasa_altos_hz
    df_merge = _alinear_spa(timeline_spa, df_spa)

    if modo == "bilateral":
        matriz_izq, frecuencias, tiempos_s = _reconstruir_lado(
            raw,
            [0],
            header,
            info_alineacion,
            parametros_finales,
        )
        matriz_der, _, _ = _reconstruir_lado(
            raw,
            [2],
            header,
            info_alineacion,
            parametros_finales,
        )
        dsa_izq = _ajustar_reconstruida_a_timeline(
            matriz_izq,
            frecuencias,
            tiempos_s,
            timeline_spa,
        )
        dsa_der = _ajustar_reconstruida_a_timeline(
            matriz_der,
            frecuencias,
            tiempos_s,
            timeline_spa,
        )
        mascaras_comunes = _calcular_mascaras_comunes(
            modo,
            raw,
            header,
            info_alineacion,
            timeline_spa,
            df_merge,
            tiempos_s,
            suavizado_s,
            parametros_finales,
            cobertura_temporal["tiempos_spa"],
            cobertura_temporal["tiempos_fa"],
        )
        mask_izq = mascaras_comunes["entrada_suavizado"]["izquierda"]
        mask_der = mascaras_comunes["entrada_suavizado"]["derecha"]
        mask_izq_final = mascaras_comunes["final"]["izquierda"]
        mask_der_final = mascaras_comunes["final"]["derecha"]
        shift_s = mascaras_comunes["shift_s"]
        mascara_suavizado_izq = (
            mask_izq
            if parametros_finales["excluir_invalidos_suavizado"]
            else None
        )
        mascara_suavizado_der = (
            mask_der
            if parametros_finales["excluir_invalidos_suavizado"]
            else None
        )
        dsa_izq = _suavizar_y_desplazar(
            dsa_izq,
            suavizado_s,
            shift_s,
            mascara_inicial=mascara_suavizado_izq,
        )
        dsa_der = _suavizar_y_desplazar(
            dsa_der,
            suavizado_s,
            shift_s,
            mascara_inicial=mascara_suavizado_der,
        )
        dsa_izq.loc[mask_izq_final.values, :] = np.nan
        dsa_der.loc[mask_der_final.values, :] = np.nan

        asimetria = pd.to_numeric(
            df_merge["ASYM09"],
            errors="coerce",
        ).copy()
        asimetria.loc[(mask_izq_final | mask_der_final).values] = np.nan
        registro = {
            "modo": "bilateral",
            "origen": "reconstruida",
            "tiempo": timeline_spa.reset_index(drop=True),
            "frecuencias": np.asarray(frecuencias, dtype=float),
            "matriz_izq": dsa_izq.to_numpy(dtype=float),
            "matriz_der": dsa_der.to_numpy(dtype=float),
            "sef_izq": _preparar_curva(
                df_merge["SEF08_izq"],
                mask_izq_final,
            ),
            "mef_izq": _preparar_curva(
                df_merge["MEDFRQ08_izq"],
                mask_izq_final,
            ),
            "sef_der": _preparar_curva(
                df_merge["SEF08_der"],
                mask_der_final,
            ),
            "mef_der": _preparar_curva(
                df_merge["MEDFRQ08_der"],
                mask_der_final,
            ),
            "bis_izq": _preparar_bis(
                df_merge["DB13U01_izq"],
                mask_izq_final,
            ),
            "bis_der": _preparar_bis(
                df_merge["DB13U01_der"],
                mask_der_final,
            ),
            "emg_izq": _preparar_variable_0_100(
                df_merge["EMGLOW01_izq"],
                mask_izq_final,
            ),
            "emg_der": _preparar_variable_0_100(
                df_merge["EMGLOW01_der"],
                mask_der_final,
            ),
            "sr_izq": _preparar_variable_0_100(
                df_merge["SR12_izq"],
                mask_izq_final,
            ),
            "sr_der": _preparar_variable_0_100(
                df_merge["SR12_der"],
                mask_der_final,
            ),
            "asimetria": asimetria.to_numpy(dtype=float),
        }
        mascaras = {
            "izquierda": int(mask_izq_final.sum()),
            "derecha": int(mask_der_final.sum()),
        }
        mascaras_entrada_suavizado = {
            "izquierda": int(mask_izq.sum()),
            "derecha": int(mask_der.sum()),
        }
        diagnostico_ceros_raw = mascaras_comunes["diagnostico_ceros_raw"]
    else:
        matriz, frecuencias, tiempos_s = _reconstruir_lado(
            raw,
            [0],
            header,
            info_alineacion,
            parametros_finales,
        )
        dsa = _ajustar_reconstruida_a_timeline(
            matriz,
            frecuencias,
            tiempos_s,
            timeline_spa,
        )
        mascaras_comunes = _calcular_mascaras_comunes(
            modo,
            raw,
            header,
            info_alineacion,
            timeline_spa,
            df_merge,
            tiempos_s,
            suavizado_s,
            parametros_finales,
            cobertura_temporal["tiempos_spa"],
            cobertura_temporal["tiempos_fa"],
        )
        mask = mascaras_comunes["entrada_suavizado"]["unilateral"]
        mask_final = mascaras_comunes["final"]["unilateral"]
        shift_s = mascaras_comunes["shift_s"]
        mascara_suavizado = (
            mask
            if parametros_finales["excluir_invalidos_suavizado"]
            else None
        )
        dsa = _suavizar_y_desplazar(
            dsa,
            suavizado_s,
            shift_s,
            mascara_inicial=mascara_suavizado,
        )
        dsa.loc[mask_final.values, :] = np.nan
        registro = {
            "modo": "unilateral",
            "origen": "reconstruida",
            "tiempo": timeline_spa.reset_index(drop=True),
            "frecuencias": np.asarray(frecuencias, dtype=float),
            "matriz": dsa.to_numpy(dtype=float),
            "sef": _preparar_curva(df_merge["SEF08"], mask_final),
            "mef": _preparar_curva(df_merge["MEDFRQ08"], mask_final),
            "bis": _preparar_bis(df_merge["DB13U01"], mask_final),
            "emg": _preparar_variable_0_100(
                df_merge["EMGLOW01"],
                mask_final,
            ),
            "sr": _preparar_variable_0_100(
                df_merge["SR12"],
                mask_final,
            ),
        }
        mascaras = {
            "unilateral": int(mask_final.sum()),
        }
        mascaras_entrada_suavizado = {
            "unilateral": int(mask.sum()),
        }
        diagnostico_ceros_raw = mascaras_comunes["diagnostico_ceros_raw"]

    registro["parametros_reconstruccion"] = {
        **parametros_finales,
        "spsmooth_codigo": codigo_spsmooth,
        "suavizado_s": int(suavizado_s),
        "lofilter_codigo": codigo_lofilter,
        "lofilter_origen": origen_lofilter,
        "shift_s": shift_s,
        "num_canales": header["num_canales"],
        "fs": header["fs"],
        "pendiente": header["pendiente"],
        "offset": header["offset"],
        "mascaras": mascaras,
        "mascaras_entrada_suavizado": mascaras_entrada_suavizado,
        "diagnostico_ceros_raw": diagnostico_ceros_raw,
        "alineacion": info_alineacion,
        "cobertura_temporal": cobertura_temporal,
    }
    return registro
