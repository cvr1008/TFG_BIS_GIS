from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from src.excel_icca import generar_excel_icca_sesion
from src.intervalos import analizar_seleccion


PATRON_PACIENTE = re.compile(r"^PACIENTE_(\d{3,})$")


def _nombre_seguro(texto):
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", texto).strip("_")
    return limpio or "BIS"


def _ruta_normalizada(ruta):
    return str(Path(ruta).expanduser().resolve()).casefold()


def siguiente_paciente(directorio):
    raiz = Path(directorio).expanduser().resolve()
    numeros = []
    if raiz.exists():
        for ruta in raiz.iterdir():
            if not ruta.is_dir():
                continue
            coincidencia = PATRON_PACIENTE.fullmatch(ruta.name)
            if coincidencia:
                numeros.append(int(coincidencia.group(1)))
    return f"PACIENTE_{max(numeros, default=0) + 1:03d}"


def _guardar_json(ruta, datos):
    Path(ruta).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _esta_dentro(ruta, raiz):
    try:
        Path(ruta).resolve().relative_to(Path(raiz).resolve())
        return True
    except ValueError:
        return False


def _eliminar_temporal(ruta, raiz):
    ruta = Path(ruta)
    if ruta.exists() and _esta_dentro(ruta, raiz):
        shutil.rmtree(ruta)


def listar_pacientes(directorio):
    raiz = Path(directorio).expanduser().resolve()
    if not raiz.exists():
        return []
    pacientes = []
    for carpeta in sorted(raiz.iterdir()):
        if not carpeta.is_dir() or not PATRON_PACIENTE.fullmatch(carpeta.name):
            continue
        manifiesto = carpeta / "paciente.json"
        if not manifiesto.is_file():
            continue
        try:
            datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        datos["carpeta"] = str(carpeta)
        pacientes.append(datos)
    return pacientes


def obtener_fuentes_paciente(datos):
    """Devuelve fuentes editables, con compatibilidad para manifiestos antiguos."""
    carpeta = Path(datos["carpeta"]).resolve()
    fuentes = datos.get("fuentes", {})

    rutas_icca = list(fuentes.get("icca", []))
    if not rutas_icca:
        for registro in datos.get("icca", []):
            ruta = registro.get("ruta")
            copia = registro.get("copia")
            if ruta and Path(ruta).is_file():
                rutas_icca.append(ruta)
            elif copia and (carpeta / copia).is_file():
                rutas_icca.append(str(carpeta / copia))

    carpetas_bis = list(fuentes.get("bis", []))
    if not carpetas_bis:
        for sesion in datos.get("sesiones", []):
            origen = sesion.get("origen_bis")
            copia = sesion.get("carpeta_bis")
            if origen and Path(origen).is_dir():
                carpetas_bis.append(origen)
            elif copia and (carpeta / copia).is_dir():
                carpetas_bis.append(str(carpeta / copia))

    return {
        "icca": list(dict.fromkeys(str(Path(ruta).resolve()) for ruta in rutas_icca)),
        "bis": list(dict.fromkeys(str(Path(ruta).resolve()) for ruta in carpetas_bis)),
    }


def _conflictos_fuentes(directorio, analisis, excluir_paciente=None):
    conflictos = {}
    rutas_icca = {_ruta_normalizada(item["ruta"]): item for item in analisis["icca"]}
    rutas_bis = {_ruta_normalizada(item["ruta"]): item for item in analisis["bis"]}
    firmas_bis = {
        (item["sesion_id"], item["inicio"], item["fin"]): item
        for item in analisis["bis"]
    }

    for paciente in listar_pacientes(directorio):
        if paciente["paciente_id"] == excluir_paciente:
            continue
        fuentes = obtener_fuentes_paciente(paciente)
        paciente_id = paciente["paciente_id"]
        for ruta in fuentes["icca"]:
            registro = rutas_icca.get(_ruta_normalizada(ruta))
            if registro:
                conflictos.setdefault(paciente_id, set()).add("icca")
        for ruta in fuentes["bis"]:
            sesion = rutas_bis.get(_ruta_normalizada(ruta))
            if sesion:
                conflictos.setdefault(paciente_id, set()).add("bis")
        for sesion_existente in paciente.get("sesiones", []):
            firma = (
                sesion_existente.get("sesion_bis_id"),
                sesion_existente.get("inicio_bis"),
                sesion_existente.get("fin_bis"),
            )
            sesion = firmas_bis.get(firma)
            if sesion:
                conflictos.setdefault(paciente_id, set()).add("bis")

    return conflictos


