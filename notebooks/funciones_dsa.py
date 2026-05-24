import pandas as pd
import numpy as np

from scipy.signal import welch
from scipy.stats import pearsonr, spearmanr
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.colors import BoundaryNorm
import matplotlib.pyplot as plt
import matplotlib.dates as mdates






def limpiar_spa_para_dsa(df_spa):
    
    """ 
    Coger el DF del .spa y asegurar que las columnas necesarias sean numéricas.
    
    Parámetros:
     - df_spa: spa original
    
    Devuelve:
     - df: spa en el cual las columnas de valores centinelas han sido pasados a NaN
    """
    
    # Copiar el dF original para no modificar el original
    df = df_spa.copy()

    # Definir columnas necesarias para modificar la DSA: SEF, MEF, Calidad de la señal y Potencia total
    # Se utilizan para superponer las curvas y detectar tramos inválidos
    cols = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01", "ASYM09"]
    
    # Va columna por columna para ver si está en la lista
    # Convertir los valores a numéricos
   
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # definir los valores centinelas
    sentinelas = [-327.7, -3276.0, -3276.8, -3276, -32767, -32768]
    # si la variable está en el spa, la metemos en el nuevo spa limpio
    cols_presentes = [c for c in cols if c in df.columns]
    # si la columna tiene valores centinelas los convertimos a NaN
    df[cols_presentes] = df[cols_presentes].replace(sentinelas, np.nan)

    return df



def construir_mascara_no_valida(df_spa, umbral_sqi=15):
    """ 
    Crea una máscara booleana que marca en qué filas la señal no debe considerarse válida.
    
    Parámetros:
     - df_spa: dF con el spa original
     - umbral_sqi=15: criterio para la creación de una máscara basada en la calidad de la señal
    
    Devuelve:
     - mask_no_valida: serie de pandas que pone true a los segundos de variables no válidas y false a los segundos donde sí había información útil.
    """

    mask_no_valida = pd.Series(False, index=df_spa.index)

    if "SQI10" in df_spa.columns:
        sqi = pd.to_numeric(df_spa["SQI10"], errors="coerce")
        mask_no_valida = mask_no_valida | (sqi < umbral_sqi)

    if "TOTPOW08" in df_spa.columns:
        totpow = pd.to_numeric(df_spa["TOTPOW08"], errors="coerce")
        mask_no_valida = mask_no_valida | totpow.isna() | np.isclose(totpow, -327.7)

    return mask_no_valida
    
    
    
def crear_cmap_bis():
    
    """ 
    Crea un colormap personalizado parecido al del BIS
    
    Devuelve:
     - cmap: colormap con los valores válidos en color y los inválidos en blanco
    """
    
    # colores
    # Rampa aproximada a la leyenda del monitor BIS
    colores_bis = [
        "#000080",  # azul oscuro
        "#0033cc",  # azul intenso
        "#25fade",  # cian
        "#94ff6e",  # verde
        "#f5f532",  # amarillo
        "#FF3F34",  # rojo-naranja
        "#ac0505"   # rojo oscuro
    ]
    
    # Construcción de un colormapcontinuo a partir de esos colores 
    # Hace que el gradiente tenga 256 niveles de color transicionando entre los 8 definidos
    cmap = LinearSegmentedColormap.from_list("bis_like", colores_bis, N=256)
    
    # qué color usar para valores inválidos
    # cuando en el DF de la dsa haya una fila NaN se pinta de blanco
    cmap.set_bad(color="white")
    return cmap



