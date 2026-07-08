from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd

from src.carpeta_bis import detectar_exportacion_bis


VERSION_SINTESIS = "2.4"
SEMILLA_BASE = 20260629

RANGOS_GASOMETRIA = {
    "arterial": {
        "po2": (80.0, 100.0),
        "pco2": (35.0, 45.0),
    },
    "venosa": {
        "po2": (24.0, 40.0),
        "pco2": (41.0, 51.0),
    },
}

COLUMNAS_AUDITORIA_GASOMETRIA = [
    "tipo_gasometria_final",
    "origen_tipo_gasometria",
    "confianza_inferencia",
    "incluida_visualizacion",
    "criterios_inferencia",
    "motivo_exclusion",
]

# Límites técnicos amplios para la simulación. No son intervalos clínicos.
CONFIGURACION_SERIES = {
    "fc": {"limites": (20.0, 250.0), "cambio_max_s": 3.0, "ruido": 0.8},
    "spo2": {"limites": (50.0, 100.0), "cambio_max_s": 1.0, "ruido": 0.18},
    "pic": {"limites": (-5.0, 80.0), "cambio_max_s": 2.0, "ruido": 0.35},
    "frecuencia_respiratoria": {
        "limites": (2.0, 80.0),
        "cambio_max_s": 1.0,
        "ruido": 0.25,
    },
    "temperatura": {
        "limites": (30.0, 43.0),
        "cambio_max_s": 0.08,
        "ruido": 0.025,
    },
    "pa_sistolica": {
        "limites": (40.0, 280.0),
        "cambio_max_s": 5.0,
        "ruido": 0.8,
    },
    "pa_diastolica": {
        "limites": (20.0, 180.0),
        "cambio_max_s": 5.0,
        "ruido": 0.6,
    },
    "pa_media": {
        "limites": (25.0, 220.0),
        "cambio_max_s": 5.0,
        "ruido": 0.6,
    },
}


def _normalizar(texto):
    """
    Ejecuta la lógica asociada a normalizar.

    Parámetros
    ----------
    texto : Any
        Texto que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r"[^a-z0-9]+", "_", texto.casefold()).strip("_")


def _tipo_gasometria_explicito(valor):
    """
    Ejecuta la lógica asociada a tipo gasometria explicito.

    Parámetros
    ----------
    valor : Any
        Valor que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    normalizado = _normalizar(valor)
    if "arterial" in normalizado:
        return "arterial"
    if "venos" in normalizado:
        return "venosa"
    return None


def _fila_marcada_fuera_de_rango(fila):
    """
    Ejecuta la lógica asociada a fila marcada fuera de rango.

    Parámetros
    ----------
    fila : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    marca = str(fila.get("marca_original") or "")
    detalle = str(fila.get("detalle_original") or "")
    fuera = _normalizar(fila.get("fuera_rango_uci")) in {
        "si",
        "true",
        "1",
    }
    return fuera or "^" in marca or "^" in detalle


def _evidencias_tipo_gasometria(grupo):
    """
    Ejecuta la lógica asociada a evidencias tipo gasometria.

    Parámetros
    ----------
    grupo : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    evidencias = []
    for _, fila in grupo.iterrows():
        variable = _normalizar(fila.get("variable"))
        valor = pd.to_numeric(pd.Series([fila.get("valor")]), errors="coerce").iloc[0]
        if variable not in {"po2", "pco2"} or pd.isna(valor):
            continue

        if variable == "po2" and float(valor) < 60.0:
            evidencias.append(
                ("venosa", "pO2 < 60 mmHg (criterio contextual indicado por la UCI)")
            )

        if not _fila_marcada_fuera_de_rango(fila):
            continue
        fuera_arterial = not (
            RANGOS_GASOMETRIA["arterial"][variable][0]
            <= float(valor)
            <= RANGOS_GASOMETRIA["arterial"][variable][1]
        )
        fuera_venosa = not (
            RANGOS_GASOMETRIA["venosa"][variable][0]
            <= float(valor)
            <= RANGOS_GASOMETRIA["venosa"][variable][1]
        )
        if fuera_arterial != fuera_venosa:
            tipo = "arterial" if fuera_arterial else "venosa"
            evidencias.append(
                (
                    tipo,
                    f"marca ^ compatible unicamente con el rango {tipo} de {variable}",
                )
            )
    return evidencias


