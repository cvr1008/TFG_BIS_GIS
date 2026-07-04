import numpy as np
import pandas as pd


MAX_INSTANTES_SIN_REDUCCION = 7200


def crear_opciones_tramos_horarios(tiempo):
    """Divide un registro en tramos ajustados a las horas naturales."""
    tiempo = pd.to_datetime(pd.Series(tiempo), errors="coerce").dropna()
    if tiempo.empty:
        raise ValueError("El registro no contiene tiempos válidos.")

    inicio_registro = tiempo.iloc[0]
    fin_registro = tiempo.iloc[-1]
    cursor = inicio_registro.floor("h")
    opciones = []

    while cursor <= fin_registro:
        inicio = max(inicio_registro, cursor)
        fin = min(fin_registro, cursor + pd.Timedelta(hours=1))
        if inicio <= fin:
            opciones.append(
                {
                    "label": (
                        f"{inicio.strftime('%d/%m %H:%M')} - "
                        f"{fin.strftime('%d/%m %H:%M')}"
                    ),
                    "value": f"{inicio.isoformat()}|{fin.isoformat()}",
                }
            )
        cursor += pd.Timedelta(hours=1)

    return opciones


def _interpretar_tramo(valor_tramo):
    try:
        inicio_texto, fin_texto = valor_tramo.split("|", 1)
        inicio = pd.Timestamp(inicio_texto)
        fin = pd.Timestamp(fin_texto)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("El tramo temporal seleccionado no es válido.") from exc

    if inicio > fin:
        raise ValueError("El inicio del tramo es posterior a su final.")
    return inicio, fin


def _recortar_registro(registro, inicio, fin):
    tiempo = pd.to_datetime(pd.Series(registro["tiempo"]), errors="coerce")
    indices = np.flatnonzero((tiempo >= inicio) & (tiempo <= fin))
    if indices.size == 0:
        raise ValueError("No hay datos dentro del tramo temporal seleccionado.")

    vista = {
        "modo": registro["modo"],
        "frecuencias": registro["frecuencias"],
        "tiempo": tiempo.iloc[indices].reset_index(drop=True),
    }
    numero_instantes = len(tiempo)

    for nombre, valores in registro.items():
        if nombre in {"modo", "frecuencias", "tiempo"}:
            continue
        array = np.asarray(valores)
        if array.ndim >= 1 and len(array) == numero_instantes:
            vista[nombre] = array[indices]
        else:
            vista[nombre] = valores

    return vista


def preparar_registro_completo(registro):
    """Devuelve el registro completo sin reducir ni promediar instantes."""
    tiempo = pd.to_datetime(pd.Series(registro["tiempo"]), errors="coerce")
    vista = dict(registro)
    vista["tiempo"] = tiempo.reset_index(drop=True)
    vista["vista_estatica"] = len(tiempo) > MAX_INSTANTES_SIN_REDUCCION
    return vista


def preparar_vista_temporal(registro, valor_tramo, duracion):
    tiempo = pd.to_datetime(pd.Series(registro["tiempo"]), errors="coerce")
    inicio_registro = tiempo.iloc[0]
    fin_registro = tiempo.iloc[-1]

    if duracion == "todo":
        return (
            preparar_registro_completo(registro),
            inicio_registro,
            fin_registro,
            True,
        )

    inicio, fin_tramo = _interpretar_tramo(valor_tramo)
    ampliaciones = {
        "1h": pd.Timedelta(0),
        "2h": pd.Timedelta(hours=1),
        "4h": pd.Timedelta(hours=3),
    }
    if duracion not in ampliaciones:
        raise ValueError("La duración de la vista no es válida.")

    inicio = max(inicio, inicio_registro)
    fin = min(fin_tramo + ampliaciones[duracion], fin_registro)
    vista = _recortar_registro(registro, inicio, fin)
    vista["vista_estatica"] = duracion == "4h"
    return vista, inicio, fin, False