def obtener_hora_inicio_desde_spa(df_spa, columna_tiempo="Time"):
    """
    No solamente hay queçobtener hora_inicio, también el df_spa que se usará después tenga Time en formato datetime para que el merge funcione bien.
    
    Parámetros:
     - df_spa: DataFrame procedente del archivo .spa.
     - columna_tiempo="Time": nombre de la columna donde está la fecha y hora. Por defecto se llama "Time".
    
    Devuelve:
     - df: el DataFrame .spa preparado, con la columna Time en formato datetime y redondeada al segundo.
     - hora_inicio: el primer instante temporal del .spa.
    """

    # copia del dF original para no modificar el spa y siga intacto
    df = df_spa.copy()

    # comprobación de si la columna temporal existe en el dF y lanzamiento de error para parar el programa
    if columna_tiempo not in df.columns:
        raise ValueError(f"El DataFrame del .spa no contiene la columna '{columna_tiempo}'.")

    """
    Conversión de la columna temporal a formato datetime de pandas. Para convertirlo a fecha-hora real.
     - errors="coerce": valores inválidos se convierten en NaT.
     - ).dt.floor("s"): redondear los tiempos hacia abajo al segundo más cercano.
    """
    df[columna_tiempo] = pd.to_datetime(
        df[columna_tiempo],
        errors="coerce"
    ).dt.floor("s")
    

    # elimina las filas donde la columna Time es inválida o está vacía
    df = df.dropna(subset=[columna_tiempo])

    if df.empty:
        raise ValueError("No hay tiempos válidos en el .spa.")

    # como df[columna_tiempo] tiene todos los tiempos válidos, .min() devuelve la fecha y hora del primero
    hora_inicio = df[columna_tiempo].min()

    return df, hora_inicio



def alinear_spa_con_tiempo(tiempo, df_spa, columnas=None):
    """
    Alinear el df del .spa con el df de la DSA por tiempo:
    
    Parámetros:
     - tiempo, dsa: variables que vienen del .f_a (instantes de tiempo y decibelios según frecuencia)
     - df_spa: DataFrame procedente del .spa. Lo hemos limpiado y quedan las columnas numéricas.
               Están los instantes de tiempo y los valores de los campos 
     - columnas: variables del spa que queremos incluir en el dF de fusión
     
    Devuelve:
    df_merge: se hace una unión del DF de tiempo con las columnas limpias del dF del .spa
        - on: como las dos tienen las columnas de tiempo en común se fusionan por ahí
        - how="left": conserva todos los tiempos de la DSA, aunque en el .spa falte alguno
    """
    # si no le pasamos las variables del spa tenemos algunas por defecto
    if columnas is None:
        columnas = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01", "ASYM09"]

    # llamada a la función de limpieza y obtenemos un spa sin valores centinela
    df_spa = limpiar_spa_para_dsa(df_spa)

    # lista con las columnas de variables procesadas cada segundo y la columna de tiempo
    cols = ["Time"] + [c for c in columnas if c in df_spa.columns]

    # creación de un dF auxiliar que contiene solo la serie temporal de la DSA
    df_aux = pd.DataFrame({"Time": tiempo}).reset_index(drop=True)
    df_merge = df_aux.merge(
        df_spa[cols],   
        on="Time",
        how="left"
    )

    return df_merge



def preparar_dsa_con_mask(tiempo, dsa, df_merge, umbral_sqi=15, umbral_ceros=0.9):
    
    """
    Parámetros:
     - tiempo:
     - dsa:
     - df_merge:
     - umbral_sqi=15:
     - umbral_ceros=0.9:
    
    Devuelve:
     - dsa_plot:
     - mask_total:
    """
    
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
    mask_ceros = porcentaje_ceros > umbral_ceros

    
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

    return dsa_plot, mask_total



def preparar_escala_color_dsa(dsa_plot, vmin=None, vmax=None, gamma=0.55):
    
    # convierte el DataFrame en una matriz de numPy
    matriz = dsa_plot.values

    # se crea una matriz del mismo tamaño con true/false (si es un valor finito normal o no)
    # se guardan en un vector solo los valores que sean reales (los true)
    vals = matriz[np.isfinite(matriz)]
    
    if len(vals) == 0:
        raise ValueError("No hay valores válidos en la DSA para preparar la escala de color.")

    
    # se calculan los percentiles con los valores del vector
    if vmin is None:
        vmin = np.nanpercentile(vals, 2)
    if vmax is None:
        vmax = np.nanpercentile(vals, 99.5)

        
    if vmin == vmax:
        raise ValueError("vmin y vmax son iguales; no se puede crear una escala de color válida.")
    
    
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

    return matriz, vmin, vmax, norm, cmap





# ------------------------------- Funciones de EEG a DSA -----------------------------------------


