from datetime import datetime
from pathlib import Path
import math
import struct

from src.alineacion_temporal import (
    calcular_timeline_comun,
    deduplicar_tiempos,
)

KEY_SPA_VARIABLES = (
    "DB13U01",
    "SQI10",
    "TOTPOW08",
    "SEF08",
    "MEDFRQ08",
    "EMGLOW01",
    "BURST",
)
BILATERAL_EXTRA_SPA_VARIABLES = ("ASYM09",)
EXPECTED_FA_BINS = 60
MAX_FA_ROWS_FOR_NUMERIC_CHECK = 500
TIMESTAMP_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def format_size(size_bytes):
    """
    Ejecuta la lógica asociada a format size.

    Parámetros
    ----------
    size_bytes : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if size_bytes is None:
        return "No disponible"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _file_info(path_text, label):
    """
    Ejecuta la lógica asociada a file info.

    Parámetros
    ----------
    path_text : Any
        Valor de entrada utilizado por la función.

    label : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not path_text:
        return {
            "label": label,
            "name": "No encontrado",
            "path": None,
            "size_bytes": None,
            "size_label": "No disponible",
            "status": "missing",
        }
    path = Path(path_text)
    exists = path.is_file()
    size = path.stat().st_size if exists else None
    return {
        "label": label,
        "name": path.name,
        "path": str(path),
        "size_bytes": size,
        "size_label": format_size(size),
        "status": "empty" if exists and size == 0 else "found" if exists else "missing",
    }


def _pipe_fields(line):
    """
    Ejecuta la lógica asociada a pipe fields.

    Parámetros
    ----------
    line : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    fields = line.rstrip("\r\n").split("|")
    while fields and fields[-1].strip() == "":
        fields.pop()
    return [field.strip() for field in fields]


def _read_lines(path):
    """
    Ejecuta la lógica asociada a read lines.

    Parámetros
    ----------
    path : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    return Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines()


def _parse_time(value):
    """
    Ejecuta la lógica asociada a parse time.

    Parámetros
    ----------
    value : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    text = str(value).strip()
    if not text:
        return None
    for time_format in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, time_format)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _expected_spa_variables(modo=None):
    """
    Ejecuta la lógica asociada a expected spa variables.

    Parámetros
    ----------
    modo : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    variables = list(KEY_SPA_VARIABLES)
    if modo == "bilateral":
        variables.extend(BILATERAL_EXTRA_SPA_VARIABLES)
    return tuple(variables)


def _empty_spa(found, modo=None):
    """
    Ejecuta la lógica asociada a empty spa.

    Parámetros
    ----------
    found : Any
        Valor de entrada utilizado por la función.

    modo : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    expected = _expected_spa_variables(modo)
    return {
        "found": found,
        "non_empty": False,
        "row_count": 0,
        "valid_timestamp_count": 0,
        "unique_timestamp_count": 0,
        "duplicate_timestamp_count": 0,
        "first_timestamp": None,
        "last_timestamp": None,
        "key_variables_found": {key: False for key in expected},
        "warnings": [] if found else [".spa no encontrado."],
    }


def validate_spa_file(path_text, modo=None):
    """
    Valida spa file.

    Parámetros
    ----------
    path_text : Any
        Valor de entrada utilizado por la función.

    modo : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not path_text:
        return _empty_spa(False, modo=modo)

    path = Path(path_text)
    summary = _empty_spa(True, modo=modo)
    if not path.is_file() or path.stat().st_size == 0:
        summary["warnings"].append(".spa vacío o inaccesible.")
        return summary

    summary["non_empty"] = True
    try:
        lines = _read_lines(path)
    except OSError as exc:
        summary["warnings"].append(f"No se pudo leer .spa: {exc}")
        return summary

    if len(lines) < 2:
        summary["warnings"].append(".spa mal formado: faltan cabeceras.")
        return summary

    header = _pipe_fields(lines[1])
    header_set = {column for column in header if column}
    summary["key_variables_found"] = {
        key: key in header_set for key in KEY_SPA_VARIABLES
    }
    missing = [
        key for key, found in summary["key_variables_found"].items() if not found
    ]
    if missing:
        summary["warnings"].append(
            "Variables .spa ausentes: " + ", ".join(missing) + "."
        )

    timestamps = []
    row_count = 0
    for line in lines[2:]:
        if not line.strip():
            continue
        row_count += 1
        fields = _pipe_fields(line)
        if fields:
            parsed = _parse_time(fields[0])
            if parsed is not None:
                timestamps.append(parsed)

    summary["row_count"] = row_count
    summary["valid_timestamp_count"] = len(timestamps)
    if timestamps:
        tiempos_unicos, duplicados = deduplicar_tiempos(timestamps)
        summary["unique_timestamp_count"] = len(tiempos_unicos)
        summary["duplicate_timestamp_count"] = duplicados
        summary["first_timestamp"] = tiempos_unicos.iloc[0].isoformat()
        summary["last_timestamp"] = tiempos_unicos.iloc[-1].isoformat()
    else:
        summary["warnings"].append(".spa sin tiempos válidos.")
    return summary


