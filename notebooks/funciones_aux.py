
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates



def localizar_archivos(ruta_raiz, carpeta, extension):
    """
    Busca archivos .f_a dentro de subcarpetas cuyo nombre empiece por DH.
    """
    patron = os.path.join(ruta_raiz, "**", carpeta, extension)
    archivos = glob.glob(patron, recursive=True)
    print(f"Se han encontrado {len(archivos)} archivos {extension}")
    
    return archivos


def vista_preeliminar_texto(ruta, n_lineas=5):

    """
    ver el contenido de los archivos en modo texto para verificar legibilidad
    imprime primero el nombre del archivo para ver qué estamos viendo
    si algún archivo da error al abrirse no se abre 
    te abre cada archivo en modo lectura y lo guarda en variable f
        para cada archivo te lee las 5 primeras líneas y te quita los 
        espacios y saltos de línea al principio y al final

    cuando acaba cierra el archivo
    """

    print(f"\n--- {ruta} ---")
    try:
        with open(ruta, "r", errors="ignore") as f:
            for i in range(n_lineas):
                print(f.readline().strip())
    
    except Exception as e:
        print(f"Error: {e}")



def buscar_lineas_por_intervalo(ruta, inicio, fin, formato="%m/%d/%Y %H:%M:%S", max_resultados=300):
    """
    Busca líneas cuyo timestamp esté entre dos fechas/horas.

    Parámetros:
    - ruta: ruta del archivo
    - inicio: string con fecha-hora inicial
    - fin: string con fecha-hora final
    - formato: formato de fecha
    """
    print(f"\n--- Buscando entre {inicio} y {fin} en {ruta} ---")

    try:
        dt_inicio = datetime.strptime(inicio, formato)
        dt_fin = datetime.strptime(fin, formato)

        encontrados = 0

        with open(ruta, "r", errors="ignore") as f:
            for num_linea, linea in enumerate(f, start=1):
                linea_limpia = linea.strip()

                # Intentamos extraer los primeros 19 caracteres como timestamp
                posible_fecha = linea_limpia[:19]

                try:
                    dt_linea = datetime.strptime(posible_fecha, formato)

                    if dt_inicio <= dt_linea <= dt_fin:
                        print(f"Línea {num_linea}: {linea_limpia}")
                        encontrados += 1

                        if encontrados >= max_resultados:
                            break

                except ValueError:
                    # Si la línea no empieza por fecha válida, la ignoramos
                    continue

        if encontrados == 0:
            print("No se encontraron líneas en ese intervalo.")

    except Exception as e:
        print(f"Error: {e}")