def _mensaje_conflictos(conflictos):
    pacientes = sorted(conflictos)
    tipos = set().union(*(conflictos[paciente] for paciente in pacientes))
    if tipos == {"icca", "bis"}:
        seleccion = "Archivo ICCA y sesión BIS"
        asignados = "asignados"
    elif tipos == {"icca"}:
        seleccion = "Archivo ICCA"
        asignados = "asignado"
    else:
        seleccion = "Sesión BIS"
        asignados = "asignada"

    if len(pacientes) == 1:
        return f"{seleccion} ya {asignados} a un paciente ({pacientes[0]})"
    return (
        f"{seleccion} ya {asignados} a otros pacientes "
        f"({', '.join(pacientes)})"
    )


def _validar_bis_no_solapados(analisis):
    sesiones = sorted(
        analisis.get("bis", []),
        key=lambda item: item.get("inicio") or "",
    )
    anterior = None
    for sesion in sesiones:
        if anterior is None:
            anterior = sesion
            continue
        inicio_actual = datetime.fromisoformat(sesion["inicio"])
        fin_anterior = datetime.fromisoformat(anterior["fin"])
        if inicio_actual <= fin_anterior:
            raise ValueError(
                "No se pueden asignar dos sesiones BIS solapadas al mismo "
                "paciente: "
                f"{anterior['sesion_id']} ({anterior['inicio']} - {anterior['fin']}) "
                f"y {sesion['sesion_id']} ({sesion['inicio']} - {sesion['fin']})."
            )
        anterior = sesion


def _analizar_y_validar(directorio, rutas_icca, carpetas_bis, excluir_paciente=None):
    rutas_icca = list(rutas_icca or [])
    carpetas_bis = list(carpetas_bis or [])
    if not carpetas_bis:
        raise ValueError("Selecciona al menos una sesion BIS.")
    analisis = analizar_seleccion(rutas_icca, carpetas_bis)
    _validar_bis_no_solapados(analisis)

    conflictos = _conflictos_fuentes(
        directorio,
        analisis,
        excluir_paciente=excluir_paciente,
    )
    if conflictos:
        raise ValueError(_mensaje_conflictos(conflictos))
    return analisis


def analizar_asignacion(directorio, rutas_icca, carpetas_bis, excluir_paciente=None):
    return _analizar_y_validar(
        directorio,
        rutas_icca,
        carpetas_bis,
        excluir_paciente=excluir_paciente,
    )


def _construir_paciente(
    temporal,
    destino,
    paciente_id,
    analisis,
    creado=None,
):
    originales_icca = temporal / "ICCA_ORIGINALES"
    sesiones_raiz = temporal / "SESIONES"
    originales_icca.mkdir(parents=True)
    sesiones_raiz.mkdir(parents=True)

    registros_icca = []
    for indice, registro in enumerate(analisis["icca"], start=1):
        origen = Path(registro["ruta"])
        copia = originales_icca / f"{indice:02d}_{origen.name}"
        shutil.copy2(origen, copia)
        registro_guardado = dict(registro)
        registro_guardado["copia"] = str(copia.relative_to(temporal))
        registros_icca.append(registro_guardado)

    manifiestos_sesion = []
    sesiones_ordenadas = sorted(analisis["bis"], key=lambda item: item["inicio"])
    for indice, sesion in enumerate(sesiones_ordenadas, start=1):
        nombre_sesion = f"SESION_{indice:03d}_{_nombre_seguro(sesion['sesion_id'])}"
        carpeta_sesion = sesiones_raiz / nombre_sesion
        carpeta_bis = carpeta_sesion / "BIS"
        carpeta_bis.mkdir(parents=True)

        origen_bis = Path(sesion["ruta"])
        copia_bis = carpeta_bis / origen_bis.name
        shutil.copytree(origen_bis, copia_bis)

        fuentes_icca = sesion["icca_compatibles"]
        excel_auxiliar_relativo = None
        if fuentes_icca:
            carpeta_icca = carpeta_sesion / "ICCA"
            carpeta_icca.mkdir(parents=True)
            excel_auxiliar = (
                carpeta_icca / f"ICCA_{_nombre_seguro(sesion['sesion_id'])}.xlsx"
            )
            generar_excel_icca_sesion(
                fuentes_icca,
                sesion,
                excel_auxiliar,
                paciente_id=paciente_id,
                carpeta_paciente=str(destino),
            )
            excel_auxiliar_relativo = str(excel_auxiliar.relative_to(temporal))

        manifiesto_sesion = {
            "nombre_carpeta": nombre_sesion,
            "sesion_bis_id": sesion["sesion_id"],
            "modo": sesion["modo"],
            "inicio_bis": sesion["inicio"],
            "fin_bis": sesion["fin"],
            "origen_bis": str(origen_bis.resolve()),
            "carpeta_bis": str(copia_bis.relative_to(temporal)),
            "excel_icca_auxiliar": excel_auxiliar_relativo,
            "icca_origen": [str(Path(ruta).name) for ruta in fuentes_icca],
            "icca_origen_rutas": [str(Path(ruta).resolve()) for ruta in fuentes_icca],
            "solapamientos": sesion["solapamientos"],
        }
        _guardar_json(carpeta_sesion / "sesion.json", manifiesto_sesion)
        manifiestos_sesion.append(manifiesto_sesion)

    ahora = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    manifiesto = {
        "paciente_id": paciente_id,
        "creado": creado or ahora,
        "actualizado": ahora,
        "carpeta": str(destino),
        "fuentes": {
            "icca": [str(Path(item["ruta"]).resolve()) for item in analisis["icca"]],
            "bis": [str(Path(item["ruta"]).resolve()) for item in analisis["bis"]],
        },
        "icca": registros_icca,
        "sesiones": manifiestos_sesion,
    }
    _guardar_json(temporal / "paciente.json", manifiesto)
    return manifiesto