def _empty_fa(found):
    """
    Ejecuta la lógica asociada a empty fa.

    Parámetros
    ----------
    found : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    return {
        "found": found,
        "non_empty": False,
        "datasets": 0,
        "rows_parsed": 0,
        "valid_timestamp_count": 0,
        "unique_timestamp_count": 0,
        "duplicate_timestamp_count": 0,
        "first_timestamp": None,
        "last_timestamp": None,
        "expected_bins_per_row": EXPECTED_FA_BINS,
        "rows_checked_for_bins": 0,
        "rows_with_expected_bins": 0,
        "finite_ratio": 0.0,
        "zero_empty_row_ratio": 0.0,
        "warnings": [] if found else [".f_a no encontrado."],
    }


def _to_float(value):
    """
    Ejecuta la lógica asociada a to float.

    Parámetros
    ----------
    value : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def validate_fa_file(path_text):
    """
    Valida fa file.

    Parámetros
    ----------
    path_text : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not path_text:
        return _empty_fa(False)

    path = Path(path_text)
    summary = _empty_fa(True)
    if not path.is_file() or path.stat().st_size == 0:
        summary["warnings"].append(".f_a vacío o inaccesible.")
        return summary

    summary["non_empty"] = True
    try:
        lines = _read_lines(path)
    except OSError as exc:
        summary["warnings"].append(f"No se pudo leer .f_a: {exc}")
        return summary

    if len(lines) < 2:
        summary["warnings"].append(".f_a mal formado: faltan cabeceras.")
        return summary

    header = _pipe_fields(lines[1])
    spectra_indexes = [
        index
        for index, column in enumerate(header)
        if "spectra" in column.lower()
    ]
    if not spectra_indexes and len(header) > 1:
        spectra_indexes = [1]
    summary["datasets"] = len(spectra_indexes)
    if not spectra_indexes:
        summary["warnings"].append(".f_a sin columna Spectra.")
        return summary

    timestamps = []
    rows_parsed = 0
    rows_checked_for_bins = 0
    rows_with_expected_bins = 0
    sampled_numeric_count = 0
    sampled_finite_count = 0
    zero_empty_rows = 0

    for line in lines[2:]:
        if not line.strip():
            continue
        fields = _pipe_fields(line)
        if len(fields) <= min(spectra_indexes):
            continue
        rows_parsed += 1
        parsed = _parse_time(fields[0])
        if parsed is not None:
            timestamps.append(parsed)

        row_has_expected_bins = True
        row_has_signal = False
        sample_numeric = rows_parsed <= MAX_FA_ROWS_FOR_NUMERIC_CHECK
        if not sample_numeric:
            continue
        rows_checked_for_bins += 1
        for spectra_index in spectra_indexes:
            if spectra_index >= len(fields):
                row_has_expected_bins = False
                continue
            bins = [value.strip() for value in fields[spectra_index].split(",")]
            if bins and bins[-1] == "":
                bins = bins[:-1]
            if len(bins) != EXPECTED_FA_BINS:
                row_has_expected_bins = False
            for value in bins:
                if value and value not in {"0", "0.0", "0000", "0000.0"}:
                    row_has_signal = True
                if sample_numeric:
                    number = _to_float(value)
                    if number is not None:
                        sampled_numeric_count += 1
                        sampled_finite_count += 1

        if row_has_expected_bins:
            rows_with_expected_bins += 1
        if not row_has_signal:
            zero_empty_rows += 1

    summary["rows_parsed"] = rows_parsed
    summary["valid_timestamp_count"] = len(timestamps)
    summary["rows_checked_for_bins"] = rows_checked_for_bins
    summary["rows_with_expected_bins"] = rows_with_expected_bins
    summary["finite_ratio"] = (
        round(sampled_finite_count / sampled_numeric_count, 6)
        if sampled_numeric_count
        else 0
    )
    summary["zero_empty_row_ratio"] = (
        round(zero_empty_rows / rows_parsed, 6) if rows_parsed else 0
    )
    if timestamps:
        tiempos_unicos, duplicados = deduplicar_tiempos(timestamps)
        summary["unique_timestamp_count"] = len(tiempos_unicos)
        summary["duplicate_timestamp_count"] = duplicados
        summary["first_timestamp"] = tiempos_unicos.iloc[0].isoformat()
        summary["last_timestamp"] = tiempos_unicos.iloc[-1].isoformat()

    if rows_parsed == 0:
        summary["warnings"].append(".f_a sin filas espectrales parseables.")
    if rows_checked_for_bins and rows_with_expected_bins != rows_checked_for_bins:
        summary["warnings"].append(
            f"{rows_checked_for_bins - rows_with_expected_bins} fila(s) "
            f"muestreadas del .f_a sin {EXPECTED_FA_BINS} bins en todos "
            "los datasets."
        )
    if not timestamps:
        summary["warnings"].append(".f_a sin tiempos válidos.")
    return summary


def _alignment(spa, fa):
    """
    Ejecuta la lógica asociada a alignment.

    Parámetros
    ----------
    spa : Any
        Valor de entrada utilizado por la función.

    fa : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    result = {
        "status": "unknown",
        "start_delta_seconds": None,
        "end_delta_seconds": None,
        "overlap_seconds": None,
    }
    if not spa.get("first_timestamp") or not fa.get("first_timestamp"):
        return result
    spa_start = _parse_time(spa["first_timestamp"])
    spa_end = _parse_time(spa["last_timestamp"])
    fa_start = _parse_time(fa["first_timestamp"])
    fa_end = _parse_time(fa["last_timestamp"])
    if None in {spa_start, spa_end, fa_start, fa_end}:
        return result

    start_delta = abs((spa_start - fa_start).total_seconds())
    end_delta = abs((spa_end - fa_end).total_seconds())
    overlap = (min(spa_end, fa_end) - max(spa_start, fa_start)).total_seconds()
    result["start_delta_seconds"] = start_delta
    result["end_delta_seconds"] = end_delta
    result["overlap_seconds"] = max(0, overlap)
    if start_delta <= 2 and end_delta <= 2:
        result["status"] = "aligned"
    elif start_delta <= 60 and end_delta <= 60 and overlap > 0:
        result["status"] = "minor_offset"
    else:
        result["status"] = "mismatch"
    return result