def preparar_auditoria_gasometrias(analisis):
    """Clasifica gasometrias sin alterar las mediciones originales."""
    columnas_origen = list(analisis.columns) if isinstance(analisis, pd.DataFrame) else []
    columnas_salida = columnas_origen + [
        columna
        for columna in COLUMNAS_AUDITORIA_GASOMETRIA
        if columna not in columnas_origen
    ]
    if (
        not isinstance(analisis, pd.DataFrame)
        or analisis.empty
        or "variable" not in analisis.columns
    ):
        return pd.DataFrame(columns=columnas_salida)

    gasometrias = analisis.copy()
    gasometrias["_variable_normalizada"] = gasometrias["variable"].map(_normalizar)
    gasometrias = gasometrias[
        gasometrias["_variable_normalizada"].isin({"po2", "pco2"})
    ].copy()
    if gasometrias.empty:
        return pd.DataFrame(columns=columnas_salida)

    for columna in COLUMNAS_AUDITORIA_GASOMETRIA:
        gasometrias[columna] = None

    columnas_grupo = [
        columna
        for columna in [
            "timestamp",
            "fuente_pdf",
            "bloque_origen",
            "origen_pdf",
        ]
        if columna in gasometrias.columns
    ]
    if not columnas_grupo:
        gasometrias["_grupo_gasometria"] = range(len(gasometrias))
        columnas_grupo = ["_grupo_gasometria"]

    for _, grupo in gasometrias.groupby(columnas_grupo, dropna=False, sort=False):
        indices = grupo.index
        tipos_explicitos = {
            tipo
            for tipo in grupo.get("tipo_gasometria", pd.Series(dtype=object)).map(
                _tipo_gasometria_explicito
            )
            if tipo
        }
        if len(tipos_explicitos) > 1:
            gasometrias.loc[indices, "origen_tipo_gasometria"] = "indeterminado"
            gasometrias.loc[indices, "incluida_visualizacion"] = "no"
            gasometrias.loc[indices, "motivo_exclusion"] = (
                "Tipos de gasometria explicitos contradictorios en el mismo instante"
            )
            continue
        if len(tipos_explicitos) == 1:
            tipo = next(iter(tipos_explicitos))
            gasometrias.loc[indices, "tipo_gasometria_final"] = tipo
            gasometrias.loc[indices, "origen_tipo_gasometria"] = "indicado"
            gasometrias.loc[indices, "confianza_inferencia"] = "no_aplica"
            gasometrias.loc[indices, "incluida_visualizacion"] = "si"
            gasometrias.loc[indices, "criterios_inferencia"] = (
                "Tipo indicado en el documento ICCA"
            )
            continue

        variables_validas = set(
            grupo.loc[
                pd.to_numeric(grupo["valor"], errors="coerce").notna(),
                "_variable_normalizada",
            ]
        )
        if not {"po2", "pco2"}.issubset(variables_validas):
            gasometrias.loc[indices, "origen_tipo_gasometria"] = "indeterminado"
            gasometrias.loc[indices, "incluida_visualizacion"] = "no"
            gasometrias.loc[indices, "motivo_exclusion"] = (
                "Tipo no indicado y gasometria incompleta: se requieren pO2 y pCO2 "
                "del mismo instante"
            )
            continue

        evidencias = _evidencias_tipo_gasometria(grupo)
        tipos_inferidos = {tipo for tipo, _ in evidencias}
        if len(tipos_inferidos) == 1:
            tipo = next(iter(tipos_inferidos))
            criterios = list(dict.fromkeys(motivo for _, motivo in evidencias))
            gasometrias.loc[indices, "tipo_gasometria_final"] = tipo
            gasometrias.loc[indices, "origen_tipo_gasometria"] = "inferido"
            gasometrias.loc[indices, "confianza_inferencia"] = (
                "alta" if len(criterios) >= 2 else "moderada"
            )
            gasometrias.loc[indices, "incluida_visualizacion"] = "si"
            gasometrias.loc[indices, "criterios_inferencia"] = "; ".join(criterios)
        elif len(tipos_inferidos) > 1:
            gasometrias.loc[indices, "origen_tipo_gasometria"] = "indeterminado"
            gasometrias.loc[indices, "incluida_visualizacion"] = "no"
            gasometrias.loc[indices, "criterios_inferencia"] = "; ".join(
                dict.fromkeys(motivo for _, motivo in evidencias)
            )
            gasometrias.loc[indices, "motivo_exclusion"] = (
                "Indicios contradictorios sobre el tipo de gasometria"
            )
        else:
            gasometrias.loc[indices, "origen_tipo_gasometria"] = "indeterminado"
            gasometrias.loc[indices, "incluida_visualizacion"] = "no"
            gasometrias.loc[indices, "motivo_exclusion"] = (
                "Tipo no indicado; la pareja pO2/pCO2 no permite una inferencia "
                "coherente con las reglas acordadas"
            )

    gasometrias = gasometrias.drop(
        columns=["_variable_normalizada", "_grupo_gasometria"],
        errors="ignore",
    )
    return gasometrias.reindex(columns=columnas_salida)


