import pandas as pd
import numpy as np

from matplotlib.colors import PowerNorm

from funciones_dsa import (
    obtener_hora_inicio_desde_spa,
    crear_cmap_bis
)


def leer_r4a(ruta_archivo, fs=128, escala_uv=0.0511):
    """
    Lee un archivo .r4a del BIS bilateral.

    Estructura:
    - 4 canales
    - int16 little-endian
    - canales intercalados: ch1, ch2, ch3, ch4, ch1, ch2, ch3, ch4...
    - escala: 0.0511 µV/step
    """

    datos = np.fromfile(ruta_archivo, dtype="<i2")

    # Asegurar que el número de valores sea múltiplo de 4
    resto = len(datos) % 4
    if resto != 0:
        datos = datos[:-resto]

    datos = datos.reshape(-1, 4)

    canal_1_raw = datos[:, 0]
    canal_2_raw = datos[:, 1]
    canal_3_raw = datos[:, 2]
    canal_4_raw = datos[:, 3]

    tiempo_s = np.arange(len(canal_1_raw)) / fs

    df_eeg = pd.DataFrame({
        "tiempo_s": tiempo_s,

        "canal_1_raw": canal_1_raw,
        "canal_2_raw": canal_2_raw,
        "canal_3_raw": canal_3_raw,
        "canal_4_raw": canal_4_raw,

        "canal_1_uV": canal_1_raw * escala_uv,
        "canal_2_uV": canal_2_raw * escala_uv,
        "canal_3_uV": canal_3_raw * escala_uv,
        "canal_4_uV": canal_4_raw * escala_uv
    })

    return df_eeg



def limpiar_spa_bilateral(df_spa):
    """
    Limpia y estandariza el .spa para modo bilateral.
    Genera columnas separadas para lado izquierdo y derecho.
    """

    df, _ = obtener_hora_inicio_desde_spa(df_spa)
    df = df.reset_index(drop=True)

    columnas_izq = [
        "SR12", "SEF08", "MEDFRQ08", "BISBIT00", "DB13U01",
        "DB11U04", "B34U05", "TOTPOW08", "EMGLOW01",
        "SQI10", "IMPEDNCE", "ARTF2", "BURST", "ST"
    ]

    columnas_der = [
        "SR12_3", "SEF08_3", "MEDFRQ08_3", "BISBIT00_3", "DB13U01_3",
        "DB11U04_3", "B34U05_3", "TOTPOW08_3", "EMGLOW01_3",
        "SQI10_3", "IMPEDNCE_3", "ARTF2_3", "BURST_3", "ST_3"
    ]

    df_out = pd.DataFrame()
    df_out["Time"] = df["Time"]

    for col in columnas_izq:
        col_out = f"{col}_izq"

        if col in df.columns:
            df_out[col_out] = pd.to_numeric(df[col], errors="coerce")
        else:
            df_out[col_out] = np.nan
            print(f"Advertencia: no se encontró la columna izquierda {col}")

    for col in columnas_der:
        base = col.replace("_3", "")
        col_out = f"{base}_der"

        if col in df.columns:
            df_out[col_out] = pd.to_numeric(df[col], errors="coerce")
        else:
            df_out[col_out] = np.nan
            print(f"Advertencia: no se encontró la columna derecha {col}")

    if "ASYM09" in df.columns:
        df_out["ASYM09"] = pd.to_numeric(df["ASYM09"], errors="coerce")
    else:
        df_out["ASYM09"] = np.nan
        print("Advertencia: no se encontró la columna ASYM09")

    sentinelas = [-327.7, -3276.0, -3276.8, -3276, -32767, -32768]
    cols_num = [c for c in df_out.columns if c != "Time"]
    df_out[cols_num] = df_out[cols_num].replace(sentinelas, np.nan)

    df_out["modo_spa"] = "bilateral"

    return df_out


