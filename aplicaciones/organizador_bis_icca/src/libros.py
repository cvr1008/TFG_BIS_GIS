from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

from openpyxl import load_workbook


@contextmanager
def abrir_libro(ruta, **opciones):
    """Abre un Excel y usa una copia temporal si el original esta bloqueado."""
    ruta = Path(ruta).expanduser().resolve()
    temporal = None
    try:
        try:
            libro = load_workbook(ruta, **opciones)
        except PermissionError:
            temporal = TemporaryDirectory(prefix="icca_excel_")
            copia = Path(temporal.name) / ruta.name
            copy2(ruta, copia)
            libro = load_workbook(copia, **opciones)

        try:
            yield libro
        finally:
            libro.close()
    finally:
        if temporal is not None:
            temporal.cleanup()