def _variable_base(nombre):
    """
    Ejecuta la lógica asociada a variable base.

    Parámetros
    ----------
    nombre : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    normalizada = _normalizar(nombre)
    equivalencias = {
        "fc": "fc",
        "frecuencia_cardiaca": "fc",
        "spo2": "spo2",
        "pic": "pic",
        "frecuencia_respiratoria": "frecuencia_respiratoria",
        "fr": "frecuencia_respiratoria",
        "temperatura": "temperatura",
        "temp": "temperatura",
    }
    if normalizada in {"presion_arterial", "pa", "pa_invasiva"}:
        return "presion_arterial"
    return equivalencias.get(normalizada)


def _semilla_serie(paciente_id, sesion_id, serie):
    """
    Ejecuta la lógica asociada a semilla serie.

    Parámetros
    ----------
    paciente_id : Any
        Identificador del paciente.

    sesion_id : Any
        Identificador de la sesión.

    serie : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    texto = f"{SEMILLA_BASE}|{paciente_id}|{sesion_id}|{serie}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(texto).digest()[:8], "big")


def _prioridad_fuente(variable, fuente):
    """
    Ejecuta la lógica asociada a prioridad fuente.

    Parámetros
    ----------
    variable : Any
        Valor de entrada utilizado por la función.

    fuente : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    fuente = _normalizar(fuente)
    preferida = {
        "temperatura": "tcae",
        "pic": "neurocritico_monitorizado",
        "fc": "ventilatoria",
        "spo2": "ventilatoria",
        "frecuencia_respiratoria": "ventilatoria",
        "presion_arterial": "ventilatoria",
    }.get(variable)
    return (0 if preferida and preferida in fuente else 1, fuente)


def _ruido_suave_puente(longitud, rng, amplitud):
    """
    Ejecuta la lógica asociada a ruido suave puente.

    Parámetros
    ----------
    longitud : Any
        Valor de entrada utilizado por la función.

    rng : Any
        Valor de entrada utilizado por la función.

    amplitud : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if longitud <= 2 or amplitud <= 0:
        return np.zeros(longitud, dtype=float)
    ruido = rng.normal(0.0, amplitud, longitud)
    ventana = min(31, longitud if longitud % 2 else longitud - 1)
    ventana = max(3, ventana)
    relleno = ventana // 2
    extendido = np.pad(ruido, (relleno, relleno), mode="reflect")
    suave = np.convolve(extendido, np.ones(ventana) / ventana, mode="valid")
    suave = suave[:longitud]
    puente = suave - np.linspace(suave[0], suave[-1], longitud)
    puente[0] = 0.0
    puente[-1] = 0.0
    return puente