def _leer_tiempos_archivo(path_text):
    """
    Lee tiempos archivo.

    Parámetros
    ----------
    path_text : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not path_text:
        return []
    tiempos = []
    for linea in _read_lines(path_text)[2:]:
        if not linea.strip():
            continue
        campos = _pipe_fields(linea)
        if campos:
            tiempo = _parse_time(campos[0])
            if tiempo is not None:
                tiempos.append(tiempo)
    return tiempos


def _leer_inicio_ta(path_text):
    """
    Lee inicio ta.

    Parámetros
    ----------
    path_text : Any
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
    if not path_text:
        raise ValueError("No se encontró el archivo .t_a.")
    lineas = _read_lines(path_text)
    if not lineas:
        raise ValueError("El archivo .t_a está vacío.")
    inicio = _parse_time(lineas[0])
    if inicio is None:
        raise ValueError("No se pudo interpretar el inicio del .t_a.")
    return inicio


def _leer_parametros_raw(header_path, raw_path):
    """
    Lee parametros raw.

    Parámetros
    ----------
    header_path : Any
        Valor de entrada utilizado por la función.

    raw_path : Any
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
    if not header_path or not raw_path:
        raise ValueError("Faltan la cabecera o la onda cruda.")
    datos = Path(header_path).read_bytes()
    if len(datos) < 190:
        raise ValueError("La cabecera .h_a es demasiado corta.")
    num_canales = struct.unpack_from("<h", datos, 178)[0]
    fs = struct.unpack_from("<i", datos, 186)[0]
    if num_canales <= 0 or fs <= 0:
        raise ValueError("La cabecera contiene parámetros raw no válidos.")
    valores_int16 = Path(raw_path).stat().st_size // 2
    muestras_por_canal = valores_int16 // num_canales
    return fs, muestras_por_canal


def _serializar_cobertura(cobertura):
    """
    Ejecuta la lógica asociada a serializar cobertura.

    Parámetros
    ----------
    cobertura : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    fuentes = {}
    for nombre, datos in cobertura["fuentes"].items():
        tramos_recortados = [
            {
                **tramo,
                "inicio": tramo["inicio"].isoformat(),
                "fin": tramo["fin"].isoformat(),
            }
            for tramo in datos["tramos_recortados"]
        ]
        tramos_huecos = [
            {
                **tramo,
                "inicio": tramo["inicio"].isoformat(),
                "fin": tramo["fin"].isoformat(),
            }
            for tramo in datos["tramos_huecos_internos"]
        ]
        fuentes[nombre] = {
            **datos,
            "inicio": datos["inicio"].isoformat(),
            "fin": datos["fin"].isoformat(),
            "tramos_recortados": tramos_recortados,
            "tramos_huecos_internos": tramos_huecos,
        }
    return {
        "inicio": cobertura["inicio"].isoformat(),
        "fin": cobertura["fin"].isoformat(),
        "segundos": cobertura["segundos"],
        "muestras_residuales_raw": cobertura["muestras_residuales_raw"],
        "fuentes": fuentes,
        "alerta": bool(cobertura["alertas"]),
    }