def crear_matriz_dsa_fft_welch_desde_eeg(
    df_eeg,
    canal,
    fs=128,
    ventana_seg=2,
    paso_seg=1,
    fmin=0.5,
    fmax=30.0,
    paso_freq=0.5,
    modo="db",
    tiempo_referencia="centro"
):
    """
    Crea una matriz tiempo-frecuencia para DSA desde EEG crudo mediante FFT/Welch.
    
    Parámetros:
     - df_eeg: DataFrame que contiene el EEG cr.udo ya leído desde el archivo .r2a.
     - canal: qué columna del DataFrame se analiza (canal="canal_1_uV" o canal="canal_2_uV")
     - fs: frecuencia de muestreo (128)
     - ventana_seg: duración de cada ventana de análisis (2 segundos)
     - paso_seg: cuánto avanza la ventana cada vez (1 segundo). Esto significa que las ventanas se solapan.
     - fmin: frecuencia mínima que se conserva (0.5 Hz)
     - fmax: frecuencia máxima que se conserva (30 Hz)
     - paso_freq: resolución frecuencial (0.5 Hz)
     - modo: en qué unidad se va a devolver el espectro
            - "db": potencia en decibelios usando scaling="spectrum"
            - "db_densidad": densidad espectral en dB usando scaling="density"
            - "potencia": potencia espectral en µV²
            - "densidad": densidad espectral en µV²/Hz 
            - "amplitud": amplitud espectral estimada en µV
     - tiempo_referencia: indica qué tiempo se asigna a cada ventana.
                         - "inicio": etiqueta cada fila con el inicio de la ventana
                         - "centro": etiqueta cada fila con el centro de la ventana
                         - "final": etiqueta cada fila con el final de la ventana

    Devuelve:
    - df_dsa:un DataFrame donde cada fila es una ventana temporal y cada columna es una frecuencia.
    - frecuencias: array numérico con las frecuencias seleccionadas.
    """

    # Coge la columna de la señal cruda en  uV del dF 
    # .to_numpy(dtype=float) la convierte en un array numérico de np
    # x será: [valor1, valor2, valor3, valor4, ...]
    x = df_eeg[canal].to_numpy(dtype=float)

    # cuántas muestras hay en cada ventana
    nperseg = int(ventana_seg * fs)                                    # 2 s * 128 Hz = 256 muestras
    # cuántas muestras avanza la ventana cada vez
    paso = int(paso_seg * fs)                                          # 1 s * 128 Hz = 128 muestras
    """
    -tamaño de la FFT
    -como la resolución frecuencial de una FFT 
     se calcula como: resolución = fs / nfft
    -con nfft=256 se consiguen frecuencias separadas cada 0.5 Hz
    """
    nfft = int(fs / paso_freq)                                         # 128 / 0.5 = 256
 
    # lista vacía con los tiempos asociados a cada ventana
    tiempos = []
    # lista donde se guardarán los espectros calculados para cada ventana
    # cada elemento de la lista es una fila de la DSA
    espectros = []

    for inicio in range(0, len(x) - nperseg + 1, paso):
        """
        Recorrido de la señal por ventanas:
         - Empieza en 0.
         - Termina en len(x) - nperseg + 1, para que la ventana completa.
         - Avanza de paso en paso.
        """
        
        # dónde termina la ventana: 0+256, 128+256, 256+256, ...
        fin = inicio + nperseg
        # extrae el fragmento de EEG correspondiente a esa ventana.
        segmento = x[inicio:fin]

        # elegir tipo de salida de Welch
        scaling = "density" if modo == "densidad" else "spectrum"


        """
        Cálculo espectral con Welch:
        Parámetros:
         - segmento: fragmento de EEG de 2 segundos, la ventana
         - fs: frecuencia de muestreo, 128 Hz. Para que Welch devuelva frecuencias en Hz reales
         - window="hann": Aplica una ventana de Hann al segmento antes de calcular el espectro (reduce discontinuidades en los bordes)
         - nperseg=nperseg: tamaño del segmento usado por Welch (256 muestras)
         - noverlap=0: dentro de cada llamada a welch no hay solapamiento entre subsegmentos
         - nfft=nfft: Tamaño de la FFT.
         - detrend="constant": Elimina la componente constante del segmento antes de calcular el espectro.
         - scaling=scaling: tipo de escala decidido antes: density o spectrum
         
        Devuelve:
         - f: vector de frecuencias. Ejemplo: [0.0, 0.5, 1.0, ..., 64.0]
         - pxx: potencia o densidad espectral asociada a cada frecuencia.
        """
        f, pxx = welch(
            segmento,
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=0,
            nfft=nfft,
            detrend="constant",
            scaling=scaling
        )

        # máscara booleana para quedarme con las frecuencias entre fmin y fmax
        mascara = (f >= fmin) & (f <= fmax)
        # seleccionar las frecuencias en el rango
        f_sel = f[mascara]
        # seleccionar los valores espectrales correspondientes a esas frecuencias.
        pxx_sel = pxx[mascara]

        if modo in ["potencia", "densidad"]:
            valores = pxx_sel
        elif modo == "amplitud":
            valores = np.sqrt(pxx_sel)
        else:
            raise ValueError("modo debe ser 'db', 'db_densidad', 'potencia', 'densidad' o 'amplitud'")

        if tiempo_referencia == "inicio":
            # Convierte índice de muestra inicial a segundos.
            tiempo_s = inicio / fs
        elif tiempo_referencia == "centro":
            # Calcula el centro de la ventana.
            tiempo_s = (inicio + nperseg / 2) / fs
        elif tiempo_referencia == "final":
            # Convierte el índice final de la ventana a segundos.
            tiempo_s = fin / fs
        else:
            raise ValueError("tiempo_referencia debe ser 'inicio', 'centro' o 'final'")

        """
        tiempos = [1.0, 2.0, 3.0, ...]
        espectros = [
            [potencias de la ventana 1],
            [potencias de la ventana 2],
            [potencias de la ventana 3], ...]
        """
        # Añade el tiempo de esta ventana a la lista tiempos.
        tiempos.append(tiempo_s)
        # Añade el espectro calculado para esta ventana a la lista espectros.
        espectros.append(valores)

    
    """
    Convierte la lista de espectros en un DataFrame.
    Cada fila es una ventana temporal.
    Cada columna es una frecuencia.
     - {freq:.1f}: Los nombres de columnas se formatean con un decimal.
    """
    df_dsa = pd.DataFrame(
        espectros,
        columns=[f"{freq:.1f}" for freq in f_sel]
    )

    # Insertar la columna tiempo_s al principio del DataFrame
    df_dsa.insert(0, "tiempo_s", tiempos)

    return df_dsa, f_sel



