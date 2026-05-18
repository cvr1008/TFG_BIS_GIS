import pandas as pd
import numpy as np

from scipy.signal import welch
from scipy.stats import pearsonr, spearmanr
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.colors import BoundaryNorm





def limpiar_spa_para_dsa(df_spa):
    
    """ 
    Coger el DF del .spa y asegurar que las columnas necesarias sean numéricas.
    
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

    sentinelas = [-327.7, -3276.0, -3276.8, -3276, -32767, -32768]
    cols_presentes = [c for c in cols if c in df.columns]
    df[cols_presentes] = df[cols_presentes].replace(sentinelas, np.nan)

    return df



def construir_mascara_no_valida(df_spa, umbral_sqi=14):
    """ 
    Crea una máscara booleana que marca en qué filas la señal no debe considerarse válida.
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
    Convierte la columna Time del .spa a datetime, redondea al segundo y devuelve:
    - df_spa preparado
    - hora_inicio
    
    No solamente hay queçobtener hora_inicio, también el df_spa que se usará después tenga Time en formato datetime para que el merge funcione bien.
    """

    df = df_spa.copy()

    if columna_tiempo not in df.columns:
        raise ValueError(f"El DataFrame del .spa no contiene la columna '{columna_tiempo}'.")

    df[columna_tiempo] = pd.to_datetime(
        df[columna_tiempo],
        errors="coerce"
    ).dt.floor("s")

    df = df.dropna(subset=[columna_tiempo])

    if df.empty:
        raise ValueError("No hay tiempos válidos en el .spa.")

    hora_inicio = df[columna_tiempo].min()

    return df, hora_inicio



def alinear_spa_con_tiempo(tiempo, df_spa, columnas=None):
    
    if columnas is None:
        columnas = ["SEF08", "MEDFRQ08", "SQI10", "TOTPOW08", "EMGLOW01", "BURST", "DB13U01", "ASYM09"]

    df_spa = limpiar_spa_para_dsa(df_spa)

    cols = ["Time"] + [c for c in columnas if c in df_spa.columns]

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
        df_spa[cols],   
        on="Time",
        how="left"
    )

    return df_merge



def preparar_dsa_para_plot(tiempo, dsa, df_merge, umbral_sqi=14, umbral_ceros=0.9):
    
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

    Salida:
    - df_dsa: DataFrame con columna tiempo_s y columnas 0.5 ... 30.0
    - frecuencias: array de frecuencias usadas

    modo:
    - "db": potencia en decibelios usando scaling="spectrum"
    - "db_densidad": densidad espectral en dB usando scaling="density"
    - "potencia": potencia espectral en µV²
    - "densidad": densidad espectral en µV²/Hz
    - "amplitud": amplitud espectral estimada en µV

    tiempo_referencia:
    - "inicio": etiqueta cada fila con el inicio de la ventana
    - "centro": etiqueta cada fila con el centro de la ventana
    - "final": etiqueta cada fila con el final de la ventana
    """

    x = df_eeg[canal].to_numpy(dtype=float)

    nperseg = int(ventana_seg * fs)      # 2 s * 128 Hz = 256 muestras
    paso = int(paso_seg * fs)            # 1 s * 128 Hz = 128 muestras
    nfft = int(fs / paso_freq)           # 128 / 0.5 = 256

    tiempos = []
    espectros = []

    for inicio in range(0, len(x) - nperseg + 1, paso):
        fin = inicio + nperseg
        segmento = x[inicio:fin]

        scaling = "density" if modo in ["densidad", "db_densidad"] else "spectrum"

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

        mascara = (f >= fmin) & (f <= fmax)
        f_sel = f[mascara]
        pxx_sel = pxx[mascara]

        if modo == "db":
            valores = 10 * np.log10(pxx_sel + 1e-12)
        elif modo == "db_densidad":
            valores = 10 * np.log10(pxx_sel + 1e-12)
        elif modo in ["potencia", "densidad"]:
            valores = pxx_sel
        elif modo == "amplitud":
            valores = np.sqrt(pxx_sel)
        else:
            raise ValueError("modo debe ser 'db', 'db_densidad', 'potencia', 'densidad' o 'amplitud'")

        if tiempo_referencia == "inicio":
            tiempo_s = inicio / fs
        elif tiempo_referencia == "centro":
            tiempo_s = (inicio + nperseg / 2) / fs
        elif tiempo_referencia == "final":
            tiempo_s = fin / fs
        else:
            raise ValueError("tiempo_referencia debe ser 'inicio', 'centro' o 'final'")

        tiempos.append(tiempo_s)
        espectros.append(valores)

    df_dsa = pd.DataFrame(
        espectros,
        columns=[f"{freq:.1f}" for freq in f_sel]
    )

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

    hora_inicio = pd.Timestamp(hora_inicio).floor("s")

    columnas_freq = [f"{f:.1f}" for f in frecuencias]

    columnas_faltantes = [col for col in columnas_freq if col not in df_dsa.columns]
    if columnas_faltantes:
        raise ValueError(f"Faltan columnas de frecuencia en df_dsa: {columnas_faltantes[:5]}...")

    df = df_dsa.copy()

    if insertar_fila_inicial_nan:
        primera_fila = {"tiempo_s": 0.0}

        for col in columnas_freq:
            primera_fila[col] = np.nan

        df = pd.concat(
            [pd.DataFrame([primera_fila]), df],
            ignore_index=True
        )

    tiempo = pd.Series(hora_inicio + pd.to_timedelta(df["tiempo_s"], unit="s"), name="Time").dt.floor("s")

    dsa = df[columnas_freq].copy()

    return tiempo, dsa

   
    