def _interpolar_controlada(reales, indice, configuracion, semilla):
    """
    Ejecuta la lógica asociada a interpolar controlada.

    Parámetros
    ----------
    reales : Any
        Valor de entrada utilizado por la función.

    indice : Any
        Valor de entrada utilizado por la función.

    configuracion : Any
        Valor de entrada utilizado por la función.

    semilla : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    resultado = pd.Series(np.nan, index=indice, dtype=float)
    tipo = pd.Series(pd.NA, index=indice, dtype="object")
    reales = reales.dropna().sort_index()
    reales = reales[~reales.index.duplicated(keep="last")]
    reales.index = reales.index.round("s")
    reales = reales[~reales.index.duplicated(keep="last")]
    reales = reales[reales.index.isin(indice)]
    if reales.empty:
        return resultado, tipo

    posiciones = indice.get_indexer(reales.index)
    valores = reales.to_numpy(dtype=float)
    rng = np.random.default_rng(semilla)
    limites = configuracion["limites"]
    cambio_maximo = float(configuracion["cambio_max_s"])

    for posicion, valor in zip(posiciones, valores):
        resultado.iloc[posicion] = valor
        tipo.iloc[posicion] = "real"

    for numero in range(len(posiciones) - 1):
        inicio = int(posiciones[numero])
        fin = int(posiciones[numero + 1])
        if fin <= inicio + 1:
            continue
        valor_inicio = float(valores[numero])
        valor_fin = float(valores[numero + 1])
        longitud = fin - inicio + 1
        base = np.linspace(valor_inicio, valor_fin, longitud)
        ruido = _ruido_suave_puente(longitud, rng, configuracion["ruido"])

        pendiente_base = abs(valor_fin - valor_inicio) / max(1, fin - inicio)
        margen_cambio = max(0.0, cambio_maximo - pendiente_base)
        cambio_ruido = np.max(np.abs(np.diff(ruido))) if longitud > 1 else 0.0
        if cambio_ruido > margen_cambio and cambio_ruido > 0:
            ruido *= margen_cambio / cambio_ruido

        sintetica = base + ruido
        if limites[0] <= valor_inicio <= limites[1] and limites[0] <= valor_fin <= limites[1]:
            sintetica[1:-1] = np.clip(sintetica[1:-1], *limites)
        sintetica[0] = valor_inicio
        sintetica[-1] = valor_fin

        resultado.iloc[inicio : fin + 1] = sintetica
        tipo.iloc[inicio + 1 : fin] = "sintetico"
        tipo.iloc[inicio] = "real"
        tipo.iloc[fin] = "real"

    return resultado, tipo


def listar_pacientes(carpeta_raiz):
    """
    Lista pacientes.

    Parámetros
    ----------
    carpeta_raiz : Any
        Carpeta raíz donde se almacenan los pacientes.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    raiz = Path(carpeta_raiz or "").expanduser()
    if not raiz.is_dir():
        raise ValueError("La ruta seleccionada no es una carpeta válida.")
    pacientes = []
    for manifiesto in sorted(raiz.glob("*/paciente.json")):
        try:
            datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        datos["_carpeta"] = str(manifiesto.parent.resolve())
        pacientes.append(datos)
    if not pacientes:
        raise ValueError("No se encontraron carpetas de pacientes con paciente.json.")
    return pacientes


def cargar_paciente(carpeta_raiz, paciente_id):
    """
    Carga paciente.

    Parámetros
    ----------
    carpeta_raiz : Any
        Carpeta raíz donde se almacenan los pacientes.

    paciente_id : Any
        Identificador del paciente.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    for paciente in listar_pacientes(carpeta_raiz):
        if paciente.get("paciente_id") == paciente_id:
            return paciente
    raise ValueError(f"No se encontró {paciente_id} en la carpeta seleccionada.")


def _resolver_ruta(carpeta_paciente, valor):
    """
    Resuelve ruta.

    Parámetros
    ----------
    carpeta_paciente : Any
        Valor de entrada utilizado por la función.

    valor : Any
        Valor que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not valor:
        return None
    ruta = Path(valor or "")
    if not ruta.is_absolute():
        ruta = Path(carpeta_paciente) / ruta
    return ruta.resolve()


def _detectar_bis_con_cache(carpeta_bis):
    """
    Detecta bis con cache.

    Parámetros
    ----------
    carpeta_bis : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    carpeta_bis = Path(carpeta_bis).resolve()
    carpeta_sesion = carpeta_bis.parent.parent
    cache = carpeta_sesion / "resumen_visualizador.json"
    archivos_bis = [ruta for ruta in carpeta_bis.rglob("*") if ruta.is_file()]
    ultima_modificacion = max(
        (ruta.stat().st_mtime for ruta in archivos_bis),
        default=0,
    )
    if cache.is_file() and cache.stat().st_mtime >= ultima_modificacion:
        try:
            deteccion_cache = json.loads(cache.read_text(encoding="utf-8"))
            carpeta_cache = Path(deteccion_cache.get("carpeta") or "")
            if carpeta_cache.is_absolute() and carpeta_cache.resolve() == carpeta_bis:
                return deteccion_cache
        except (OSError, json.JSONDecodeError):
            pass
    deteccion = detectar_exportacion_bis(carpeta_bis)
    temporal = cache.with_suffix(".temporal.json")
    temporal.write_text(
        json.dumps(deteccion, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporal, cache)
    return deteccion


def _ruta_metadatos_sintesis(ruta):
    """
    Ejecuta la lógica asociada a ruta metadatos sintesis.

    Parámetros
    ----------
    ruta : Any
        Ruta del archivo o carpeta que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    return Path(ruta).with_suffix(".meta.json")