def adaptar_dsa_reconstruida_para_plot(df_dsa, frecuencias, hora_inicio, insertar_fila_inicial_nan=False):
    """
    Convierte la DSA reconstruida desde EEG crudo al formato esperado
    por las funciones de visualización.

    Entrada:
    - df_dsa: DataFrame con columna tiempo_s y columnas de frecuencia.
    - frecuencias: array con frecuencias.
    - hora_inicio: Timestamp del inicio del registro.
    - insertar_fila_inicial_nan:
        Si True, añade una primera fila en tiempo_s = 0 con NaN.
        Esto es útil cuando la DSA se calculó con tiempo_referencia='centro'
        y la primera estimación real cae 1 segundo después del inicio.

    Salida:
    - tiempo: Serie datetime.
    - dsa: DataFrame solo con columnas espectrales.
    """

    # asegurarse de que la hora está en formato Timestamp para pandas
    # redondeamos ese tiempo al segundo más cercano (hacia abajo)
    hora_inicio = pd.Timestamp(hora_inicio).floor("s")

    # cada una de las frecuencias las convierte en un string y las almacena en una lista
    columnas_freq = [f"{f:.1f}" for f in frecuencias]

    # mete aquí todas las columnas que puedan faltar en el dF y sí que hubiera en la dsa
    columnas_faltantes = [col for col in columnas_freq if col not in df_dsa.columns]
    if columnas_faltantes:
        raise ValueError(f"Faltan columnas de frecuencia en df_dsa")

    # copia del df
    df = df_dsa.copy()

    # pedimos una fila inicial de NaN para poder suplir la falta del primer segundo 
    # a causa de la ventana de 2 segundos
    if insertar_fila_inicial_nan:
        
        # establece el tiempo en 0.0 segundos y llena las columnas de frecuencia con NaN
        primera_fila = {"tiempo_s": 0.0}

        for col in columnas_freq:
            primera_fila[col] = np.nan

        # convierte la primera fila en un dF de una fila y lo concatena al inicio del dF
        df = pd.concat(
            [pd.DataFrame([primera_fila]), df],
            ignore_index=True
        )
    
    """
     - Las filas de la columna tiempo_s (los segundos de medición de tiempo) se convierten en deltas de tiempo -> duraciones/cantidades de tiempo.
     - Se suman esos segundos a la hora de inicio extraída de la función y se vuelve a crear la columna tiempo con la fecha y hora, minuto y segundo de cada registro
     - Se guarda en una Serie de Pandas llamada "Time" y vuelve a redondear al segundo exacto: .dt.floor("s")
    """
    
    tiempo = pd.Series(hora_inicio + pd.to_timedelta(df["tiempo_s"], unit="s"), name="Time").dt.floor("s")
    
    # nos quedamos únicamente con las columnas que contienen los valores de frecuencia
    # deja fuera la columna de tiempo
    dsa = df[columnas_freq].copy()

    return tiempo, dsa