# --------------------------------- Funciones calibración ------------------------------------------------


def preparar_matrices_para_comparacion(dsa_1, dsa_2):
    """
    Asegura que las dos DSA tengan:
    - mismas columnas
    - misma longitud
    - columnas en el mismo orden
    """

    dsa_1 = dsa_1.copy()
    dsa_2 = dsa_2.copy()

    # Convertir nombres de columnas a float para evitar diferencias tipo "0.5" vs 0.5
    dsa_1.columns = [float(c) for c in dsa_1.columns]
    dsa_2.columns = [float(c) for c in dsa_2.columns]

    columnas_comunes = sorted(set(dsa_1.columns).intersection(set(dsa_2.columns)))

    n = min(len(dsa_1), len(dsa_2))

    dsa_1 = dsa_1.iloc[:n][columnas_comunes]
    dsa_2 = dsa_2.iloc[:n][columnas_comunes]

    return dsa_1, dsa_2


def zscore_global(df):
    """
    Normaliza toda la matriz con media y desviación típica global, ignorando NaN.
    """
    # convierte la DSA a matriz numérica
    matriz = df.to_numpy(dtype=float)

    # media y desviación típica ignorando NaN
    media = np.nanmean(matriz)
    std = np.nanstd(matriz)

    if std == 0 or np.isnan(std):
        raise ValueError("No se puede aplicar z-score: desviación típica nula o NaN.")
    
    # aplica la fórmula
    matriz_z = (matriz - media) / std

    return pd.DataFrame(matriz_z, index=df.index, columns=df.columns)


def comparar_dsa_global(dsa_1, dsa_2):
    """
    Calcula métricas globales entre dos matrices DSA.
    Compara solo posiciones donde ambas matrices tienen valores válidos.
    """

    A = dsa_1.to_numpy(dtype=float)
    B = dsa_2.to_numpy(dtype=float)

    mask = np.isfinite(A) & np.isfinite(B)

    A_valid = A[mask]
    B_valid = B[mask]

    if len(A_valid) == 0:
        raise ValueError("No hay valores válidos comunes para comparar.")

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

    for col in dsa_1.columns:
        a = dsa_1[col].to_numpy(dtype=float)
        b = dsa_2[col].to_numpy(dtype=float)

        mask = np.isfinite(a) & np.isfinite(b)

        if mask.sum() > 2:
            r = pearsonr(a[mask], b[mask])[0]
        else:
            r = np.nan

        resultados.append({
            "frecuencia_Hz": col,
            "correlacion": r
        })

    return pd.DataFrame(resultados)


def correlacion_por_tiempo(dsa_1, dsa_2, tiempo=None):
    """
    Calcula la correlación fila a fila.
    Cada fila representa un instante temporal.
    """

    resultados = []

    for i in range(len(dsa_1)):
        a = dsa_1.iloc[i].to_numpy(dtype=float)
        b = dsa_2.iloc[i].to_numpy(dtype=float)

        mask = np.isfinite(a) & np.isfinite(b)

        if mask.sum() > 2:
            r = pearsonr(a[mask], b[mask])[0]
        else:
            r = np.nan

        resultados.append(r)

    df = pd.DataFrame({"correlacion": resultados})

    if tiempo is not None:
        df.insert(0, "Time", tiempo.iloc[:len(df)].values)

    return df


def probar_suavizado_y_shifts(
    dsa_eeg,
    dsa_fa,
    ventanas_suavizado=(5, 10, 15, 25, 30, 40, 60, 80),
    shifts=range(-60, 61)
):
    resultados = []

    for w in ventanas_suavizado:
        dsa_eeg_suav = dsa_eeg.rolling(
            window=w,
            min_periods=1,
            center=False
        ).mean()

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