
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

        
        
def lectura_h_a(archivo_bin):

    with open(archivo_bin, "rb") as archivo:
        contenido = archivo.read()

    print("ARCHIVO DE CABECERA (.h_a)")
    print("-" * 50)

    # 1. Leer el nombre del archivo (Bytes 18 al 31)
    inicio, fin = 18, 32
    texto_crudo = struct.unpack('14s', contenido[inicio:fin])[0]
    nombre_archivo = texto_crudo.decode('ascii').replace('\x00', '')
    print(f"Nombre del archivo:      {nombre_archivo}")

    # Extraer la hora real desde el nombre del archivo (L + Mes + Día + Hora + Min)
    # Sabiendo que el formato es L03041035
    hora_inicio = nombre_archivo[5:7]
    minuto_inicio = nombre_archivo[7:9]
    print(f"Hora de inicio deducida: {hora_inicio}:{minuto_inicio}:")

    # 2. Encontrar el nombre del Algoritmo
    texto_buscar = b"BIS-R2"
    posicion_algo = contenido.find(texto_buscar)

    if posicion_algo != -1:
        inicio, fin = posicion_algo, posicion_algo + 6
        version_algo = struct.unpack('6s', contenido[inicio:fin])[0].decode('ascii')
        print(f"Motor del algoritmo:     {version_algo}")

    # 3. Encontrar los parámetros de Filtro Float (0.05 Hz)
    secuencia_float = bytes.fromhex('cdcc4c3d')
    posicion_float = contenido.find(secuencia_float)

    if posicion_float != -1:
        inicio, fin = posicion_float, posicion_float + 4
        valor_filtro = struct.unpack('<f', contenido[inicio:fin])[0]
        print(f"Configuración de Filtro: {valor_filtro:.2f} Hz")



def procesar_spa(ruta_spa):
    # Leer los datos
    df = pd.read_csv(
        ruta_spa,
        sep="|",
        header=None,
        skiprows=2,
        engine="python"
    )

    # Eliminar columnas completamente vacías
    df = df.dropna(axis=1, how="all")

    # Leer la segunda línea como nombres de columnas
    with open(ruta_spa, "r", errors="ignore") as f:
        _ = f.readline()                      # primera cabecera
        cabecera = f.readline().strip("\n")  # segunda cabecera

    nombres = [x.strip() for x in cabecera.split("|")]
    nombres = nombres[:df.shape[1]]

    # Hacer nombres únicos
    contador = {}
    nombres_unicos = []

    for col in nombres:
        if col == "":
            col = "col_vacia"

        if col in contador:
            contador[col] += 1
            nombres_unicos.append(f"{col}_{contador[col]}")
        else:
            contador[col] = 1
            nombres_unicos.append(col)

    df.columns = nombres_unicos

    # Convertir la fecha
    if "Time" in df.columns:
        df["Time"] = pd.to_datetime(
            df["Time"],
            format="%m/%d/%Y %H:%M:%S",
            errors="coerce"
        )

    return df        
        
    

def traducir_r2a(archivo_entrada, archivo_salida): # Traducir el lenguaje máquina

    """ 
    Abrimos el .r2a a la vez que el .csv uno para leer la info de ahí y otro para escribir
    f_in: abrir el .r2a en modo lectura binaria pura, sin intentar leerlo como texto. 
    f_out:abrir el .csv en modo escritura normal de texto.
    """
    with open(archivo_entrada, "rb") as f_in, open(archivo_salida, "w") as f_out:

        # escribir cabeceras 
        f_out.write("Tiempo_s,Canal_1,Canal_2\n")

        # cada 128 muestras será 1 segundo
        contador_muestras = 0

        # hasta que le digamos que para
        while True:

            # Leemos 4 bytes (2 canales * 2 bytes/canal)
            bytes_muestra = f_in.read(4)

            # si queda un trozo de menos de 4 bytes 
            if not bytes_muestra or len(bytes_muestra) < 4:
                break

            """ 
            traductor struct pasándole el molde '<hh' para desencriptar los 4 bytes:
             - < estaba en little endian: dar la vuelta a los bytes porque la máquina los guardó al revés para sumar más rápido
             - hh short integer: 
                - Guardar en la variable canal_1: Los primeros 2 bytes son un entero de 16 bits con signos positivos y negativos
                - Guardar en la variable canal_2: Los siguientes 2 bytes son otro entero igual
            """
            canal_1, canal_2 = struct.unpack('<hh', bytes_muestra)

            # el tiempo avanza 1 segundo cada 128 muestras
            tiempo_en_segundos = contador_muestras / 128.0

            """ 
            Forma de escribir el archivo en .csv: 
             - escribir el tiempo en segundos con 4 decimales
             - separar las columnas por comas
             - salto de línea al final para que el siguiente segundo vaya después
            """
            f_out.write(f"{tiempo_en_segundos:.4f},{canal_1},{canal_2}\n")

            # avanza el reloj para leer los siguientes 4 bits
            contador_muestras += 1

    print(f"Se procesaron {contador_muestras} muestras por canal.")
    print(f"Tiempo total real: {contador_muestras / 128.0:.2f} segundos.")
    
    
    
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


    