def calcular_sef_mef_desde_potencia(
    potencia,
    frecuencias,
    percentil_sef=0.95,
    percentil_mef=0.50
):
    """
    Calcula SEF y MEF a partir de una matriz de potencia lineal.

    Parámetros:
    - potencia: matriz numpy o DataFrame con forma tiempo x frecuencia.
    - frecuencias: array/lista con las frecuencias correspondientes a las columnas.
    - percentil_sef: por defecto 0.95 para SEF95.
    - percentil_mef: por defecto 0.50 para frecuencia mediana.

    Devuelve:
    - sef: array con la frecuencia bajo la cual se acumula el 95% de la potencia.
    - mef: array con la frecuencia bajo la cual se acumula el 50% de la potencia.
    """

    potencia = np.asarray(potencia, dtype=float)
    frecuencias = np.asarray(frecuencias, dtype=float)

    sef = np.full(potencia.shape[0], np.nan)
    mef = np.full(potencia.shape[0], np.nan)

    for i in range(potencia.shape[0]):
        p = potencia[i, :]

        mask = np.isfinite(p) & (p >= 0)

        if mask.sum() == 0:
            continue

        p_valid = p[mask]
        f_valid = frecuencias[mask]

        potencia_total = np.sum(p_valid)

        if potencia_total <= 0:
            continue

        acumulada = np.cumsum(p_valid)
        proporcion = acumulada / potencia_total

        idx_mef = np.searchsorted(proporcion, percentil_mef)
        idx_sef = np.searchsorted(proporcion, percentil_sef)

        mef[i] = f_valid[min(idx_mef, len(f_valid) - 1)]
        sef[i] = f_valid[min(idx_sef, len(f_valid) - 1)]

    return sef, mef

   
    
# --------------------------------- Funciones calibración ------------------------------------------------


def preparar_matrices_para_comparacion(dsa_1, dsa_2):
    """
    Asegura que las dos DSA tengan:
    - mismas columnas
    - misma longitud
    - columnas en el mismo orden
    """

    # copias para no alterar los datos originales
    dsa_1 = dsa_1.copy()
    dsa_2 = dsa_2.copy()

    # recorrer los nombres de las columnas (las frecuencias en Hz)
    # forzar a float para que estén en un mismo formato
    dsa_1.columns = [float(c) for c in dsa_1.columns]
    dsa_2.columns = [float(c) for c in dsa_2.columns]

    # convertir las columnas en conjuntos y extraer solo las que existen en ambas matrices: intersección
    # luego ordena las columnas de menor a mayor frecuencia
    columnas_comunes = sorted(set(dsa_1.columns).intersection(set(dsa_2.columns)))

    # busca cuál es la matriz más corta
    # si el eeg graba más que lo que tenemos en el f_a se recorta 
    n = min(len(dsa_1), len(dsa_2))

    # coge las filas desde la 0 hasta la n y filtra solo las frecuencias compartidas y ordenadas
    dsa_1 = dsa_1.iloc[:n][columnas_comunes]
    dsa_2 = dsa_2.iloc[:n][columnas_comunes]

    return dsa_1, dsa_2


