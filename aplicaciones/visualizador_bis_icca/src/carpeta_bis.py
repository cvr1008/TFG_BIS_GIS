from pathlib import Path

from src.validacion_bis import validar_exportacion_bis


EXTENSIONES_NECESARIAS = {
    "fa": ".f_a",
    "header": ".h_a",
    "ta": ".t_a",
    "spa": ".spa",
}
EXTENSIONES_RAW = {".r2a": "unilateral", ".r4a": "bilateral"}


def _archivo_util(ruta):
    """
    Ejecuta la lógica asociada a archivo util.

    Parámetros
    ----------
    ruta : Any
        Ruta del archivo o carpeta que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    return (
        ruta.is_file()
        and not ruta.name.startswith("._")
        and "__MACOSX" not in ruta.parts
    )


def _buscar_companero(archivos, raw, extension):
    """
    Busca companero.

    Parámetros
    ----------
    archivos : Any
        Valor de entrada utilizado por la función.

    raw : Any
        Valor de entrada utilizado por la función.

    extension : Any
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
    candidatos = [
        archivo
        for archivo in archivos
        if archivo.suffix.lower() == extension
        and archivo.stem.casefold() == raw.stem.casefold()
    ]
    misma_carpeta = [
        archivo for archivo in candidatos if archivo.parent == raw.parent
    ]
    if len(misma_carpeta) == 1:
        return misma_carpeta[0]
    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1:
        raise ValueError(
            f"Hay varios archivos {raw.stem}{extension}. "
            "Selecciona una carpeta que contenga una sola exportación BIS."
        )
    return None


def detectar_exportacion_bis(ruta_carpeta):
    """Localiza y clasifica una exportación BIS dentro de una carpeta."""
    carpeta = Path(ruta_carpeta).expanduser()
    if not carpeta.exists() or not carpeta.is_dir():
        raise ValueError("La ruta seleccionada no es una carpeta válida.")

    carpeta = carpeta.resolve()
    archivos = [ruta for ruta in carpeta.rglob("*") if _archivo_util(ruta)]
    raw_encontrados = [
        ruta
        for ruta in archivos
        if ruta.suffix.lower() in EXTENSIONES_RAW
    ]

    if not raw_encontrados:
        raise ValueError(
            "No se encontró ningún archivo de onda cruda .r2a o .r4a. "
            "No es posible determinar si el registro es unilateral o bilateral."
        )
    if len(raw_encontrados) > 1:
        nombres = ", ".join(ruta.name for ruta in raw_encontrados[:4])
        raise ValueError(
            "La carpeta contiene más de una exportación BIS "
            f"({nombres}). Selecciona la carpeta de un único registro."
        )

    raw = raw_encontrados[0]
    modo = EXTENSIONES_RAW[raw.suffix.lower()]
    encontrados = {"raw": raw}
    for clave, extension in EXTENSIONES_NECESARIAS.items():
        encontrados[clave] = _buscar_companero(archivos, raw, extension)

    if encontrados["spa"] is None:
        raise ValueError(f"No se encontró {raw.stem}.spa.")

    fa = encontrados["fa"]
    fa_disponible = fa is not None and fa.stat().st_size > 0
    raw_completo = all(
        encontrados[clave] is not None
        for clave in ["header", "ta", "raw", "spa"]
    )

    if not fa_disponible and not raw_completo:
        faltantes = [
            EXTENSIONES_NECESARIAS[clave]
            for clave in ["header", "ta"]
            if encontrados[clave] is None
        ]
        raise ValueError(
            "El .f_a no existe o está vacío y no puede reconstruirse la DSA. "
            f"Faltan: {', '.join(faltantes)}."
        )

    if fa_disponible and raw_completo:
        origenes = ["fa", "raw"]
        origen_forzado = None
    elif fa_disponible:
        origenes = ["fa"]
        origen_forzado = "fa"
    else:
        origenes = ["raw"]
        origen_forzado = "raw"

    return {
        "carpeta": str(carpeta),
        "carpeta_datos": str(raw.parent),
        "base": raw.stem,
        "modo": modo,
        "archivos": {
            clave: str(ruta) if ruta is not None else None
            for clave, ruta in encontrados.items()
        },
        "fa_disponible": fa_disponible,
        "fa_bytes": fa.stat().st_size if fa is not None else 0,
        "raw_completo": raw_completo,
        "origenes": origenes,
        "origen_forzado": origen_forzado,
        "validacion": validar_exportacion_bis(
            {
                clave: str(ruta) if ruta is not None else None
                for clave, ruta in encontrados.items()
            },
            modo=modo,
        ),
    }
