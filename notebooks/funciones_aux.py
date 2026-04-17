
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


def limpiar_spa_bilateral(df):

    print("Iniciando limpieza del archivo .spa...")
    
    columnas_a_borrar = []
    
    for col in df.columns:
        # 1. Fuera los canales de apoyo/ruido (_2 y _4)
        if col.endswith('_2') or col.endswith('_4'):
            columnas_a_borrar.append(col)
            
        # 2. Fuera las variables internas reservadas de Medtronic
        elif col.startswith('RESVR'):
            columnas_a_borrar.append(col)
            
        # 3. Fuera el fantasma de la Asimetría del canal derecho
        elif col == 'ASYM09_3':
            columnas_a_borrar.append(col)
            
        # 4. Fuera la fontanería física de la pegatina (Pines, Impedancias de cable)
        elif col in ['C1POSIMP', 'C1NEGIMP', 'GNDIMP', 'C2POSIMP', 'C2NEGIMP', 
                     'C3POSIMP', 'C3NEGIMP', 'C4POSIMP', 'C4NEGIMP', 'BILBITS']:
            columnas_a_borrar.append(col)
            
    # Filtramos por si acaso alguna columna ya no estaba en el archivo
    columnas_a_borrar = [c for c in columnas_a_borrar if c in df.columns]
    
    # Ejecutamos el borrado
    df_limpio = df.drop(columns=columnas_a_borrar)
    
    print(f"Se han eliminado {len(columnas_a_borrar)} columnas basura.")
    return df_limpio