def zscore_global(df):
    """
    Normaliza toda la matriz con media y desviación típica global, ignorando NaN.
    
    Z(t, f) = (D(t, f) - media_D)/std_D
    """
    # convierte la DSA a matriz numérica en float
    matriz = df.to_numpy(dtype=float)

    # media y desviación típica. Ignora los huecos (NaN) para que no devuelva NaN ante un solo hueco
    media = np.nanmean(matriz)
    std = np.nanstd(matriz)

    # evitar problemas al calcular el z-score por intentar dividir entre 0
    if std == 0 or np.isnan(std):
        raise ValueError("Desviación típica nula")
    
    # fórmula z-score a cada celda simultáneamente
    matriz_z = (matriz - media) / std

    # volver a convertir la matriz a dataFrame con sus índices de tiempo y columnas de frecuencias
    matriz_normalizada = pd.DataFrame(matriz_z, index=df.index, columns=df.columns)
    
    return matriz_normalizada


def comparar_dsa_global(dsa_1, dsa_2):
    """
    Calcula métricas globales entre dos matrices DSA.
    Compara solo posiciones donde ambas matrices tienen valores válidos.
    """

    # se pasan las dsa a arrays de numpy en float
    A = dsa_1.to_numpy(dtype=float)
    B = dsa_2.to_numpy(dtype=float)

    # se crea una máscara donde solo son true las celdas en las que ambas matrices tienen un número real
    mask = np.isfinite(A) & np.isfinite(B)

    # se le aplica la máscara a las matrices y se extraen los valores donde la máscara es true
    # la matriz pierde su forma rectangular (una matriz no puede tener huecos) -> convertir a listas planas -> A_valid y B_valid tienen la misma longitud
    A_valid = A[mask]
    B_valid = B[mask]

    if len(A_valid) == 0:
        raise ValueError("No hay valores válidos comunes para comparar.")

    """ 
    Métricas
    MAE: mide error medio absoluto -> resta un array del otro, lo pone en valor absoluto y saca la media
    RMSE: penaliza más los errores grandes -> resta, eleva al cuadrado, hace la media, y saca la raíz cuadrada
    bias: resta para ver hacia donde se dirige el error
    pearson: cuantificar la similitud lineal entre los valores normalizados de ambas matrices DSA
    spearman: evaluar la fuerza y dirección de la asociación entre los arrays. Evaluar si la estructura de intensidades se mantenía entre matrices aunque la relación no fuera estrictamente lineal.
    """
    mae = np.mean(np.abs(A_valid - B_valid))
    rmse = np.sqrt(np.mean((A_valid - B_valid) ** 2))
    bias = np.mean(B_valid - A_valid)

    pearson = pearsonr(A_valid, B_valid)[0]
    spearman = spearmanr(A_valid, B_valid)[0]

    return {
        "n_valores_comparados": len(A_valid),
        "MAE": mae,
        "RMSE": rmse,
        "bias_B_menos_A": bias,
        "Pearson": pearson,
        "Spearman": spearman
    }


def correlacion_por_frecuencia(dsa_1, dsa_2):
    """
    Calcula la correlación entre ambas DSA para cada frecuencia.
    """

    resultados = []

    # itera columna a columna (frecuencia a frec. Cada 0.5 Hz)
    for col in dsa_1.columns:
        # convertir esa columna (de cada dsa) a array numérico de numpy
        a = dsa_1[col].to_numpy(dtype=float)
        b = dsa_2[col].to_numpy(dtype=float)

        # máscara donde solo son true las celdas en las que ambas matrices tienen un número real
        mask = np.isfinite(a) & np.isfinite(b)

        # contar cuántos True hay
        # pearson requiere de 3 puntos de datos para calcular una correlación. Si no, devuelve NaN
        if mask.sum() > 2:
            r = pearsonr(a[mask], b[mask])[0]
        else:
            r = np.nan

        # guardar cada frecuencia con su correlación
        resultados.append({
            "frecuencia_Hz": col,
            "correlacion": r})

    return pd.DataFrame(resultados)


