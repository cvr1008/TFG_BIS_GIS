import sys
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import struct

from funciones_aux import *


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
        
    
    
def limpiar_spa_para_dsa(df_spa):
    
    """ 
    Coger el DF del .spa y asegurar que las columnas necesarias sean numéricas.
    
    """
    
    # Copiar el dF original para no modificar el original
    df = df_spa.copy()

    # Definir columnas necesarias para modificar la DSA: SEF, MEF, Calidad de la señal y Potencia total
    # Se utilizan para superponer las curvas y detectar tramos inválidos
    cols = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08"]
    
    # Va columna por columna para ver si está en la lista
    # Convertir los valores a numéricos
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df



def construir_mascara_no_valida(df_spa, umbral_sqi=14):
    
    """ 
    Crea una máscara booleana que marca en qué filas la señal no debe considerarse válida.
    
    """
    # Extrae la columna SQI10 
    sqi = df_spa["SQI10"]
    
    # Extrae TOTPOW08 
    totpow = df_spa["TOTPOW08"]

    """ 
    Se alinean y convierten las filas a True/False: es True si: 
     - SQI10 < 14
     - TOTPOW08 es igual o muy próximo a -327.7
    Basta con que falle una condición para marcar la fila como no válida.
    
    Con números decimales a veces hay pequeñas diferencias de precisión.
    Así se aceptan valores muy cercanos a -327.7, no solo el idéntico.
    """
    mask_no_valida = (sqi < umbral_sqi) | (np.isclose(totpow, -327.7))
    
    return mask_no_valida
    
    
    
def crear_cmap_bis():
    
    """ 
    Crea un colormap personalizado parecido al del BIS
    
    """
    
    # colores
    # Rampa aproximada a la leyenda del monitor BIS
    colores_bis = [
        "#001a8f",  # azul oscuro
        "#004cff",  # azul
        "#00c8ff",  # cian
        "#46e6b2",  # verde-agua
        "#d7ef3c",  # amarillo verdoso
        "#ffe100",  # amarillo
        "#ff8c00",  # naranja
        "#d40000",  # rojo
    ]
    
    # Construcción de un colormapcontinuo a partir de esos colores 
    # Hace que el gradiente tenga 256 niveles de color transicionando entre los 8 definidos
    cmap = LinearSegmentedColormap.from_list("bis_like", colores_bis, N=256)
    
    # qué color usar para valores inválidos
    # cuando en el DF de la dsa haya una fila NaN se pinta de blanco
    cmap.set_bad(color="white")
    return cmap



