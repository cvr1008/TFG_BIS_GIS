import base64
import io
import numpy as np
import pandas as pd


def cargar_tiempos_fa_desde_ruta(ruta):
    """Lee únicamente la columna temporal del .f_a."""
    df = pd.read_csv(
        ruta,
        sep="|",
        header=None,
        skiprows=2,
        usecols=[0],
        engine="python",
        encoding="latin1",
    )
    return pd.to_datetime(
        df.iloc[:, 0].astype(str).str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce",
    ).dropna().reset_index(drop=True)


def _decode_upload_to_text(contents):
    """
    Convierte el contenido subido por Dash en texto.
    """
    _, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    return decoded.decode("latin1", errors="ignore")


def _cargar_fa_unilateral_desde_texto(texto, escalar_db=True):
    """
    Equivalente adaptado de cargar_fa_directo() de tu repo.

    Estructura esperada:
        Time | Spectra

    Devuelve:
    - tiempo
    - frecuencias
    - dsa
    """

    df = pd.read_csv(
        io.StringIO(texto),
        sep="|",
        header=None,
        skiprows=2,
        engine="python"
    )

    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all").reset_index(drop=True)

    if df.shape[1] < 2:
        raise ValueError(
            f"El .f_a unilateral debería tener al menos 2 columnas, pero tiene {df.shape[1]}."
        )

    df = df.iloc[:, :2]
    df.columns = ["Time", "Spectra"]

    df["Time"] = pd.to_datetime(
        df["Time"].astype(str).str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce"
    )

    df = df[df["Time"].notna()].reset_index(drop=True)

    dsa = (
        df["Spectra"]
        .astype(str)
        .str.strip()
        .str.split(",", expand=True)
    )

    dsa = dsa.apply(pd.to_numeric, errors="coerce")
    dsa = dsa.dropna(axis=1, how="all")

    frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)

    if dsa.shape[1] < len(frecuencias):
        raise ValueError(
            f"Solo se han encontrado {dsa.shape[1]} columnas espectrales; "
            f"se esperaban {len(frecuencias)}."
        )

    dsa = dsa.iloc[:, :len(frecuencias)]

    if escalar_db:
        dsa = dsa / 100.0

    dsa.columns = frecuencias

    return df["Time"], frecuencias, dsa


def cargar_fa_unilateral_desde_upload(contents, escalar_db=True):
    return _cargar_fa_unilateral_desde_texto(
        _decode_upload_to_text(contents),
        escalar_db=escalar_db,
    )


def cargar_fa_unilateral_desde_ruta(ruta, escalar_db=True):
    with open(ruta, "r", encoding="latin1", errors="ignore") as archivo:
        texto = archivo.read()
    return _cargar_fa_unilateral_desde_texto(
        texto,
        escalar_db=escalar_db,
    )


def _cargar_fa_bilateral_desde_texto(texto, escalar_db=True):
    """
    Carga las dos matrices de un archivo .f_a bilateral.

    Estructura esperada:
        Time | Left Spectra | Right Spectra

    Devuelve:
    - tiempo
    - frecuencias
    - dsa_izquierda
    - dsa_derecha
    """

    df = pd.read_csv(
        io.StringIO(texto),
        sep="|",
        header=None,
        skiprows=2,
        engine="python"
    )

    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all").reset_index(drop=True)

    if df.shape[1] < 3:
        raise ValueError(
            f"El .f_a bilateral debería tener al menos 3 columnas "
            f"Time | Left Spectra | Right Spectra, pero tiene {df.shape[1]}."
        )

    df = df.iloc[:, :3]
    df.columns = ["Time", "Left Spectra", "Right Spectra"]

    df["Time"] = pd.to_datetime(
        df["Time"].astype(str).str.strip(),
        format="%m/%d/%Y %H:%M:%S",
        errors="coerce"
    )

    df = df[df["Time"].notna()].reset_index(drop=True)

    frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)

    def procesar_columna_spectra(serie_spectra, nombre):
        dsa = (
            serie_spectra
            .astype(str)
            .str.strip()
            .str.split(",", expand=True)
        )

        dsa = dsa.apply(pd.to_numeric, errors="coerce")
        dsa = dsa.dropna(axis=1, how="all")

        if dsa.shape[1] < len(frecuencias):
            raise ValueError(
                f"{nombre} tiene {dsa.shape[1]} columnas espectrales; "
                f"se esperaban {len(frecuencias)}."
            )

        dsa = dsa.iloc[:, :len(frecuencias)]

        if escalar_db:
            dsa = dsa / 100.0

        dsa.columns = frecuencias

        return dsa

    dsa_izq = procesar_columna_spectra(
        df["Left Spectra"],
        nombre="Left Spectra"
    )

    dsa_der = procesar_columna_spectra(
        df["Right Spectra"],
        nombre="Right Spectra"
    )

    return df["Time"], frecuencias, dsa_izq, dsa_der


def cargar_fa_bilateral_completo_desde_upload(contents, escalar_db=True):
    return _cargar_fa_bilateral_desde_texto(
        _decode_upload_to_text(contents),
        escalar_db=escalar_db,
    )


def cargar_fa_bilateral_completo_desde_ruta(ruta, escalar_db=True):
    with open(ruta, "r", encoding="latin1", errors="ignore") as archivo:
        texto = archivo.read()
    return _cargar_fa_bilateral_desde_texto(
        texto,
        escalar_db=escalar_db,
    )


def cargar_fa_bilateral_desde_upload(contents, lado="izquierda", escalar_db=True):
    """Carga uno de los lados de un archivo .f_a bilateral."""
    tiempo, frecuencias, dsa_izq, dsa_der = (
        cargar_fa_bilateral_completo_desde_upload(
            contents,
            escalar_db=escalar_db,
        )
    )

    if lado == "izquierda":
        return tiempo, frecuencias, dsa_izq
    if lado == "derecha":
        return tiempo, frecuencias, dsa_der

    raise ValueError("lado debe ser 'izquierda' o 'derecha'")