def _validar_cobertura_temporal(archivos, fa_disponible):
    """
    Valida cobertura temporal.

    Parámetros
    ----------
    archivos : Any
        Valor de entrada utilizado por la función.

    fa_disponible : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    try:
        fs, muestras_raw = _leer_parametros_raw(
            archivos.get("header"),
            archivos.get("raw"),
        )
        cobertura = calcular_timeline_comun(
            inicio_raw=_leer_inicio_ta(archivos.get("ta")),
            numero_muestras_raw=muestras_raw,
            fs=fs,
            tiempos_spa=_leer_tiempos_archivo(archivos.get("spa")),
            tiempos_fa=(
                _leer_tiempos_archivo(archivos.get("fa"))
                if fa_disponible
                else None
            ),
        )
    except (OSError, ValueError, struct.error) as exc:
        return None, [f"No se pudo calcular la timeline común: {exc}"]

    avisos = []
    for datos in cobertura["alertas"]:
        porcentaje = datos["proporcion_eliminada"] * 100
        if datos["forma_recorte"] == "bloque_continuo":
            tramo = datos["tramos_recortados"][0]
            forma = (
                f"un único bloque continuo al {tramo['posicion']} "
                f"de {tramo['segundos']} s"
            )
        elif datos["forma_recorte"] == "dos_bloques_extremos":
            forma = (
                "dos bloques continuos, uno al inicio y otro al final "
                f"({datos['segundos_eliminados']} s en total)"
            )
        else:
            forma = "sin bloques de recorte"
        avisos.append(
            "ALERTA temporal: para crear el intervalo común se elimina "
            f"el {porcentaje:.1f}% de la duración de {datos['nombre']}: "
            f"{forma}. "
            "El registro puede estar mal recogido, artefactado o pertenecer "
            "a intervalos incompatibles."
        )
    for nombre, datos in cobertura["fuentes"].items():
        if datos["discontinuidad_interna"]:
            avisos.append(
                f"Discontinuidad interna en {nombre}: faltan "
                f"{datos['segundos_huecos_internos']} s repartidos en "
                f"{datos['numero_tramos_huecos_internos']} tramo(s) dentro "
                "del intervalo común. No es un recorte de extremos; el "
                "primer segundo presente tras cada hueco se conserva si "
                "supera los demás criterios de calidad."
            )
    return _serializar_cobertura(cobertura), avisos


def validar_exportacion_bis(archivos, modo=None):
    """Devuelve un resumen serializable de archivos y checks previos."""
    labels = {
        "raw": "Onda cruda",
        "spa": "Variables .spa",
        "fa": "DSA .f_a",
        "header": "Cabecera .h_a",
        "ta": "Inicio .t_a",
    }
    file_rows = [
        {"key": key, **_file_info(archivos.get(key), label)}
        for key, label in labels.items()
    ]
    spa = validate_spa_file(archivos.get("spa"), modo=modo)
    fa = validate_fa_file(archivos.get("fa"))
    warnings = [*spa["warnings"]]
    if fa["found"]:
        warnings.extend(fa["warnings"])
    alignment = _alignment(spa, fa) if fa.get("non_empty") else None
    if alignment and alignment["status"] == "mismatch":
        warnings.append(".spa y .f_a no parecen compartir el mismo intervalo.")
    cobertura_temporal, avisos_cobertura = _validar_cobertura_temporal(
        archivos,
        fa_disponible=bool(fa.get("non_empty")),
    )
    warnings.extend(avisos_cobertura)

    return {
        "files": file_rows,
        "spa": spa,
        "fa": fa,
        "alignment": alignment,
        "cobertura_temporal": cobertura_temporal,
        "warnings": warnings,
    }
