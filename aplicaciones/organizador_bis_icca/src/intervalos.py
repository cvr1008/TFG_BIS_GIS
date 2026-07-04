from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.libros import abrir_libro


FORMATOS_FECHA = (
    "%m/%d/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)


def _parsear_fecha(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.replace(microsecond=0)

    texto = str(valor).strip()
    if not texto:
        return None
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto).replace(microsecond=0)
    except ValueError:
        return None


def _iso(valor):
    return valor.isoformat(sep=" ") if valor is not None else None


def _duracion_segundos(inicio, fin):
    return max(0, int((fin - inicio).total_seconds()))


def _buscar_archivo_spa(carpeta):
    candidatos = [
        ruta
        for ruta in Path(carpeta).rglob("*.spa")
        if ruta.is_file()
        and "__MACOSX" not in ruta.parts
        and not ruta.name.startswith("._")
    ]
    if not candidatos:
        raise ValueError("La carpeta no contiene ningun archivo .spa.")
    if len(candidatos) > 1:
        nombres = ", ".join(ruta.name for ruta in candidatos[:5])
        raise ValueError(
            "La carpeta contiene varias sesiones BIS "
            f"({nombres}). Selecciona una carpeta por sesion."
        )
    return candidatos[0]


def descubrir_sesiones_bis_en_carpeta(carpeta):
    """Localiza carpetas de sesión BIS dentro de una carpeta madre."""
    raiz = Path(carpeta).expanduser().resolve()
    if not raiz.is_dir():
        raise ValueError("La ruta BIS no es una carpeta valida.")

    carpetas = []
    vistas = set()
    for spa in sorted(raiz.rglob("*.spa")):
        if (
            not spa.is_file()
            or "__MACOSX" in spa.parts
            or spa.name.startswith("._")
        ):
            continue
        carpeta_sesion = spa.parent.resolve()
        clave = str(carpeta_sesion).casefold()
        if clave in vistas:
            continue
        vistas.add(clave)
        try:
            leer_intervalo_bis(carpeta_sesion)
        except ValueError:
            continue
        carpetas.append(str(carpeta_sesion))
    return carpetas


def leer_intervalo_bis(carpeta):
    carpeta = Path(carpeta).expanduser().resolve()
    if not carpeta.is_dir():
        raise ValueError("La ruta BIS no es una carpeta valida.")

    spa = _buscar_archivo_spa(carpeta)
    inicio = None
    fin = None
    filas = 0
    tiempos = set()

    with spa.open("r", encoding="latin1", errors="ignore") as archivo:
        primera = archivo.readline()
        cabecera = archivo.readline()
        if not primera or not cabecera:
            raise ValueError(f"{spa.name} no contiene cabecera suficiente.")

        nombres = [campo.strip() for campo in cabecera.rstrip("\r\n").split("|")]
        try:
            indice_time = nombres.index("Time")
        except ValueError as exc:
            raise ValueError(f"{spa.name} no contiene la columna Time.") from exc

        for linea in archivo:
            campos = linea.rstrip("\r\n").split("|")
            if indice_time >= len(campos):
                continue
            instante = _parsear_fecha(campos[indice_time])
            if instante is None:
                continue
            filas += 1
            tiempos.add(instante)
            inicio = instante if inicio is None or instante < inicio else inicio
            fin = instante if fin is None or instante > fin else fin

    if inicio is None or fin is None:
        raise ValueError(f"No se encontraron timestamps validos en {spa.name}.")

    archivos = [ruta for ruta in carpeta.rglob("*") if ruta.is_file()]
    raw = next(
        (ruta for ruta in archivos if ruta.suffix.lower() in {".r2a", ".r4a"}),
        None,
    )
    modo = {
        ".r2a": "unilateral",
        ".r4a": "bilateral",
    }.get(raw.suffix.lower() if raw else "", "no determinado")

    return {
        "tipo": "BIS",
        "ruta": str(carpeta),
        "nombre": carpeta.name,
        "sesion_id": spa.stem,
        "spa": str(spa),
        "modo": modo,
        "inicio": _iso(inicio),
        "fin": _iso(fin),
        "duracion_s": _duracion_segundos(inicio, fin),
        "filas_spa": filas,
        "timestamps_unicos": len(tiempos),
        "duplicados_spa": filas - len(tiempos),
        "numero_archivos": len(archivos),
        "bytes": sum(ruta.stat().st_size for ruta in archivos),
    }


def _buscar_hoja(libro, nombre):
    objetivo = nombre.casefold()
    for hoja in libro.worksheets:
        if hoja.title.casefold() == objetivo:
            return hoja
    return None


def _intervalo_desde_general(libro):
    hoja = _buscar_hoja(libro, "general")
    if hoja is None:
        return None, None

    cabeceras = {
        str(celda.value).strip(): celda.column
        for celda in hoja[3]
        if celda.value is not None
    }
    columna_inicio = cabeceras.get("fecha_hora_ingreso")
    columna_fin = cabeceras.get("fecha_hora_alta")
    if not columna_inicio or not columna_fin:
        return None, None
    return (
        _parsear_fecha(hoja.cell(4, columna_inicio).value),
        _parsear_fecha(hoja.cell(4, columna_fin).value),
    )


def _intervalo_desde_observaciones(libro):
    inicio = None
    fin = None
    for nombre in ("constantes_vitales", "analisis", "perfusiones"):
        hoja = _buscar_hoja(libro, nombre)
        if hoja is None:
            continue
        cabeceras = {
            str(celda.value).strip(): celda.column
            for celda in hoja[3]
            if celda.value is not None
        }
        columna = cabeceras.get("timestamp")
        if not columna:
            continue
        indice = columna - 1
        for valores in hoja.iter_rows(min_row=4, values_only=True):
            if indice >= len(valores):
                continue
            instante = _parsear_fecha(valores[indice])
            if instante is None:
                continue
            inicio = instante if inicio is None or instante < inicio else inicio
            fin = instante if fin is None or instante > fin else fin
    return inicio, fin


def leer_intervalo_icca(ruta_excel):
    ruta = Path(ruta_excel).expanduser().resolve()
    if not ruta.is_file() or ruta.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("La ruta ICCA debe ser un archivo Excel .xlsx o .xlsm.")

    with abrir_libro(ruta, read_only=True, data_only=True) as libro:
        ingreso, alta = _intervalo_desde_general(libro)
        obs_inicio, obs_fin = _intervalo_desde_observaciones(libro)
        inicio = ingreso or obs_inicio
        fin = alta or obs_fin
        if inicio is None or fin is None:
            raise ValueError(
                "No se encontro un intervalo ICCA en general ni en las hojas temporales."
            )
        return {
            "tipo": "ICCA",
            "ruta": str(ruta),
            "nombre": ruta.name,
            "inicio": _iso(inicio),
            "fin": _iso(fin),
            "duracion_s": _duracion_segundos(inicio, fin),
            "observaciones_inicio": _iso(obs_inicio),
            "observaciones_fin": _iso(obs_fin),
            "hojas": libro.sheetnames,
            "bytes": ruta.stat().st_size,
        }


def descubrir_icca_en_carpeta(carpeta):
    """Localiza plantillas ICCA Excel utilizables dentro de una carpeta madre."""
    raiz = Path(carpeta).expanduser().resolve()
    if not raiz.is_dir():
        raise ValueError("La ruta ICCA no es una carpeta valida.")

    rutas = []
    for ruta in sorted(raiz.rglob("*")):
        if (
            not ruta.is_file()
            or ruta.name.startswith("~$")
            or ruta.name.startswith("._")
            or ruta.suffix.lower() not in {".xlsx", ".xlsm"}
        ):
            continue
        try:
            leer_intervalo_icca(ruta)
        except ValueError:
            continue
        rutas.append(str(ruta.resolve()))
    return rutas


def calcular_solapamiento(intervalo_bis, intervalo_icca):
    bis_inicio = _parsear_fecha(intervalo_bis["inicio"])
    bis_fin = _parsear_fecha(intervalo_bis["fin"])
    icca_inicio = _parsear_fecha(intervalo_icca["inicio"])
    icca_fin = _parsear_fecha(intervalo_icca["fin"])

    inicio = max(bis_inicio, icca_inicio)
    fin = min(bis_fin, icca_fin)
    segundos = max(0, int((fin - inicio).total_seconds()))
    duracion_bis = max(1, int((bis_fin - bis_inicio).total_seconds()))
    cobertura = min(1.0, segundos / duracion_bis)
    return {
        "inicio": _iso(inicio) if segundos > 0 else None,
        "fin": _iso(fin) if segundos > 0 else None,
        "segundos": segundos,
        "cobertura_bis": cobertura,
        "completo": icca_inicio <= bis_inicio and icca_fin >= bis_fin,
    }


def analizar_seleccion(rutas_icca, carpetas_bis):
    icca = [leer_intervalo_icca(ruta) for ruta in rutas_icca]
    bis = [leer_intervalo_bis(ruta) for ruta in carpetas_bis]
    for sesion in bis:
        sesion["solapamientos"] = [
            {
                "icca": registro["ruta"],
                **calcular_solapamiento(sesion, registro),
            }
            for registro in icca
        ]
        sesion["icca_compatibles"] = [
            item["icca"]
            for item in sesion["solapamientos"]
            if item["segundos"] > 0
        ]
    return {"icca": icca, "bis": bis}
