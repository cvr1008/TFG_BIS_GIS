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

        
# ------------------------------------- explorar campos -------------------------------------------------        
        
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



def cargar_fa_bilateral(ruta_fa, escalar_db=True):
    """
    Carga un archivo .f_a bilateral del BIS.

    Estructura esperada:
        Time | Left Spectra | Right Spectra

    Devuelve:
    - tiempo: serie temporal
    - dsa_L: matriz espectral izquierda
    - dsa_R: matriz espectral derecha

    Las matrices DSA tienen:
    - filas = tiempo
    - columnas = frecuencias de 0.5 a 30 Hz
    - valores = potencia espectral en dB si escalar_db=True
    """

    df = pd.read_csv(
        ruta_fa,
        sep="|",
        header=None,
        skiprows=2,
        engine="python"
    )

    # Limpiar columnas vacías generadas por separadores finales
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all").reset_index(drop=True)

    if df.shape[1] < 3:
        raise ValueError(
            f"El archivo {ruta_fa} no parece bilateral: "
            f"tiene {df.shape[1]} columnas tras limpieza y se esperaban al menos 3."
        )

    # Conservar Time, Left Spectra y Right Spectra
    df = df.iloc[:, :3]
    df.columns = ["Time", "Left Spectra", "Right Spectra"]

    # Convertir tiempo
    df["Time"] = pd.to_datetime(
        df["Time"].astype(str).str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce"
    )

    # Quitar filas sin tiempo válido
    df = df[df["Time"].notna()].reset_index(drop=True)

    # Eje de frecuencias esperado
    frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)

    def procesar_columna_spectra(serie_spectra, nombre):
        """
        Convierte una columna tipo 'Spectra' en matriz DSA.
        """

        dsa = (
            serie_spectra
            .astype(str)
            .str.strip()
            .str.split(",", expand=True)
        )

        dsa = dsa.apply(pd.to_numeric, errors="coerce")

        # Eliminar columnas completamente vacías, si aparecen por comas extra
        dsa = dsa.dropna(axis=1, how="all")

        if dsa.shape[1] < len(frecuencias):
            raise ValueError(
                f"{nombre} tiene {dsa.shape[1]} columnas espectrales, "
                f"pero se esperaban {len(frecuencias)}."
            )

        # Si hubiera alguna columna extra, se toman las 60 primeras
        dsa = dsa.iloc[:, :len(frecuencias)]

        if escalar_db:
            dsa = dsa / 100

        dsa.columns = frecuencias

        return dsa

    dsa_L = procesar_columna_spectra(
        df["Left Spectra"],
        nombre="Left Spectra"
    )

    dsa_R = procesar_columna_spectra(
        df["Right Spectra"],
        nombre="Right Spectra"
    )

    return df["Time"], dsa_L, dsa_R



# ------------------------------------------------ archivo spa --------------------------------------------------
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
                   
    
    
# ---------------------------------------- archivo header ----------------------------------------------------
def extraer_parametros_eeg(ruta_h_a):
    """
    Abre un archivo de cabecera (.h_a) del monitor BIS y extrae únicamente
    los parámetros matemáticos necesarios para procesar la señal de EEG bruta.
    
    Retorna:
        Un diccionario con los parámetros, o None si ocurre un error.
    """
    try:
        with open(ruta_h_a, 'rb') as f:
            # 1. Número de canales EEG (Offset 178, entero de 2 bytes)
            f.seek(178)
            num_canales = struct.unpack('<h', f.read(2))[0]
            
            # 2. Frecuencia de muestreo (Offset 186, entero de 4 bytes)
            f.seek(186)
            fs = struct.unpack('<i', f.read(4))[0]
            
            # 3. Pendiente de calibración "m" (Offset 702, float de 32 bits)
            f.seek(702)
            pendiente = struct.unpack('<f', f.read(4))[0]
            
            # 4. Intersección "b" u Offset (Offset 766, float de 32 bits)
            f.seek(766)
            offset = struct.unpack('<f', f.read(4))[0]
            
            # Agrupamos los resultados en un diccionario para usarlos fácilmente
            return num_canales, fs, pendiente, offset
            
    except Exception as e:
        print(f"Error al extraer parámetros de {ruta_h_a}: {e}")
        return None

    
