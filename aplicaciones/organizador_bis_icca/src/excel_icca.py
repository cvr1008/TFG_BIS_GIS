from __future__ import annotations

from copy import copy
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.intervalos import _parsear_fecha
from src.libros import abrir_libro


HOJAS_TEMPORALES = ("constantes_vitales", "analisis", "perfusiones")
COLUMNAS_PERFUSION_CALCULADAS = (
    "volumen_acumulado_calculado_ml",
    "dia_clinico_inicio",
    "acumulado_calculado_origen",
)


def _buscar_hoja(libro, nombre):
    objetivo = nombre.casefold()
    for hoja in libro.worksheets:
        if hoja.title.casefold() == objetivo:
            return hoja
    return None


def _cabeceras(hoja):
    return [
        str(celda.value).strip() if celda.value is not None else ""
        for celda in hoja[3]
    ]


def _asegurar_columna(hoja, nombre):
    cabeceras = _cabeceras(hoja)
    if nombre in cabeceras:
        return

    columna = len(cabeceras) + 1
    hoja.cell(3, columna, nombre)
    if columna > 1:
        origen = hoja.cell(3, columna - 1)
        destino = hoja.cell(3, columna)
        destino._style = copy(origen._style)
        destino.number_format = origen.number_format
        destino.alignment = copy(origen.alignment)
        destino.font = copy(origen.font)
        destino.fill = copy(origen.fill)


def _asegurar_columnas_perfusiones(hoja):
    for nombre in COLUMNAS_PERFUSION_CALCULADAS:
        _asegurar_columna(hoja, nombre)


def _clave_fila(valores):
    clave = []
    for valor in valores:
        if isinstance(valor, datetime):
            clave.append(valor.replace(microsecond=0).isoformat())
        else:
            clave.append(str(valor) if valor is not None else "")
    return tuple(clave)