def crear_paciente(directorio, rutas_icca, carpetas_bis):
    raiz = Path(directorio).expanduser().resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    paciente_id = siguiente_paciente(raiz)
    destino = raiz / paciente_id
    temporal = raiz / f".{paciente_id}.temporal"

    if destino.exists():
        raise FileExistsError(f"Ya existe {destino}.")
    if temporal.exists():
        _eliminar_temporal(temporal, raiz)

    analisis = _analizar_y_validar(raiz, rutas_icca, carpetas_bis)
    try:
        manifiesto = _construir_paciente(
            temporal,
            destino,
            paciente_id,
            analisis,
        )
        temporal.rename(destino)
        _guardar_json(destino / "paciente.json", manifiesto)
        return manifiesto
    except Exception:
        _eliminar_temporal(temporal, raiz)
        raise


def actualizar_paciente(directorio, paciente_id, rutas_icca, carpetas_bis):
    raiz = Path(directorio).expanduser().resolve()
    if not PATRON_PACIENTE.fullmatch(str(paciente_id)):
        raise ValueError("El identificador de paciente no es valido.")

    destino = raiz / paciente_id
    if not destino.is_dir() or not _esta_dentro(destino, raiz):
        raise FileNotFoundError(f"No existe {paciente_id}.")

    anterior = next(
        (item for item in listar_pacientes(raiz) if item["paciente_id"] == paciente_id),
        None,
    )
    if anterior is None:
        raise ValueError(f"No se pudo leer el manifiesto de {paciente_id}.")

    analisis = _analizar_y_validar(
        raiz,
        rutas_icca,
        carpetas_bis,
        excluir_paciente=paciente_id,
    )
    temporal = raiz / f".{paciente_id}.actualizacion"
    respaldo = raiz / f".{paciente_id}.respaldo"
    if temporal.exists():
        _eliminar_temporal(temporal, raiz)
    if respaldo.exists():
        raise RuntimeError(
            f"Existe un respaldo pendiente para {paciente_id}; no se ha modificado nada."
        )

    try:
        manifiesto = _construir_paciente(
            temporal,
            destino,
            paciente_id,
            analisis,
            creado=anterior.get("creado"),
        )
        destino.rename(respaldo)
        try:
            temporal.rename(destino)
        except Exception:
            respaldo.rename(destino)
            raise
        _guardar_json(destino / "paciente.json", manifiesto)
        _eliminar_temporal(respaldo, raiz)
        return manifiesto
    except Exception:
        _eliminar_temporal(temporal, raiz)
        raise


def eliminar_paciente(directorio, paciente_id):
    raiz = Path(directorio).expanduser().resolve()
    if not PATRON_PACIENTE.fullmatch(str(paciente_id)):
        raise ValueError("El identificador de paciente no es valido.")
    destino = (raiz / paciente_id).resolve()
    if not destino.is_dir() or not _esta_dentro(destino, raiz):
        raise FileNotFoundError(f"No existe {paciente_id}.")
    shutil.rmtree(destino)
