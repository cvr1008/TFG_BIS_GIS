import sys
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import struct


from matplotlib.colors import LinearSegmentedColormap, PowerNorm



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



def buscar_filas_por_intervalo(df, inicio, fin, columna_tiempo="Time",
                               formato="%m/%d/%Y %H:%M:%S", max_resultados=300,
                               mostrar=True):
    """
    Busca filas de un DataFrame cuyo timestamp esté entre dos fechas/horas.

    Parámetros:
    - df: DataFrame de pandas
    - inicio: string con fecha-hora inicial
    - fin: string con fecha-hora final
    - columna_tiempo: nombre de la columna temporal
    - formato: formato de fecha si inicio y fin vienen como texto
    - max_resultados: máximo de filas a mostrar/devolver
    - mostrar: si True, imprime el resultado

    Devuelve:
    - DataFrame filtrado
    """

    try:
        # Convertir inicio y fin a datetime
        dt_inicio = datetime.strptime(inicio, formato)
        dt_fin = datetime.strptime(fin, formato)

        # Comprobar que la columna existe
        if columna_tiempo not in df.columns:
            raise ValueError(f"La columna '{columna_tiempo}' no existe en el DataFrame.")

        # Copia para no modificar el original
        df_busqueda = df.copy()

        # Asegurar que la columna temporal es datetime
        if not pd.api.types.is_datetime64_any_dtype(df_busqueda[columna_tiempo]):
            df_busqueda[columna_tiempo] = pd.to_datetime(
                df_busqueda[columna_tiempo],
                format=formato,
                errors="coerce"
            )

        # Filtrar intervalo
        resultado = df_busqueda[
            (df_busqueda[columna_tiempo] >= dt_inicio) &
            (df_busqueda[columna_tiempo] <= dt_fin)
        ].head(max_resultados)

        if mostrar:
            print(f"\n--- Buscando entre {inicio} y {fin} ---")
            if resultado.empty:
                print("No se encontraron filas en ese intervalo.")
            else:
                display(resultado)

        return resultado

    except Exception as e:
        print(f"Error: {e}")
        return None

        
        