def plot_dsa_pdf_con_spa(tiempo, dsa, df_spa, umbral_sqi=14, vmin=None, vmax=None, gamma=0.55):

    """ 
    Parte de la matriz dsa del .f_a de la anterior función
    Utiliza el .spa para usar la información procesada
    Detectar los tramos no válidos
    Tramos no válidos -> blanco
    dibujar DSA
    Superponer SEF y MEF
    """
    
    # limpiar el dF y convertir columnas en numérico
    df_spa = limpiar_spa_para_dsa(df_spa)

    
    """
    Alinear el df del .spa con el df de la DSA por tiempo:
     - tiempo, dsa: variables que vienen del .f_a (instantes de tiempo y decibelios según frecuencia)
     - df_spa: DataFrame procedente del .spa. Lo hemos limpiado y quedan las columnas numéricas.
               Están los instantes de tiempo y los valores de los campos 
     
    df_aux: Creación de un dF auxiliar que contiene solo la serie temporal de la DSA
    df_merge: se hace una unión del DF de tiempo con las columnas limpias del dF del .spa
        - on: como las dos tienen las columnas de tiempo en común se fusionan por ahí
        - how="left": conserva todos los tiempos de la DSA, aunque en el .spa falte alguno
    """
    df_aux = pd.DataFrame({"Time": tiempo}).reset_index(drop=True)
    df_merge = df_aux.merge(
        df_spa[["Time", "SEF08", "MEDFRQ08", "SQI10", "TOTPOW08"]],
        on="Time",
        how="left"
    )

    
    # guardar los valores de los campos del sef y mef para luego dibujar las curvas
    sef = df_merge["SEF08"]
    mf = df_merge["MEDFRQ08"]

    
    # copiar la matriz de densidad espectral para modificarla. Se copia y convierte a float
    # van a entrar los NaN y hace falta float
    dsa_plot = dsa.copy().astype(float)

    
    # metemos el dF de unión con el tiempo de la dsa y los campos del spa
    # marca las filas que cumplen los requisitos como no válidas
    mask_no_valida = construir_mascara_no_valida(df_merge, umbral_sqi=umbral_sqi)

    
    """ 
    compara cada celda con el 0 y del true/false (1 y 0) se hace media por filas
    si la media es > a 0.9 (más del 90% son ceros) se marca esa fila como no válida
    
    Si una fila tiene casi todo a cero, probablemente no aporta información útil
    """
    porcentaje_ceros = (dsa_plot == 0).mean(axis=1)
    mask_ceros = porcentaje_ceros > 0.9

    
    """ 
    se calcula la diferencia entre cada tiempo y el anterior (la primera da NaT porque no tiene instante anterior) (se hace una columna)
    se convierten las diferencias a segundos numéricos
    
    si los segundos son >1 se vuelven True esos valores y el resto false (mete false el NaN del inicio)
    
    mira si hay huecos temporales en la grabación si de repente pasas de un segundo a un salto de varios 
    """
    delta_t = tiempo.diff().dt.total_seconds()
    mask_saltos = delta_t.gt(1).fillna(False)

    
    """
    unir las tres condiciones con un OR lógico
    una fila no es válida si :
     - mala calidad/valor no válido según .spa
     - casi todo ceros
     - salto temporal
    """
    mask_total = mask_no_valida | mask_ceros | mask_saltos

    
    # en las filas marcadas como no válidas se sustituyen los valores por NaN (que saldrán en blanco)
    dsa_plot.loc[mask_total.values, :] = np.nan

    # convierte el DataFrame en una matriz de numPy
    matriz = dsa_plot.values

    # se crea una matriz del mismo tamaño con true/false (si es un valor finito normal o no)
    # se guardan en un vector solo los valores que sean reales (los true)
    vals = matriz[np.isfinite(matriz)]
    
    
    # se calculan los percentiles con los valores del vector
    if vmin is None:
        vmin = np.nanpercentile(vals, 2)
    if vmax is None:
        vmax = np.nanpercentile(vals, 99.5)

        
    """ 
    se controla cómo se reparten los colores sobre los valores de la DSA
     - PowerNorm: transformación no lineal. Reparte los colores con una potencia controlada por gamma.
                  normalización = ((x - vmin) / (vmax - vmin)) ^ gamma
                 
     - gamma: cambia la forma en que los valores intermedios se distribuyen entre vmin y vmax
              gamma = 1: normalización lineal, no hay cambios
              gamma < 1 (0.55): hace que los valores intermedios suban visualmente en la escala
              gamma > 1 (1.2): comprime los intermedios hacia abajo y predominan más los tonos bajos
    
     - vmin: valor mínimo referencia. Lo que sea igual o por debajo va al extremo
     - vmax: valor máximo referencia. Lo que sea igual o por encima va al extremo
    """
    norm = PowerNorm(gamma=gamma, vmin=vmin, vmax=vmax)
    
    # crear el colormap con los colores tipo BIS y blanco para el NaN
    cmap = crear_cmap_bis()

    
    
    # ---------------------------- Creación de la figura --------------------------------------
    
    fig, ax = plt.subplots(figsize=(4.8, 10))

    
    # definir el primer y último tiempo del registro
    y0 = mdates.date2num(tiempo.iloc[0])
    y1 = mdates.date2num(tiempo.iloc[-1])
    
    # definir la mínima y máxima frecuencia que se representa en la DSA
    x0 = dsa_plot.columns.min()
    x1 = dsa_plot.columns.max()

    
    """ 
    mostrar la matriz:
     - aspect="auto": Ajusta la forma
     - origin="upper": primera fila de la matriz va arriba
     - extent=[x0, x1, y1, y0]: coloca la imagen. En el eje X frecuencia e Y tiempo
                                invierte el eje temporal para que el tiempo inicial quede arriba
     - cmap=cmap: usa la paleta BIS
     - norm=norm: normalización calculada
     - interpolation="nearest": no suaviza artificialmente los píxeles
    """
    im = ax.imshow(
        matriz,
        aspect="auto",
        origin="upper",
        extent=[x0, x1, y1, y0],
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    
    """ 
    invert_xaxis(): los 30 Hz quedan a la izquierda y los 0.5 a la derecha
    yaxis_date(): eje Y temporal
    DateFormatter("%H:%M"): tiempo como horas y minutos
    """
    ax.invert_xaxis()
    ax.yaxis_date()
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    
    # texto descriptivo
    ax.set_xlabel("Frecuencia")
    ax.set_ylabel("Tiempo")
    ax.set_title("DSA", loc="left", fontsize=9, pad=6)

    # marcas de frecuencias de separación de las bandas
    ax.set_xticks([30, 13, 8, 4])
    ax.set_xticklabels(["30Hz", "13Hz", "8Hz", "4Hz"], fontsize=8)

    # dibujar las líneas verticales para separar bandas
    for f in [13, 8, 4]:
        ax.axvline(f, color="gray", linestyle="--", linewidth=1, alpha=0.7)

    bandas = {
        "Beta":  (13 + 30) / 2,
        "Alpha": (8 + 13) / 2,
        "Theta": (4 + 8) / 2,
        "Delta": (0.5 + 4) / 2,
    }

    
    
    for nombre, xpos in bandas.items():
        ax.text(
            xpos, 1.01, nombre,
            transform=ax.get_xaxis_transform(),
            ha="center", va="bottom",
            fontsize=8, rotation=45
        )

    """
    curvas SEF y MF con datos válidos
    
    creación de máscaras booleanas para decidir qué puntos se pueden dibujar sobre la DSA
     - se quitan los valores NaN y los valores por fuera del rango de frecuencias
    """
    mask_sef = sef.notna() & (sef >= 0.5) & (sef <= 30)
    mask_mf = mf.notna() & (mf >= 0.5) & (mf <= 30)

    # dibujar las líneas blanca y morada
    ax.plot(
    sef[mask_sef], tiempo[mask_sef],
    color="white", linewidth=2.0, alpha=0.95, label="SEF"
    )

    ax.plot(
        mf[mask_mf], tiempo[mask_mf],
        color="purple", linewidth=2.0, alpha=0.95, label="MEF"
    )
    
    # colocar la leyenda fuera del gráfico a la derecha
    ax.legend(
    loc="upper left",
    bbox_to_anchor=(1.25, 0.92),
    frameon=True,
    facecolor="white",
    framealpha=0.85,
    fontsize=8,
    borderaxespad=0
    )

    # añadir la barra de color con etiqueta vertical y máximo y mínimo
    cbar = plt.colorbar(im, ax=ax, pad=0.03)
    cbar.set_ticks([vmin, vmax])
    cbar.set_ticklabels(["Min", "Max"])
    cbar.ax.tick_params(length=0)
    cbar.set_label("Intensidad espectral (dB)", rotation=90, labelpad=12)

    
    plt.tight_layout()
    plt.show()
    

    
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
        # no son muestras totales del archivo, sino frames o instantes de muestreo
        # cada frame contiene una muestra del canal 1 y una del canal 2
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


    