# ------------------------------------------------ explicar logica crudos ------------------------------------------------
def explicar_frames_r2a(ruta_r2a, n_frames=8, factor_uv=0.05, mostrar=True):
    """
    Lee los primeros n_frames de un archivo .r2a y:
    - separa los frames de 4 bytes
    - divide cada frame en canal 1 y canal 2
    - traduce cada pareja de bytes a entero con signo de 16 bits
    - convierte los valores a microvoltios
    
    Devuelve un DataFrame con el detalle.
    """

    """ 
    "rb" = lectura en modo binario
    read(n_frames * 4) = leer los primeros 32 bytes del archivo
    """
    with open(ruta_r2a, "rb") as f:
        bruto = f.read(n_frames * 4)

        
    # lista vacía en la que se guardan las filas (diccionarios con las características de los frames)
    filas = []

    if mostrar:
        print("ANÁLISIS DEL ARCHIVO .r2a")
        print("-" * 60)
        print(f"Se leen los primeros {n_frames * 4} bytes del archivo.")
        print("Cada frame temporal ocupa 4 bytes:")
        print("  - 2 bytes para el canal 1")
        print("  - 2 bytes para el canal 2")
        print(f"Conversión a microvoltios: valor_crudo × {factor_uv}")
        print()
        
    
    """
    recorrer los frames desde 0 a n-1
    bloque: se cogen los 4 bytes de cada frame. Si se lee que el bloque es más pequeño que eso se detiene
            del bloque principal se divide en 2 sub-bloques uno por cada canal
    """
    for i in range(n_frames):
        bloque = bruto[i*4:(i+1)*4]

        if len(bloque) < 4:
            break

        bytes_c1 = bloque[:2]
        bytes_c2 = bloque[2:]

        
        """        
        Interpreta cada pareja de bytes como un entero con signo de 16 bits
        struct.unpack("<h", bytes_c1):
            h: entero corto con signo, 16 bits, 2 bytes
            <: little-endian
            [0]: porque struct.unpack(...) devuelve una tupla y hay que quedarse con el primer elemento
        """        
        raw_c1 = struct.unpack("<h", bytes_c1)[0]
        raw_c2 = struct.unpack("<h", bytes_c2)[0]

        """ 
        Fórmula de procesamiento: 
        Para obtener la amplitud real de la onda cerebral, debes coger el número entero extraído y multiplicarlo por 0.05. 
        El resultado será el valor de la onda en microvoltios (µV).
        """
        uv_c1 = raw_c1 * factor_uv
        uv_c2 = raw_c2 * factor_uv

        # crea un diccionario con toda la información útil del frame actual
        fila = {
            "Frame": i + 1,
            "Bytes frame": bloque.hex(" "),
            "Bytes C1": bytes_c1.hex(" "),
            "Bytes C2": bytes_c2.hex(" "),
            "Raw C1": raw_c1,
            "Raw C2": raw_c2,
            "C1 (µV)": uv_c1,
            "C2 (µV)": uv_c2,
        }
        filas.append(fila)

        if mostrar:
            print(f"Frame/Muestra {i+1}")
            print(f"  Bytes del frame: {bloque.hex(' ')}")
            print(f"  Canal 1 -> bytes: {bytes_c1.hex(' ')} -> entero: {raw_c1} -> µV: {uv_c1:.2f}")
            print(f"  Canal 2 -> bytes: {bytes_c2.hex(' ')} -> entero: {raw_c2} -> µV: {uv_c2:.2f}")
            print()

    """
    convierte la lista de diccionarios en un DataFrame de pandas
    cada diccionario será una fila
    """
    df_frames = pd.DataFrame(filas)
    return df_frames