def buscar_filas_por_valor(df, columna, operador, valor1, valor2=None, max_resultados=300, mostrar=True):
    """
    Busca filas de un DataFrame según una condición sobre una columna.

    Parámetros:
    - df: DataFrame de pandas
    - columna: nombre de la columna donde buscar
    - operador: "==", "<", "<=", ">", ">=", "between"
    - valor1: valor principal de comparación
    - valor2: segundo valor si operador = "between"
    - max_resultados: máximo de filas a devolver
    - mostrar: si True, muestra el resultado

    Devuelve:
    - DataFrame filtrado
    """

    try:
        if columna not in df.columns:
            raise ValueError(f"La columna '{columna}' no existe en el DataFrame.")

        df_busqueda = df.copy()

        # Convertir la columna a numérica si hace falta
        df_busqueda[columna] = pd.to_numeric(df_busqueda[columna], errors="coerce")

        if operador == "==":
            resultado = df_busqueda[df_busqueda[columna] == valor1]

        elif operador == "<":
            resultado = df_busqueda[df_busqueda[columna] < valor1]

        elif operador == "<=":
            resultado = df_busqueda[df_busqueda[columna] <= valor1]

        elif operador == ">":
            resultado = df_busqueda[df_busqueda[columna] > valor1]

        elif operador == ">=":
            resultado = df_busqueda[df_busqueda[columna] >= valor1]

        elif operador == "between":
            if valor2 is None:
                raise ValueError("Para el operador 'between' necesitas valor1 y valor2.")
            resultado = df_busqueda[
                (df_busqueda[columna] >= valor1) & (df_busqueda[columna] <= valor2)
            ]

        else:
            raise ValueError("Operador no válido. Usa: ==, <, <=, >, >=, between")

        resultado = resultado.head(max_resultados)

        if mostrar:
            print(f"\n--- Buscando filas donde {columna} {operador} {valor1}" +
                  (f" y {valor2}" if operador == "between" else "") + " ---")

            if resultado.empty:
                print("No se encontraron filas.")
            else:
                display(resultado)

        return resultado

    except Exception as e:
        print(f"Error: {e}")
        return None
    
    
        
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


        
def cargar_fa_directo(ruta_fa, escalar_db=True):
    """
    Carga un archivo .f_a directamente en un DataFrame.
    Devuelve:
    - tiempo: serie temporal
    - dsa: matriz espectral (filas=tiempo, columnas=frecuencia)
    """


    """
    ruta_fa: ruta del archivo
    sep="|": le dice a pandas que el separador principal es |
    header=None: le dice que no use ninguna fila como nombres de columnas
    skiprows=2: se salta las dos primeras líneas del archivo que so cabecera
    engine="python": usa el motor de Python para leerlo, que suele ser más flexible con archivos raros
    """
    df = pd.read_csv(
        ruta_fa,
        sep="|",
        header=None,
        skiprows=2,
        engine="python"
    )


    """
    print(df.shape)
    print(df.head())
    Esto nos muestra que al principio hay 3 columnas
    """


    # limpiar columnas vacías generadas por el | final
    df = df.dropna(axis=1, how="all") # axis=1 es columnas. Elimina solo si toda la columna está vacía
    
    # Para quedarme solo con las dos primeras columnas del DataFrame
    """ 
    iloc sirve para seleccionar por posición, por número de fila y número de columna
     - : en la parte de filas selecciona todas las filas
     - : :2 en la parte de columnas selecciona desde la columna 0 a la 1
    Realmente esto es para asegurarse de que solo se conservarán las dos columnas
    """
    df = df.iloc[:, :2]

    # df.columns es la lista de nombres de columnas del DataFrame. Aquí renombra las columnas.
    df.columns = ["Time", "Spectra"]


    # Convertir tiempo
    """ 
    Selecciona la columna de Time que está en formato texto
    Quita espacios sobrantes al principio y al final de cada valor de texto
    Transforma texto en fecha-hora de pandas y pone el formato que BIS suele usar el americano

    errors="coerce": si algún valor no se puede convertir bien se convierte en NaT
    """
    df["Time"] = pd.to_datetime(
        df["Time"].str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce"
    )


    # Separar los 60 valores espectrales
    """ 
    Cada fila de Spectra es un único texto largo con 60 valores separados por comas.
    Se quitan los espacios sobrantes al principio y fin de texto
    Se divide el texto usando la coma de separador

    expand=True: convierte cada elemento del split (números que estaban en una lista) en una columna distinta

    Este DataFrame ya es esencialmente la matriz DSA:
     - filas = instantes temporales
     - columnas = bandas de frecuencia
     - valores = intensidad espectral

    Falta convertir valores a número y colocar nombres de frecuencia
    """
    dsa = df["Spectra"].str.strip().str.split(",", expand=True)
    
    # convertir esas columnas de texto en números reales que son decibelios
    dsa = dsa.apply(pd.to_numeric, errors="coerce") 



    # Escalado: si está activada la corrección de escala, divide toda la matriz espectral entre 100 para obtener los valores reales
    if escalar_db:
        dsa = dsa / 100



    # crea el eje de frecuencias: 0.5 a 30 Hz. 
    # np.arange genera números espaciados regularmente. 
    # 30.0 + 0.5 porque el límite final no siempre se incluye directamente
    frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)

    # Cambia los nombres de las columnas de dsa.
    dsa.columns = frecuencias


    """ 
    Devuelve una serie temporal de pandas y la matriz dsa

    No se devuelve un único df final:
     - tiempo: 
        filas: una por instante temporal
        contenido: timestamp
        tipo: datetime64[ns]

     - dsa:
        filas: instantes temporales
        columnas: frecuencias
        valores: intensidad espectral
    """
    return df["Time"], dsa



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
                   
                                
    
def traducir_r2a(archivo_entrada, archivo_salida, factor_uv=0.05):
    
    """ 
    Abrimos el .r2a a la vez que el .csv uno para leer la info de ahí y otro para escribir
    f_in: abrir el .r2a en modo lectura binaria pura, sin intentar leerlo como texto. 
    f_out:abrir el .csv en modo escritura normal de texto.
    """
    
    with open(archivo_entrada, "rb") as f_in, open(archivo_salida, "w") as f_out:

        f_out.write("Tiempo_s,Canal_1_raw,Canal_2_raw,Canal_1_uV,Canal_2_uV\n")

        # cada 128 muestras será 1 segundo
        # no son muestras totales del archivo, sino frames o instantes de muestreo
        # cada frame contiene una muestra del canal 1 y una del canal 2
        contador_muestras = 0

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

            # Conversión a microvoltios
            canal_1_uv = canal_1 * factor_uv
            canal_2_uv = canal_2 * factor_uv

            # el tiempo avanza 1 segundo cada 128 muestras
            tiempo_en_segundos = contador_muestras / 128.0

            
            """ 
            Forma de escribir el archivo en .csv: 
             - escribir el tiempo en segundos con 4 decimales
             - separar las columnas por comas
             - salto de línea al final para que el siguiente segundo vaya después
            """
            f_out.write(
                f"{tiempo_en_segundos:.4f},{canal_1},{canal_2},{canal_1_uv:.4f},{canal_2_uv:.4f}\n"
            )
            
            # avanza el reloj para leer los siguientes 4 bytes
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


    