def correlacion_por_tiempo(dsa_1, dsa_2, tiempo=None):
    """
    Calcula la correlación fila a fila.
    Cada fila representa un instante temporal.
    """

    resultados = []

    # itera segundo a segundo (fila)
    for i in range(len(dsa_1)):
        # convertir esa columna (de cada dsa) a array numérico de numpy
        a = dsa_1.iloc[i].to_numpy(dtype=float)
        b = dsa_2.iloc[i].to_numpy(dtype=float)

        # máscara donde solo son true las celdas en las que ambas matrices tienen un número real
        mask = np.isfinite(a) & np.isfinite(b)

        # contar cuántos True hay
        # pearson requiere de 3 puntos de datos para calcular una correlación. Si no, devuelve NaN
        if mask.sum() > 2:
            r = pearsonr(a[mask], b[mask])[0]
        else:
            r = np.nan

        resultados.append(r)

    df = pd.DataFrame({"correlacion": resultados})

    # al pasarle una columna de marcas temporales reales, se inserta la primera
    if tiempo is not None:
        df.insert(0, "Time", tiempo.iloc[:len(df)].values)

    return df


def probar_suavizado_y_shifts(
    dsa_eeg,
    dsa_fa,
    ventanas_suavizado=(0, 5, 10, 30, 60),
    shifts=range(-60, 61)
):
    resultados = []

    for w in ventanas_suavizado:
        dsa_eeg_suav = dsa_eeg.rolling(
            window=w,
            min_periods=1,
            center=False
        ).mean()
    
        #dsa_eeg_suav.loc[mask_total.values, :] = np.nan

        for shift in shifts:

            if shift < 0:
                A = dsa_eeg_suav.iloc[-shift:].reset_index(drop=True)
                B = dsa_fa.iloc[:len(A)].reset_index(drop=True)

            elif shift > 0:
                A = dsa_eeg_suav.iloc[:-shift].reset_index(drop=True)
                B = dsa_fa.iloc[shift:].reset_index(drop=True)

            else:
                A = dsa_eeg_suav.reset_index(drop=True)
                B = dsa_fa.reset_index(drop=True)

            n = min(len(A), len(B))
            A = A.iloc[:n]
            B = B.iloc[:n]

            A_z = zscore_global(A)
            B_z = zscore_global(B)

            met = comparar_dsa_global(A_z, B_z)

            resultados.append({
                "suavizado_s": w,
                "shift_s": shift,
                "Pearson": met["Pearson"],
                "Spearman": met["Spearman"],
                "MAE": met["MAE"],
                "RMSE": met["RMSE"]
            })

    return pd.DataFrame(resultados)