def extraer_lado_spa_bilateral(df_spa_bilat, lado="izq"):
    """
    Extrae un lado del .spa bilateral y lo convierte a nombres estándar.
    """

    if lado not in ["izq", "der"]:
        raise ValueError("lado debe ser 'izq' o 'der'")

    df = pd.DataFrame()
    df["Time"] = df_spa_bilat["Time"]

    variables = [
        "SR12", "SEF08", "MEDFRQ08", "BISBIT00", "DB13U01",
        "DB11U04", "B34U05", "TOTPOW08", "EMGLOW01",
        "SQI10", "IMPEDNCE", "ARTF2", "BURST", "ST"
    ]

    for var in variables:
        col_lado = f"{var}_{lado}"

        if col_lado in df_spa_bilat.columns:
            df[var] = df_spa_bilat[col_lado]
        else:
            df[var] = np.nan
            print(f"Advertencia: no se encontró {col_lado}")

    if "ASYM09" in df_spa_bilat.columns:
        df["ASYM09"] = df_spa_bilat["ASYM09"]

    df["modo_spa"] = f"bilateral_{lado}"

    return df


# -------------------------------------------------------------------------------------------------------

def preparar_escala_color_dsa_bilateral(dsa_plot_1, dsa_plot_2, gamma=0.55):
    """
    Prepara una escala de color común para dos matrices DSA bilaterales.
    """

    matriz_1 = dsa_plot_1.values
    matriz_2 = dsa_plot_2.values

    vals_1 = matriz_1[np.isfinite(matriz_1)]
    vals_2 = matriz_2[np.isfinite(matriz_2)]

    vals = np.concatenate([vals_1, vals_2])

    if len(vals) == 0:
        raise ValueError("No hay valores válidos en ninguna de las dos DSA bilaterales.")

    vmin = np.nanpercentile(vals, 2)
    vmax = np.nanpercentile(vals, 99.5)

    norm = PowerNorm(gamma=gamma, vmin=vmin, vmax=vmax)
    cmap = crear_cmap_bis()

    return matriz_1, matriz_2, vmin, vmax, norm, cmap

# -------------------------------------------------------------------------- lo del csv --------------------------------------------------

def convertir_r4a_a_csv(archivo_entrada, archivo_salida):
    """
    Convierte un archivo de ondas crudas .r4a (Bilateral, 4 canales) a formato CSV.
    Basado en las especificaciones del monitor BIS: 
    - 128 muestras por segundo (Hz).
    - Los valores enteros se multiplican por 0.05 para obtener microvoltios (µV).
    
    Parámetros:
    - archivo_entrada (str): Ruta al archivo .r4a que se desea leer.
    - archivo_salida (str): Ruta donde se guardará el archivo .csv resultante.
    """
    print(f"Iniciando conversión de ondas crudas (BIS Bilateral) a 128 Hz...")
    print(f"Archivo origen: {archivo_entrada}")
    
    try:
        with open(archivo_entrada, "rb") as f_in, open(archivo_salida, "w") as f_out:
            # 1. Escribimos la cabecera indicando las unidades en microvoltios
            f_out.write("Tiempo_s,Canal_1_uV,Canal_2_uV,Canal_3_uV,Canal_4_uV\n")
            
            contador_muestras = 0
            
            # 2. Bucle de lectura de 8 en 8 bytes (4 canales * 2 bytes/canal)
            while True:
                bytes_muestra = f_in.read(8)
                if not bytes_muestra or len(bytes_muestra) < 8:
                    break
                
                # 3. Desempaquetar 4 enteros de 16 bits con signo ('<hhhh')
                canal_1, canal_2, canal_3, canal_4 = struct.unpack('<hhhh', bytes_muestra)
                
                # 4. Convertir a microvoltios (µV) multiplicando por 0.05
                c1_uv = canal_1 * 0.05
                c2_uv = canal_2 * 0.05
                c3_uv = canal_3 * 0.05
                c4_uv = canal_4 * 0.05
                
                # 5. Calcular tiempo en segundos usando la frecuencia de muestreo (128 Hz)
                tiempo_en_segundos = contador_muestras / 128.0
                
                # 6. Escribir en el CSV con 4 decimales de precisión
                f_out.write(f"{tiempo_en_segundos:.4f},{c1_uv:.4f},{c2_uv:.4f},{c3_uv:.4f},{c4_uv:.4f}\n")
                
                contador_muestras += 1

        print(f"- Muestras por canal procesadas: {contador_muestras}")
        print(f"- Tiempo total del registro: {contador_muestras / 128.0:.2f} segundos.")
        print(f"- Archivo guardado en: {os.path.abspath(archivo_salida)}\n")

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{archivo_entrada}'. Por favor, verifica la ruta.\n")
    except Exception as e:
        print(f"Ocurrió un error inesperado al procesar el archivo: {e}\n")