def _numero(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _inicio_dia_clinico(instante):
    inicio = instante.replace(hour=8, minute=0, second=0, microsecond=0)
    if instante < inicio:
        inicio -= timedelta(days=1)
    return inicio


def _integrar_hasta(inicio, fin, velocidad_ml_h, acumulado, dia_clinico):
    velocidad = float(velocidad_ml_h or 0.0)
    actual = inicio
    while actual < fin:
        siguiente_reset = dia_clinico + timedelta(days=1)
        tramo_fin = min(fin, siguiente_reset)
        acumulado += velocidad * max(0.0, (tramo_fin - actual).total_seconds()) / 3600.0
        actual = tramo_fin
        if actual == siguiente_reset and actual < fin:
            dia_clinico = siguiente_reset
            acumulado = 0.0
    return acumulado, dia_clinico


def _anadir_acumulados_perfusiones(filas, cabeceras):
    indices = {nombre: indice for indice, nombre in enumerate(cabeceras)}
    necesarios = {"timestamp", "farmaco", *COLUMNAS_PERFUSION_CALCULADAS}
    if not necesarios.issubset(indices):
        return filas

    salida = [list(fila) for fila in filas]
    grupos = {}
    for indice, fila in enumerate(salida):
        instante = _parsear_fecha(fila[indices["timestamp"]])
        farmaco = str(fila[indices["farmaco"]] or "").strip()
        if instante is None or not farmaco:
            continue
        grupos.setdefault(farmaco.casefold(), []).append((indice, instante))

    indice_velocidad = indices.get("velocidad_bomba_ml_h")
    indice_acumulado_real = indices.get("volumen_acumulado_24h_ml")
    indice_calculado = indices["volumen_acumulado_calculado_ml"]
    indice_dia = indices["dia_clinico_inicio"]
    indice_origen = indices["acumulado_calculado_origen"]

    for grupo in grupos.values():
        grupo.sort(key=lambda item: (item[1], item[0]))
        acumulado = 0.0
        dia_clinico = None
        instante_previo = None
        velocidad_previa = 0.0

        for indice, instante in grupo:
            fila = salida[indice]
            dia_actual = _inicio_dia_clinico(instante)
            if dia_clinico is None:
                acumulado = 0.0
                dia_clinico = dia_actual
                instante_previo = dia_actual
                velocidad_previa = 0.0

            if instante_previo is not None and instante > instante_previo:
                acumulado, dia_clinico = _integrar_hasta(
                    instante_previo,
                    instante,
                    velocidad_previa,
                    acumulado,
                    dia_clinico,
                )

            acumulado_real = (
                _numero(fila[indice_acumulado_real])
                if indice_acumulado_real is not None
                else None
            )
            if acumulado_real is not None:
                acumulado = acumulado_real
                origen = "ICCA acumulado 24h"
            elif velocidad_previa:
                origen = "integrado desde mL/h"
            else:
                origen = "sin volumen previo; acumulado calculado desde 0"

            fila[indice_calculado] = round(acumulado, 4)
            fila[indice_dia] = dia_clinico
            fila[indice_origen] = origen

            velocidad_actual = (
                _numero(fila[indice_velocidad])
                if indice_velocidad is not None
                else None
            )
            if velocidad_actual is not None:
                velocidad_previa = velocidad_actual
            instante_previo = instante

    return salida


def _recoger_filas(rutas, nombre_hoja, cabeceras_destino, inicio, fin, paciente_id, sesion_id):
    filas = []
    vistos = set()
    for ruta in rutas:
        with abrir_libro(ruta, read_only=True, data_only=False) as libro:
            hoja = _buscar_hoja(libro, nombre_hoja)
            if hoja is None:
                continue
            cabeceras_origen = _cabeceras(hoja)
            indices = {
                nombre: indice
                for indice, nombre in enumerate(cabeceras_origen)
                if nombre
            }
            if "timestamp" not in indices:
                continue

            for valores_origen in hoja.iter_rows(min_row=4, values_only=True):
                instante = _parsear_fecha(valores_origen[indices["timestamp"]])
                if instante is None or instante < inicio or instante > fin:
                    continue

                valores = []
                for nombre in cabeceras_destino:
                    if nombre == "paciente_id":
                        valor = paciente_id
                    elif nombre == "sesion_bis_id":
                        valor = sesion_id
                    elif nombre in indices and indices[nombre] < len(valores_origen):
                        valor = valores_origen[indices[nombre]]
                    else:
                        valor = None
                    valores.append(valor)

                clave = _clave_fila(valores)
                if clave not in vistos:
                    vistos.add(clave)
                    filas.append(valores)

    indice_timestamp = cabeceras_destino.index("timestamp")
    filas.sort(key=lambda fila: _parsear_fecha(fila[indice_timestamp]) or datetime.max)
    return filas


def _capturar_estilo_fila(hoja, fila, numero_columnas):
    return [
        {
            "style": copy(hoja.cell(fila, columna)._style),
            "number_format": hoja.cell(fila, columna).number_format,
            "alignment": copy(hoja.cell(fila, columna).alignment),
        }
        for columna in range(1, numero_columnas + 1)
    ]


def _reemplazar_datos(hoja, filas):
    cabeceras = _cabeceras(hoja)
    numero_columnas = len(cabeceras)
    estilo = _capturar_estilo_fila(hoja, 4, numero_columnas)

    if hoja.max_row >= 4:
        hoja.delete_rows(4, hoja.max_row - 3)

    filas_escritas = filas if filas else [[None] * numero_columnas]
    for indice_fila, valores in enumerate(filas_escritas, start=4):
        for indice_columna, valor in enumerate(valores, start=1):
            celda = hoja.cell(indice_fila, indice_columna, valor)
            plantilla = estilo[indice_columna - 1]
            celda._style = copy(plantilla["style"])
            celda.number_format = plantilla["number_format"]
            celda.alignment = copy(plantilla["alignment"])

    ultima_fila = 3 + len(filas_escritas)
    ultima_columna = get_column_letter(numero_columnas)
    for tabla in hoja.tables.values():
        tabla.ref = f"A3:{ultima_columna}{ultima_fila}"


def _actualizar_general(libro, paciente_id, carpeta_paciente, sesion_id):
    hoja = _buscar_hoja(libro, "general")
    if hoja is None:
        return
    cabeceras = {
        str(celda.value).strip(): celda.column
        for celda in hoja[3]
        if celda.value is not None
    }
    valores = {
        "paciente_id": paciente_id,
        "carpeta_paciente": carpeta_paciente,
        "sesion_bis_id": sesion_id,
    }
    for nombre, valor in valores.items():
        if nombre in cabeceras:
            hoja.cell(4, cabeceras[nombre], valor)


def _crear_metadata(libro, paciente_id, sesion, rutas_icca):
    if "metadata_sesion" in libro.sheetnames:
        del libro["metadata_sesion"]
    hoja = libro.create_sheet("metadata_sesion", 1)
    hoja.append(["Campo", "Valor"])
    hoja.append(["Paciente", paciente_id])
    hoja.append(["Sesion BIS", sesion["sesion_id"]])
    hoja.append(["Inicio BIS", _parsear_fecha(sesion["inicio"])])
    hoja.append(["Fin BIS", _parsear_fecha(sesion["fin"])])
    hoja.append(["Modo BIS", sesion.get("modo", "")])
    hoja.append(["Excel ICCA origen", "; ".join(str(Path(ruta).name) for ruta in rutas_icca)])
    hoja.append(["Generado", datetime.now().replace(microsecond=0)])

    hoja["A1"].font = Font(bold=True, color="FFFFFF")
    hoja["B1"].font = Font(bold=True, color="FFFFFF")
    hoja["A1"].fill = PatternFill("solid", fgColor="1F4E78")
    hoja["B1"].fill = PatternFill("solid", fgColor="1F4E78")
    hoja.column_dimensions["A"].width = 24
    hoja.column_dimensions["B"].width = 70
    hoja.freeze_panes = "A2"
    for fila in (4, 5, 8):
        hoja.cell(fila, 2).number_format = "dd/mm/yyyy hh:mm:ss"


def generar_excel_icca_sesion(
    rutas_icca,
    sesion,
    salida,
    paciente_id,
    carpeta_paciente,
):
    if not rutas_icca:
        raise ValueError("No hay archivos ICCA compatibles con la sesion BIS.")

    inicio = _parsear_fecha(sesion["inicio"])
    fin = _parsear_fecha(sesion["fin"])
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)

    with abrir_libro(rutas_icca[0]) as libro:
        _actualizar_general(
            libro,
            paciente_id=paciente_id,
            carpeta_paciente=carpeta_paciente,
            sesion_id=sesion["sesion_id"],
        )
        for nombre in HOJAS_TEMPORALES:
            hoja = _buscar_hoja(libro, nombre)
            if hoja is None:
                continue
            if nombre == "perfusiones":
                _asegurar_columnas_perfusiones(hoja)
            cabeceras = _cabeceras(hoja)
            filas = _recoger_filas(
                rutas_icca,
                nombre,
                cabeceras,
                inicio,
                fin,
                paciente_id,
                sesion["sesion_id"],
            )
            if nombre == "perfusiones":
                filas = _anadir_acumulados_perfusiones(filas, cabeceras)
            _reemplazar_datos(hoja, filas)

        _crear_metadata(libro, paciente_id, sesion, rutas_icca)
        libro.save(salida)
    return salida