def _registros_json(dataframe):
    """
    Ejecuta la lógica asociada a registros json.

    Parámetros
    ----------
    dataframe : Any
        DataFrame de entrada.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if dataframe is None or dataframe.empty:
        return []
    return json.loads(
        dataframe.to_json(
            orient="records",
            date_format="iso",
        )
    )


def _resumen_sintetico_existente(ruta, origen=None, inicio=None, fin=None):
    """
    Ejecuta la lógica asociada a resumen sintetico existente.

    Parámetros
    ----------
    ruta : Any
        Ruta del archivo o carpeta que se va a procesar.

    origen : Any
        Valor de entrada utilizado por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    ruta = Path(ruta)
    ruta_metadatos = _ruta_metadatos_sintesis(ruta)
    try:
        metadata = json.loads(ruta_metadatos.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if str(metadata.get("version")) != VERSION_SINTESIS:
        return None
    if origen is not None:
        origen = Path(origen)
        if (
            int(metadata.get("origen_tamano", -1)) != origen.stat().st_size
            or int(metadata.get("origen_mtime_ns", -1)) != origen.stat().st_mtime_ns
        ):
            return None
    if inicio is not None and metadata.get("inicio_bis") != pd.Timestamp(inicio).isoformat():
        return None
    if fin is not None and metadata.get("fin_bis") != pd.Timestamp(fin).isoformat():
        return None
    return {
        "ruta": str(ruta),
        "ruta_metadatos": str(ruta_metadatos),
        "formato": "csv",
        "filas": int(metadata.get("filas_segundo", 0)),
        "series": int(metadata.get("series_generadas", 0)),
        "mediciones_reales": int(metadata.get("mediciones_reales", 0)),
        "gasometrias_incluidas": int(
            metadata.get("gasometrias_incluidas_visualizacion", 0)
        ),
        "gasometrias_excluidas": int(
            metadata.get("gasometrias_excluidas_visualizacion", 0)
        ),
    }


def generar_icca_sintetico(
    ruta_icca,
    inicio,
    fin,
    paciente_id,
    sesion_id,
    ruta_salida=None,
):
    """
    Genera icca sintetico.

    Parámetros
    ----------
    ruta_icca : Any
        Ruta utilizada por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    paciente_id : Any
        Identificador del paciente.

    sesion_id : Any
        Identificador de la sesión.

    ruta_salida : Any
        Ruta utilizada por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.

    Lanza
    -----
    FileNotFoundError
        Si se produce una condición no válida durante la ejecución.
    ValueError
        Si se produce una condición no válida durante la ejecución.
    """
    origen = Path(ruta_icca).resolve()
    if not origen.is_file():
        raise FileNotFoundError("No existe el Excel ICCA auxiliar de la sesión.")
    salida = (
        Path(ruta_salida).resolve()
        if ruta_salida
        else origen.with_name(f"{origen.stem}_sintetico.csv")
    )
    salida = salida.with_suffix(".csv")
    if salida.is_file() and salida.stat().st_mtime >= origen.stat().st_mtime:
        resumen = _resumen_sintetico_existente(salida, origen=origen)
        if resumen:
            return resumen

    inicio = pd.Timestamp(inicio).floor("s")
    fin = pd.Timestamp(fin).floor("s")
    if pd.isna(inicio) or pd.isna(fin) or fin < inicio:
        raise ValueError("El intervalo BIS de la sesión no es válido.")

    constantes = pd.read_excel(
        origen,
        sheet_name="constantes_vitales",
        header=2,
        engine="openpyxl",
    )
    if "timestamp" not in constantes.columns:
        raise ValueError("La hoja constantes_vitales no contiene timestamp.")
    constantes["timestamp"] = pd.to_datetime(constantes["timestamp"], errors="coerce")
    constantes = constantes[
        constantes["timestamp"].between(inicio, fin, inclusive="both")
    ].copy()
    try:
        analisis = pd.read_excel(
            origen,
            sheet_name="analisis",
            header=2,
            engine="openpyxl",
        )
        if "timestamp" in analisis.columns:
            analisis["timestamp"] = pd.to_datetime(
                analisis["timestamp"], errors="coerce"
            )
            analisis = analisis[
                analisis["timestamp"].between(inicio, fin, inclusive="both")
            ].copy()
    except (ValueError, KeyError):
        analisis = pd.DataFrame()
    auditoria_gasometrias = preparar_auditoria_gasometrias(analisis)
    gasometrias_incluidas = int(
        auditoria_gasometrias.get(
            "incluida_visualizacion", pd.Series(dtype=object)
        ).eq("si").sum()
    )
    gasometrias_excluidas = int(
        auditoria_gasometrias.get(
            "incluida_visualizacion", pd.Series(dtype=object)
        ).eq("no").sum()
    )

    indice = pd.date_range(inicio, fin, freq="s")
    salida_segundo = pd.DataFrame({"timestamp": indice})
    metadatos_series = []
    mediciones_reales = 0
    series_reales = [[] for _ in range(len(indice))]
    constantes["_variable_base"] = constantes["variable"].map(_variable_base)

    for base, grupo_variable in constantes.dropna(subset=["_variable_base"]).groupby(
        "_variable_base"
    ):
        fuentes = sorted(
            grupo_variable["fuente_pdf"].dropna().unique(),
            key=lambda fuente: _prioridad_fuente(base, fuente),
        )
        fuente = fuentes[0] if fuentes else "origen_no_indicado"
        grupo = grupo_variable[
            grupo_variable["fuente_pdf"].fillna("origen_no_indicado") == fuente
        ]
        fuente_texto = str(fuente or "origen_no_indicado")
        componentes = []
        if base == "presion_arterial":
            componentes = [
                ("pa_sistolica", "pa_sistolica_mmHg", "mmHg"),
                ("pa_diastolica", "pa_diastolica_mmHg", "mmHg"),
                ("pa_media", "pa_media_mmHg", "mmHg"),
            ]
        else:
            unidad = next(
                (str(valor) for valor in grupo.get("unidad", []) if pd.notna(valor)),
                "",
            )
            componentes = [(base, "valor", unidad)]

        for nombre_serie, columna_valor, unidad in componentes:
            if columna_valor not in grupo.columns:
                continue
            valores = pd.to_numeric(grupo[columna_valor], errors="coerce")
            reales = pd.Series(valores.to_numpy(), index=grupo["timestamp"])
            reales = reales.dropna()
            if reales.empty:
                continue
            clave = nombre_serie
            configuracion = CONFIGURACION_SERIES[nombre_serie]
            interpolada, tipo = _interpolar_controlada(
                reales,
                indice,
                configuracion,
                _semilla_serie(paciente_id, sesion_id, clave),
            )
            salida_segundo[f"{clave}__valor"] = interpolada.to_numpy()
            mascara_real = tipo.eq("real").fillna(False).to_numpy(dtype=bool)
            for posicion in np.flatnonzero(mascara_real):
                series_reales[int(posicion)].append(clave)
            cantidad_reales = int(mascara_real.sum())
            mediciones_reales += cantidad_reales
            metadatos_series.append(
                {
                    "serie": clave,
                    "variable": nombre_serie,
                    "fuente": fuente_texto,
                    "unidad": unidad,
                    "limite_tecnico_inferior": configuracion["limites"][0],
                    "limite_tecnico_superior": configuracion["limites"][1],
                    "cambio_maximo_por_segundo": configuracion["cambio_max_s"],
                    "amplitud_variacion": configuracion["ruido"],
                    "mediciones_reales": cantidad_reales,
                }
            )
    salida_segundo["series_reales"] = [";".join(series) or None for series in series_reales]

    metadata_json = {
        "version": VERSION_SINTESIS,
        "formato": "csv",
        "paciente_id": paciente_id,
        "sesion_bis_id": sesion_id,
        "inicio_bis": inicio.isoformat(),
        "fin_bis": fin.isoformat(),
        "filas_segundo": len(salida_segundo),
        "series_generadas": len(metadatos_series),
        "mediciones_reales": mediciones_reales,
        "gasometrias_incluidas_visualizacion": gasometrias_incluidas,
        "gasometrias_excluidas_visualizacion": gasometrias_excluidas,
        "semilla_base": SEMILLA_BASE,
        "origen_tamano": origen.stat().st_size,
        "origen_mtime_ns": origen.stat().st_mtime_ns,
        "aviso": (
            "Constantes vitales simuladas a partir de mediciones intermitentes. "
            "No aptas para validación clínica ni correlaciones reales con BIS."
        ),
        "series_sinteticas": metadatos_series,
        "gasometrias_auditoria": _registros_json(auditoria_gasometrias),
    }

    salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_metadatos = _ruta_metadatos_sintesis(salida)
    identificador_temporal = uuid4().hex
    temporal_csv = salida.with_name(
        f".{salida.stem}.{identificador_temporal}.temporal.csv"
    )
    temporal_json = ruta_metadatos.with_name(
        f".{ruta_metadatos.stem}.{identificador_temporal}.temporal.json"
    )
    try:
        salida_segundo.to_csv(
            temporal_csv,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
        )
        temporal_json.write_text(
            json.dumps(metadata_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporal_csv, salida)
        os.replace(temporal_json, ruta_metadatos)
    finally:
        for temporal in [temporal_csv, temporal_json]:
            if temporal.exists():
                temporal.unlink()

    return {
        "ruta": str(salida),
        "ruta_metadatos": str(ruta_metadatos),
        "formato": "csv",
        "filas": len(salida_segundo),
        "series": len(metadatos_series),
        "mediciones_reales": mediciones_reales,
        "gasometrias_incluidas": gasometrias_incluidas,
        "gasometrias_excluidas": gasometrias_excluidas,
    }

def preparar_sesiones_paciente(carpeta_raiz, paciente_id, generar_sinteticos=True):
    """
    Prepara sesiones paciente.

    Parámetros
    ----------
    carpeta_raiz : Any
        Carpeta raíz donde se almacenan los pacientes.

    paciente_id : Any
        Identificador del paciente.

    generar_sinteticos : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    paciente = cargar_paciente(carpeta_raiz, paciente_id)
    carpeta_paciente = Path(paciente["_carpeta"])
    sesiones = []
    for sesion in paciente.get("sesiones", []):
        datos = dict(sesion)
        carpeta_bis = _resolver_ruta(carpeta_paciente, sesion.get("carpeta_bis"))
        ruta_icca = _resolver_ruta(carpeta_paciente, sesion.get("excel_icca_auxiliar"))
        datos["carpeta_bis_absoluta"] = str(carpeta_bis)
        datos["icca_auxiliar_absoluto"] = (
            str(ruta_icca) if ruta_icca is not None else None
        )

        solapamientos = sesion.get("solapamientos") or []
        cobertura = max(
            (float(item.get("cobertura_bis") or 0) for item in solapamientos),
            default=0.0,
        )
        datos["cobertura_icca"] = cobertura
        datos["estado_icca"] = (
            "completa" if any(item.get("completo") for item in solapamientos)
            else "parcial" if cobertura > 0
            else "ausente"
        )
        datos["icca_disponible"] = (
            ruta_icca is not None and ruta_icca.is_file() and cobertura > 0
        )

        try:
            deteccion = _detectar_bis_con_cache(carpeta_bis)
            datos["deteccion_bis"] = deteccion
            datos["alerta_recorte_bis"] = bool(
                ((deteccion.get("validacion") or {}).get("cobertura_temporal") or {}).get(
                    "alerta"
                )
            )
            datos["fa_disponible"] = bool(deteccion.get("fa_disponible"))
            datos["reconstruccion_disponible"] = "raw" in deteccion.get("origenes", [])
        except Exception as exc:
            datos["error_bis"] = str(exc)
            datos["alerta_recorte_bis"] = False
            datos["fa_disponible"] = False
            datos["reconstruccion_disponible"] = False

        if datos["icca_disponible"] and generar_sinteticos:
            try:
                datos["icca_sintetico"] = generar_icca_sintetico(
                    ruta_icca,
                    sesion.get("inicio_bis"),
                    sesion.get("fin_bis"),
                    paciente_id,
                    sesion.get("sesion_bis_id"),
                )
            except Exception as exc:
                datos["error_sintesis_icca"] = str(exc)
        sesiones.append(datos)
    return sesiones