def dibujar_panel_dsa_en_grid(
    fig,
    subgs,
    tiempo,
    frecuencias,
    matriz,
    norm,
    cmap,
    df_merge=None,
    titulo="DSA",
    etiqueta_colorbar="Intensidad espectral (dB)",
    mostrar_sef=False,
    mostrar_mef=False,
    mask_total=None
):
    """
    Dibuja un único panel DSA dentro de una subrejilla de 1x3:
    [DSA | bandas | colorbar]
    """

    frecuencias = np.asarray(frecuencias, dtype=float)

    x0 = mdates.date2num(tiempo.iloc[0] if hasattr(tiempo, "iloc") else tiempo[0])
    x1 = mdates.date2num(tiempo.iloc[-1] if hasattr(tiempo, "iloc") else tiempo[-1])

    y0 = np.min(frecuencias)
    y1 = np.max(frecuencias)

    # matriz: tiempo x frecuencia -> para imshow usamos frecuencia x tiempo
    matriz_hor = matriz.T

    ax = fig.add_subplot(subgs[0])
    ax_band = fig.add_subplot(subgs[1])
    cax = fig.add_subplot(subgs[2])
    
    im = ax.imshow(
        matriz_hor,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    # SEF / MEF
    if df_merge is not None:
        if mostrar_sef and "SEF08" in df_merge.columns:
            sef_plot = df_merge["SEF08"].copy()
            sef_plot[(sef_plot < y0) | (sef_plot > y1)] = np.nan

            if mask_total is not None:
                sef_plot.loc[np.asarray(mask_total)] = np.nan

            ax.plot(
                tiempo,
                sef_plot,
                color="white",
                linewidth=1.8,
                label="SEF"
            )

        if mostrar_mef and "MEDFRQ08" in df_merge.columns:
            mef_plot = df_merge["MEDFRQ08"].copy()
            mef_plot[(mef_plot < y0) | (mef_plot > y1)] = np.nan

            if mask_total is not None:
                mef_plot.loc[np.asarray(mask_total)] = np.nan

            ax.plot(
                tiempo,
                mef_plot,
                color="#7a1fa2",
                linewidth=1.8,
                label="MEF"
            )

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0,
            frameon=True,
            facecolor="white",
            framealpha=0.8,
            fontsize=8
        )

    # formato eje X
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    plt.setp(ax.get_xticklabels(), rotation=45, fontsize=8)

    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Frecuencia (Hz)")
    ax.set_title(titulo, fontsize=10)
    ax.set_ylim(y0, y1)

    # líneas de bandas
    for f in [4, 8, 13]:
        ax.axhline(
            f,
            color="gray",
            linestyle="--",
            linewidth=1,
            alpha=0.7
        )

    # eje lateral de bandas
    ax_band.set_ylim(y0, y1)
    ax_band.set_xlim(0, 1)
    ax_band.axis("off")

    bandas = {
        "Delta": (0.5 + 4) / 2,
        "Theta": (4 + 8) / 2,
        "Alpha": (8 + 13) / 2,
        "Beta":  (13 + 30) / 2,
    }

    for nombre, ypos in bandas.items():
        ax_band.text(
            0.05,
            ypos,
            nombre,
            va="center",
            ha="left",
            fontsize=8
        )

    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label(etiqueta_colorbar, rotation=90, labelpad=10, fontsize=8)
    cbar.ax.tick_params(labelsize=8)

    return ax, ax_band, cax


def plot_cuadricula_4_dsa(paneles, titulo_general="Comparación de matrices DSA"):
    """
    Dibuja 4 DSA una debajo de otra con el mismo tamaño de eje.

    Estructura global:
    fila 1: [DSA | bandas | colorbar]
    fila 2: [DSA | bandas | colorbar]
    fila 3: [DSA | bandas | colorbar]
    fila 4: [DSA | bandas | colorbar]
    """

    if len(paneles) != 4:
        raise ValueError("Se esperan exactamente 4 paneles.")

    fig = plt.figure(figsize=(16, 20))

    # Una sola rejilla global para todas las filas.
    # Esto fuerza que todas las columnas tengan el mismo ancho en todos los paneles.
    gs = fig.add_gridspec(
        nrows=4,
        ncols=3,
        width_ratios=[20, 1.5, 0.8],
        height_ratios=[1, 1, 1, 1],
        left=0.06,
        right=0.94,
        bottom=0.06,
        top=0.94,
        wspace=0.06,
        hspace=0.35
    )

    axes_out = []

    # Límites temporales globales para que todos tengan exactamente el mismo eje X
    x0_global = min([p["tiempo"].iloc[0] for p in paneles])
    x1_global = max([p["tiempo"].iloc[-1] for p in paneles])
    x0_global = mdates.date2num(x0_global)
    x1_global = mdates.date2num(x1_global)

    # Límites de frecuencia globales
    todas_freq = np.concatenate([
        np.asarray(p["frecuencias"], dtype=float) for p in paneles
    ])
    y0_global = np.nanmin(todas_freq)
    y1_global = np.nanmax(todas_freq)

    for i, panel in enumerate(paneles):

        subgs = [gs[i, 0], gs[i, 1], gs[i, 2]]

        ax, ax_band, cax = dibujar_panel_dsa_en_grid(
            fig=fig,
            subgs=subgs,
            **panel
        )

        # Forzar mismos límites en todos los paneles
        ax.set_xlim(x0_global, x1_global)
        ax.set_ylim(y0_global, y1_global)
        ax_band.set_ylim(y0_global, y1_global)

        # Solo dejamos etiqueta X en el último panel para que no sature
        if i < len(paneles) - 1:
            ax.set_xlabel("")
            plt.setp(ax.get_xticklabels(), visible=False)

        axes_out.append((ax, ax_band, cax))

    fig.suptitle(titulo_general, fontsize=15)

    plt.show()

    return fig, axes_out