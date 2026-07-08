from __future__ import annotations

import base64
import io
import re
import textwrap

import matplotlib.dates as mdates
import pandas as pd
from matplotlib import rcParams
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch
from PIL import Image

from src.figuras_estaticas import crear_panoramica_estatica
from src.visualizacion_icca import NOMBRES_VARIABLES


A4_VERTICAL = (8.27, 11.69)
A4_HORIZONTAL = (11.69, 8.27)
AZUL = "#12385b"
GRIS_TEXTO = "#2f4050"
GRIS_CLARO = "#eef3f7"
BORDE = "#c9d6e2"
COLORES_VARIABLES = {
    "fc": "#1f77b4",
    "pa_sistolica": "#d62728",
    "pa_diastolica": "#1f77b4",
    "pa_media": "#9467bd",
    "spo2": "#17a2b8",
    "pic": "#ff7f0e",
    "frecuencia_respiratoria": "#2ca02c",
    "temperatura": "#e377c2",
}
COLORES_PERFUSIONES = [
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
]

rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
    }
)


def _primer_texto(*valores, defecto="No disponible"):
    """
    Ejecuta la lógica asociada a primer texto.

    Parámetros
    ----------
    defecto : Any
        Valor de entrada utilizado por la función.

    valores : Any
        Valores que se van a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    for valor in valores:
        if valor is None:
            continue
        try:
            if pd.isna(valor):
                continue
        except (TypeError, ValueError):
            pass
        texto = str(valor).strip()
        if texto:
            return texto
    return defecto


def _formatear_fecha(valor):
    """
    Formatea fecha.

    Parámetros
    ----------
    valor : Any
        Valor que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    try:
        fecha = pd.Timestamp(valor)
    except (TypeError, ValueError):
        return "No disponible"
    if pd.isna(fecha):
        return "No disponible"
    return fecha.strftime("%d/%m/%Y %H:%M:%S")


def _formatear_numero(valor):
    """
    Formatea numero.

    Parámetros
    ----------
    valor : Any
        Valor que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    numero = pd.to_numeric(pd.Series([valor]), errors="coerce").iloc[0]
    if pd.isna(numero):
        return str(valor)
    return f"{float(numero):.2f}".rstrip("0").rstrip(".")


def _guardar_pagina(pdf, fig):
    """
    Guarda pagina.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    fig : Any
        Figura que se va a modificar.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    pdf.savefig(fig)


def _texto_en_figura(fig, x, y, texto, width=100, fontsize=9.5, color=GRIS_TEXTO, weight=None, line_height=0.023):
    """
    Ejecuta la lógica asociada a texto en figura.

    Parámetros
    ----------
    fig : Any
        Figura que se va a modificar.

    x : Any
        Valor de entrada utilizado por la función.

    y : Any
        Valor de entrada utilizado por la función.

    texto : Any
        Texto que se va a procesar.

    width : Any
        Valor de entrada utilizado por la función.

    fontsize : Any
        Valor de entrada utilizado por la función.

    color : Any
        Valor de entrada utilizado por la función.

    weight : Any
        Valor de entrada utilizado por la función.

    line_height : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    lineas = textwrap.wrap(str(texto), width=width) or [""]
    for indice, linea in enumerate(lineas):
        fig.text(
            x,
            y - indice * line_height,
            linea,
            fontsize=fontsize,
            color=color,
            weight=weight,
        )
    return y - max(line_height, line_height * len(lineas))


def _formatear_eje_tiempo(ax):
    """
    Formatea eje tiempo.

    Parámetros
    ----------
    ax : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    localizador = mdates.AutoDateLocator(minticks=4, maxticks=9)
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M"))


def _rango_y_con_margen(valores):
    """
    Ejecuta la lógica asociada a rango y con margen.

    Parámetros
    ----------
    valores : Any
        Valores que se van a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    serie = pd.to_numeric(pd.Series(valores), errors="coerce").dropna()
    if serie.empty:
        return None
    minimo = float(serie.min())
    maximo = float(serie.max())
    amplitud = maximo - minimo
    margen = max(amplitud * 0.12, abs(maximo) * 0.03, 1.0)
    return minimo - margen, maximo + margen


def _texto_origen(registro):
    """
    Ejecuta la lógica asociada a texto origen.

    Parámetros
    ----------
    registro : Any
        Datos del registro que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    origen = registro.get("origen")
    if origen == "fa":
        return "Archivo .f_a"
    if origen == "reconstruida":
        return "Reconstruccion desde crudo"
    return _primer_texto(origen)


def _datos_basicos(registro, inicio, fin, duracion):
    """
    Ejecuta la lógica asociada a datos basicos.

    Parámetros
    ----------
    registro : Any
        Datos del registro que se va a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    duracion : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    sesion = registro.get("sesion_paciente") or {}
    return [
        ("Paciente", _primer_texto(sesion.get("paciente_id"), registro.get("paciente_id"))),
        (
            "Sesion BIS",
            _primer_texto(
                sesion.get("nombre_carpeta"),
                sesion.get("sesion_bis_id"),
            ),
        ),
        ("Tipo de registro", _primer_texto(registro.get("modo")).capitalize()),
        ("Origen DSA", _texto_origen(registro)),
        ("Vista seleccionada", _primer_texto(duracion, defecto="Tramo actual")),
        ("Intervalo mostrado", f"{_formatear_fecha(inicio)} - {_formatear_fecha(fin)}"),
        (
            "Informacion ICCA",
            "Disponible" if registro.get("icca") is not None else "No disponible",
        ),
    ]


def nombre_archivo_informe(registro, inicio, fin):
    """
    Ejecuta la lógica asociada a nombre archivo informe.

    Parámetros
    ----------
    registro : Any
        Datos del registro que se va a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    sesion = registro.get("sesion_paciente") or {}
    sesion_nombre = _primer_texto(
        sesion.get("nombre_carpeta"),
        sesion.get("sesion_bis_id"),
        registro.get("sesion_bis_id"),
        defecto="sin_sesion",
    )
    partes = ["Informe_BIS_ICCA_sesion", sesion_nombre]
    nombre = "_".join(_limpiar_nombre_archivo(parte) for parte in partes)
    return f"{nombre}.pdf"


def _limpiar_nombre_archivo(texto):
    """
    Ejecuta la lógica asociada a limpiar nombre archivo.

    Parámetros
    ----------
    texto : Any
        Texto que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    texto = re.sub(r"[^A-Za-z0-9_-]+", "_", str(texto).strip())
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto or "sin_nombre"


def _pagina_portada(pdf, registro, inicio, fin, duracion):
    """
    Ejecuta la lógica asociada a pagina portada.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    registro : Any
        Datos del registro que se va a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    duracion : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    fig = Figure(figsize=A4_VERTICAL, dpi=150)
    fig.patch.set_facecolor("white")
    fig.text(0.11, 0.90, "Visualizador BIS-ICCA", fontsize=22, weight="bold", color=AZUL)
    fig.text(
        0.11,
        0.855,
        "Informe del intervalo exportado",
        fontsize=10.5,
        color=GRIS_TEXTO,
    )
    fig.text(0.11, 0.80, "Datos principales", fontsize=13, weight="bold", color=AZUL)

    datos = _datos_basicos(registro, inicio, fin, duracion)
    y = 0.755
    for etiqueta, valor in datos:
        fig.text(0.13, y, etiqueta, fontsize=9.2, weight="bold", color=AZUL)
        fig.text(0.36, y, valor, fontsize=9.2, color=GRIS_TEXTO)
        y -= 0.039

    sesion = registro.get("sesion_paciente") or {}
    ruta_bis = _primer_texto(
        sesion.get("carpeta_bis_absoluta"),
        sesion.get("carpeta_bis"),
        defecto="",
    )
    ruta_icca = _primer_texto(
        sesion.get("icca_auxiliar_absoluto"),
        sesion.get("excel_icca_auxiliar"),
        defecto="",
    )
    fig.text(0.11, 0.39, "Fuentes", fontsize=13, weight="bold", color=AZUL)
    y = 0.355
    if ruta_bis:
        fig.text(0.13, y, "Carpeta BIS", fontsize=8.8, weight="bold", color=AZUL)
        y = _texto_en_figura(fig, 0.32, y, ruta_bis, width=70, fontsize=7.8, line_height=0.015)
        y -= 0.018
    if ruta_icca:
        fig.text(0.13, y, "ICCA auxiliar", fontsize=8.8, weight="bold", color=AZUL)
        _texto_en_figura(fig, 0.32, y, ruta_icca, width=70, fontsize=7.8, line_height=0.015)

    _texto_en_figura(
        fig,
        0.11,
        0.055,
        "Documento generado automaticamente desde la aplicacion BIS-ICCA. No sustituye la valoracion clinica ni la revision de los registros originales.",
        width=110,
        fontsize=7.8,
        color="#607080",
        line_height=0.015,
    )
    _guardar_pagina(pdf, fig)


def _imagen_desde_data_url(data_url):
    """
    Ejecuta la lógica asociada a imagen desde data url.

    Parámetros
    ----------
    data_url : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    _, contenido = data_url.split(",", 1)
    datos = base64.b64decode(contenido)
    return Image.open(io.BytesIO(datos)).convert("RGB")


def _pagina_dsa(pdf, vista, inicio, fin):
    """
    Ejecuta la lógica asociada a pagina dsa.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    vista : Any
        Valor de entrada utilizado por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    imagen = _imagen_desde_data_url(crear_panoramica_estatica(vista))
    fig = Figure(figsize=A4_HORIZONTAL, dpi=150)
    fig.patch.set_facecolor("white")
    fig.text(
        0.04,
        0.955,
        "DSA - Matriz de Densidad Espectral",
        fontsize=15,
        weight="bold",
        color=AZUL,
    )
    fig.text(
        0.04,
        0.925,
        f"{_formatear_fecha(inicio)} - {_formatear_fecha(fin)}",
        fontsize=9.5,
        color=GRIS_TEXTO,
    )
    ax = fig.add_axes([0.04, 0.05, 0.92, 0.84])
    ax.imshow(imagen)
    ax.axis("off")
    _guardar_pagina(pdf, fig)


def _agrupar_series_icca(metadata):
    """
    Agrupa series icca.

    Parámetros
    ----------
    metadata : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    grupos = []
    orden = [
        "fc",
        "presion_arterial",
        "spo2",
        "pic",
        "frecuencia_respiratoria",
        "temperatura",
    ]
    for variable in orden:
        if variable == "presion_arterial":
            filas = metadata[
                metadata["variable"].isin(["pa_sistolica", "pa_diastolica", "pa_media"])
            ]
        else:
            filas = metadata[metadata["variable"] == variable]
        if not filas.empty:
            grupos.append((variable, filas))
    return grupos


def _tramo_documentado_constante(mediciones, columna_valor, inicio, fin):
    """
    Ejecuta la lógica asociada a tramo documentado constante.

    Parámetros
    ----------
    mediciones : Any
        Valor de entrada utilizado por la función.

    columna_valor : Any
        Valor de entrada utilizado por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    mediciones = mediciones.sort_values("timestamp", kind="stable")
    anteriores = mediciones[mediciones["timestamp"] < inicio].tail(1)
    dentro = mediciones[mediciones["timestamp"].between(inicio, fin, inclusive="both")]
    puntos = []
    if not anteriores.empty:
        puntos.append(
            {
                "timestamp": pd.Timestamp(inicio),
                columna_valor: anteriores.iloc[0][columna_valor],
            }
        )
    puntos.extend(dentro[["timestamp", columna_valor]].to_dict("records"))
    if not puntos:
        return pd.DataFrame(columns=["timestamp", columna_valor]), dentro
    ultimo = puntos[-1]
    if pd.Timestamp(ultimo["timestamp"]) < pd.Timestamp(fin):
        puntos.append(
            {
                "timestamp": pd.Timestamp(fin),
                columna_valor: ultimo[columna_valor],
            }
        )
    return pd.DataFrame(puntos), dentro


def _pagina_mensaje_horizontal(pdf, titulo, mensaje):
    """
    Ejecuta la lógica asociada a pagina mensaje horizontal.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    titulo : Any
        Valor de entrada utilizado por la función.

    mensaje : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    fig = Figure(figsize=A4_HORIZONTAL, dpi=150)
    fig.patch.set_facecolor("white")
    fig.text(0.055, 0.91, titulo, fontsize=17, weight="bold", color=AZUL)
    fig.text(0.055, 0.83, mensaje, fontsize=11, color=GRIS_TEXTO)
    _guardar_pagina(pdf, fig)


def _pagina_constantes(pdf, datos, inicio, fin):
    """
    Ejecuta la lógica asociada a pagina constantes.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    if not datos:
        return
    constantes = datos.get("constantes")
    metadata = datos.get("series")
    if constantes is None or metadata is None or constantes.empty or metadata.empty:
        return

    grupos = _agrupar_series_icca(metadata)
    if not grupos:
        return

    inicio = pd.Timestamp(inicio)
    fin = pd.Timestamp(fin)
    por_pagina = 3
    for inicio_grupo in range(0, len(grupos), por_pagina):
        grupos_pagina = grupos[inicio_grupo : inicio_grupo + por_pagina]
        fig = Figure(figsize=A4_HORIZONTAL, dpi=150)
        fig.patch.set_facecolor("white")
        fig.text(0.065, 0.93, "Constantes vitales ICCA", fontsize=16, weight="bold", color=AZUL)

        ejes = fig.subplots(
            nrows=len(grupos_pagina),
            ncols=1,
            sharex=True,
            gridspec_kw={
            "top": 0.84,
            "bottom": 0.13,
            "left": 0.115,
            "right": 0.80,
            "hspace": 0.55,
        },
        )
        if len(grupos_pagina) == 1:
            ejes = [ejes]

        for ax, (variable, filas_metadata) in zip(ejes, grupos_pagina):
            valores = []
            for _, metadata_serie in filas_metadata.iterrows():
                clave = metadata_serie.get("serie")
                if not clave:
                    continue
                variable_serie = metadata_serie.get("variable")
                columna_valor = f"{clave}__valor"
                mediciones = _mediciones_reales_constante(constantes, clave, columna_valor)
                linea, reales_dentro = _tramo_documentado_constante(
                    mediciones,
                    columna_valor,
                    inicio,
                    fin,
                )
                color = COLORES_VARIABLES.get(variable_serie, "#1f77b4")
                nombre = NOMBRES_VARIABLES.get(str(variable_serie), str(variable_serie or clave))
                if not linea.empty and len(linea) > 1:
                    valores.extend(linea[columna_valor].dropna().tolist())
                    ax.step(
                        linea["timestamp"],
                        linea[columna_valor],
                        where="post",
                        linewidth=1.7,
                        color=color,
                        label=nombre,
                    )
                if not reales_dentro.empty:
                    valores.extend(reales_dentro[columna_valor].dropna().tolist())
                    ax.scatter(
                        reales_dentro["timestamp"],
                        reales_dentro[columna_valor],
                        s=20,
                        color=color,
                        edgecolors="#1f2d3a",
                        linewidths=0.45,
                        zorder=3,
                    )

            unidad = next(
                (str(valor) for valor in filas_metadata.get("unidad", []) if pd.notna(valor)),
                "",
            )
            ax.set_title(NOMBRES_VARIABLES.get(variable, variable), fontsize=10, color=AZUL, pad=8)
            ax.set_ylabel(unidad, fontsize=8.3, labelpad=20, color=AZUL)
            ax.set_xlim(inicio, fin)
            rango = _rango_y_con_margen(valores)
            if rango:
                ax.set_ylim(*rango)
            ax.grid(True, color="#e1e8ef", linewidth=0.7)
            ax.tick_params(axis="both", labelsize=8, colors="#20384f")
            for borde in ["top", "right"]:
                ax.spines[borde].set_visible(False)
            ax.spines["left"].set_color("#8ea3b7")
            ax.spines["bottom"].set_color("#8ea3b7")
            if ax.lines:
                ax.legend(
                    loc="center left",
                    bbox_to_anchor=(1.01, 0.5),
                    fontsize=7.2,
                    frameon=False,
                    borderaxespad=0.0,
                )

        _formatear_eje_tiempo(ejes[-1])
        ejes[-1].set_xlabel("Tiempo", fontsize=9, color=AZUL)
        _guardar_pagina(pdf, fig)


def _normalizar_variable(valor):
    """
    Normaliza variable.

    Parámetros
    ----------
    valor : Any
        Valor que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    texto = str(valor or "").casefold()
    traduccion = str.maketrans("áéíóúüñ", "aeiouun")
    return "_".join(texto.translate(traduccion).replace("-", " ").split())


def _filtrar_analisis_para_tarjetas(datos, inicio, fin):
    """
    Filtra analisis para tarjetas.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    analisis = _filtrar_intervalo(datos.get("analisis"), inicio, fin)
    if analisis.empty or "variable" not in analisis:
        return pd.DataFrame()
    analisis = analisis.copy()
    analisis["_variable_normalizada"] = analisis["variable"].map(_normalizar_variable)
    analisis["_valor_presente"] = (
        analisis["valor"].notna()
        & analisis["valor"].astype(str).str.strip().ne("")
        if "valor" in analisis
        else False
    )
    return (
        analisis.sort_values(
            ["timestamp", "_variable_normalizada", "_valor_presente"],
            ascending=[True, True, False],
            kind="stable",
        )
        .drop_duplicates(subset=["timestamp", "_variable_normalizada"], keep="first")
        .sort_values("timestamp", kind="stable")
    )


def _dibujar_tarjeta(fig, x, y, w, h, titulo, subtitulo, lineas):
    """
    Dibuja tarjeta.

    Parámetros
    ----------
    fig : Any
        Figura que se va a modificar.

    x : Any
        Valor de entrada utilizado por la función.

    y : Any
        Valor de entrada utilizado por la función.

    w : Any
        Valor de entrada utilizado por la función.

    h : Any
        Valor de entrada utilizado por la función.

    titulo : Any
        Valor de entrada utilizado por la función.

    subtitulo : Any
        Valor de entrada utilizado por la función.

    lineas : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    tarjeta = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        transform=fig.transFigure,
        facecolor="#f9fbfc",
        edgecolor=BORDE,
        linewidth=1.0,
    )
    fig.patches.append(tarjeta)
    fig.text(x + 0.018, y + h - 0.038, titulo, fontsize=8.4, color="#526170")
    fig.text(x + 0.018, y + h - 0.068, subtitulo, fontsize=10, weight="bold", color=AZUL)
    yy = y + h - 0.105
    for linea in lineas[:6]:
        yy = _texto_en_figura(fig, x + 0.018, yy, linea, width=34, fontsize=8.2, line_height=0.019)
        yy -= 0.004
    if len(lineas) > 6:
        fig.text(x + 0.018, y + 0.025, f"+ {len(lineas) - 6} medicion(es) mas", fontsize=8, color="#607080")


def _aviso_analisis(fila):
    """
    Ejecuta la lógica asociada a aviso analisis.

    Parámetros
    ----------
    fila : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    for columna in ("aviso", "interpretacion", "comentario"):
        valor = fila.get(columna)
        if pd.notna(valor) and str(valor).strip():
            return str(valor).strip()
    marca = fila.get("marca_original")
    fuera_rango = fila.get("fuera_rango_uci")
    if (pd.notna(marca) and str(marca).strip()) or fuera_rango is True:
        return "Fuera del intervalo de referencia"
    return ""


def _pagina_tarjetas_analisis(pdf, datos, inicio, fin):
    """
    Ejecuta la lógica asociada a pagina tarjetas analisis.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    if not datos:
        return
    analisis = _filtrar_analisis_para_tarjetas(datos, inicio, fin)
    if analisis.empty:
        return

    filas_tabla = []
    for _, fila in analisis.iterrows():
        valor = fila.get("valor")
        if pd.isna(valor):
            continue
        unidad = _primer_texto(fila.get("unidad"), defecto="")
        filas_tabla.append(
            [
                pd.Timestamp(fila["timestamp"]).strftime("%d/%m/%Y %H:%M:%S"),
                _primer_texto(fila.get("variable"), defecto="Variable"),
                _formatear_numero(valor),
                unidad,
                _aviso_analisis(fila),
            ]
        )
    if not filas_tabla:
        return

    columnas = ["Fecha y hora", "Variable", "Valor", "Unidad", "Aviso"]
    por_pagina = 24
    for inicio_pagina in range(0, len(filas_tabla), por_pagina):
        filas = filas_tabla[inicio_pagina : inicio_pagina + por_pagina]
        fig = Figure(figsize=A4_HORIZONTAL, dpi=150)
        fig.patch.set_facecolor("white")
        fig.text(0.065, 0.93, "Analisis clinicos ICCA", fontsize=16, weight="bold", color=AZUL)
        fig.text(
            0.065,
            0.902,
            f"Registros desde {_formatear_fecha(inicio)} hasta {_formatear_fecha(fin)}",
            fontsize=8.8,
            color=GRIS_TEXTO,
        )
        ax = fig.add_axes([0.055, 0.07, 0.89, 0.79])
        ax.axis("off")
        tabla = ax.table(
            cellText=filas,
            colLabels=columnas,
            loc="upper left",
            cellLoc="left",
            colLoc="left",
            colWidths=[0.19, 0.28, 0.10, 0.10, 0.33],
        )
        tabla.auto_set_font_size(False)
        tabla.set_fontsize(7.8)
        tabla.scale(1.0, 1.25)
        for (fila_idx, _col_idx), celda in tabla.get_celld().items():
            celda.set_edgecolor("#d8e0e8")
            celda.set_linewidth(0.45)
            if fila_idx == 0:
                celda.set_facecolor("#eef3f7")
                celda.get_text().set_weight("bold")
                celda.get_text().set_color(AZUL)
            else:
                celda.set_facecolor("white")
                celda.get_text().set_color(GRIS_TEXTO)
        _guardar_pagina(pdf, fig)


def _preparar_curva_perfusion(grupo, inicio, fin):
    """
    Prepara curva perfusion.

    Parámetros
    ----------
    grupo : Any
        Valor de entrada utilizado por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    grupo = grupo.sort_values("timestamp", kind="stable").copy()
    grupo = grupo[grupo["dosis_actual"].notna()].copy()
    if grupo.empty:
        return pd.DataFrame(), pd.DataFrame(), ""

    unidades = grupo.get("unidad_dosis", pd.Series(dtype=object)).dropna().astype(str).str.strip()
    unidades = unidades[unidades != ""]
    if unidades.empty:
        return pd.DataFrame(), pd.DataFrame(), ""
    unidad = unidades.iloc[0]
    grupo = grupo[grupo["unidad_dosis"].fillna("").astype(str).str.strip().eq(unidad)].copy()

    eventos = grupo[(grupo["timestamp"] <= fin) & grupo["dosis_actual"].notna()].copy()
    if eventos.empty:
        return pd.DataFrame(), pd.DataFrame(), unidad

    eventos_previos = eventos[eventos["timestamp"] <= inicio]
    eventos_visibles = eventos[eventos["timestamp"] > inicio]
    puntos = []
    marcados = []

    def anadir_punto(instante, valor):
        """
        Ejecuta la lógica asociada a añadir punto.

        Parámetros
        ----------
        instante : Any
            Valor de entrada utilizado por la función.

        valor : Any
            Valor que se va a procesar.

        Devuelve
        --------
        None
            La función no devuelve ningún valor.
        """
        instante = pd.Timestamp(instante)
        if inicio <= instante <= fin:
            puntos.append({"timestamp": instante, "dosis": float(valor)})

    if not eventos_previos.empty:
        anadir_punto(inicio, eventos_previos["dosis_actual"].iloc[-1])
        marcados.extend(eventos_previos[eventos_previos["timestamp"] == inicio].to_dict("records"))

    for _, fila in eventos_visibles.iterrows():
        anadir_punto(fila["timestamp"], fila["dosis_actual"])
        if inicio <= pd.Timestamp(fila["timestamp"]) <= fin:
            marcados.append(fila.to_dict())

    if puntos and pd.Timestamp(puntos[-1]["timestamp"]) < fin:
        anadir_punto(fin, puntos[-1]["dosis"])

    curva = pd.DataFrame(puntos)
    if curva.empty or curva["dosis"].notna().sum() < 2:
        return pd.DataFrame(), pd.DataFrame(marcados), unidad
    eventos_pdf = pd.DataFrame(marcados)
    if not eventos_pdf.empty:
        eventos_pdf["dosis_evento"] = pd.to_numeric(eventos_pdf["dosis_actual"], errors="coerce")
    return curva, eventos_pdf, unidad


def _pagina_perfusiones(pdf, datos, inicio, fin):
    """
    Ejecuta la lógica asociada a pagina perfusiones.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    None
        La función no devuelve ningún valor.
    """
    if not datos:
        return
    perfusiones = datos.get("perfusiones")
    if perfusiones is None or perfusiones.empty or "timestamp" not in perfusiones or "farmaco" not in perfusiones:
        return

    inicio = pd.Timestamp(inicio)
    fin = pd.Timestamp(fin)
    trabajo = perfusiones.copy()
    trabajo["timestamp"] = pd.to_datetime(trabajo["timestamp"], errors="coerce")
    trabajo = trabajo.dropna(subset=["timestamp", "farmaco"])
    for columna in ["dosis_actual", "velocidad_bomba_ml_h"]:
        if columna not in trabajo:
            trabajo[columna] = pd.NA
        trabajo[columna] = pd.to_numeric(trabajo[columna], errors="coerce")
    if "unidad_dosis" not in trabajo:
        trabajo["unidad_dosis"] = ""
    trabajo = trabajo[trabajo["dosis_actual"].notna()].sort_values(["farmaco", "timestamp"], kind="stable")
    trabajo = trabajo.drop_duplicates(
        subset=["timestamp", "farmaco", "dosis_actual", "unidad_dosis", "velocidad_bomba_ml_h"],
        keep="last",
    )
    if trabajo.empty:
        return

    curvas = []
    for farmaco, grupo in trabajo.groupby("farmaco", sort=True):
        curva, eventos, unidad = _preparar_curva_perfusion(grupo, inicio, fin)
        if not curva.empty:
            curvas.append((str(farmaco), curva, eventos, unidad))
    if not curvas:
        return

    por_pagina = 3
    for inicio_curva in range(0, len(curvas), por_pagina):
        curvas_pagina = curvas[inicio_curva : inicio_curva + por_pagina]
        fig = Figure(figsize=A4_HORIZONTAL, dpi=150)
        fig.patch.set_facecolor("white")
        fig.text(0.065, 0.93, "Perfusiones ICCA", fontsize=16, weight="bold", color=AZUL)

        ejes = fig.subplots(
            nrows=len(curvas_pagina),
            ncols=1,
            sharex=True,
            gridspec_kw={
                "top": 0.84,
                "bottom": 0.13,
                "left": 0.13,
                "right": 0.93,
                "hspace": 0.58,
            },
        )
        if len(curvas_pagina) == 1:
            ejes = [ejes]

        for indice, (ax, (farmaco, curva, eventos, unidad)) in enumerate(zip(ejes, curvas_pagina)):
            color = COLORES_PERFUSIONES[(inicio_curva + indice) % len(COLORES_PERFUSIONES)]
            ax.step(curva["timestamp"], curva["dosis"], where="post", linewidth=1.9, color=color)
            if not eventos.empty:
                ax.scatter(
                    eventos["timestamp"],
                    eventos["dosis_evento"],
                    s=24,
                    color=color,
                    edgecolors="#1f2d3a",
                    linewidths=0.6,
                    zorder=3,
                )
            valores = curva["dosis"].dropna().tolist()
            rango = _rango_y_con_margen(valores)
            if rango:
                ax.set_ylim(*rango)
            ax.set_xlim(inicio, fin)
            ax.set_title(farmaco, fontsize=10, color=AZUL, pad=8)
            ax.set_ylabel(unidad or "Dosis", fontsize=8.3, labelpad=20, color=AZUL)
            ax.grid(True, color="#e1e8ef", linewidth=0.7)
            ax.tick_params(axis="both", labelsize=8, colors="#20384f")
            for borde in ["top", "right"]:
                ax.spines[borde].set_visible(False)
            ax.spines["left"].set_color("#8ea3b7")
            ax.spines["bottom"].set_color("#8ea3b7")

        _formatear_eje_tiempo(ejes[-1])
        ejes[-1].set_xlabel("Tiempo", fontsize=9, color=AZUL)
        _guardar_pagina(pdf, fig)


def _filtrar_intervalo(tabla, inicio, fin):
    """
    Filtra intervalo.

    Parámetros
    ----------
    tabla : Any
        Valor de entrada utilizado por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if tabla is None or tabla.empty or "timestamp" not in tabla:
        return pd.DataFrame()
    trabajo = tabla.copy()
    trabajo["timestamp"] = pd.to_datetime(trabajo["timestamp"], errors="coerce")
    return trabajo[
        trabajo["timestamp"].between(pd.Timestamp(inicio), pd.Timestamp(fin), inclusive="both")
    ].copy()


def _mediciones_reales_constante(constantes, clave, columna_valor):
    """
    Ejecuta la lógica asociada a mediciones reales constante.

    Parámetros
    ----------
    constantes : Any
        Valor de entrada utilizado por la función.

    clave : Any
        Valor de entrada utilizado por la función.

    columna_valor : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if constantes is None or constantes.empty:
        return pd.DataFrame(columns=["timestamp", columna_valor])
    if columna_valor not in constantes.columns or "timestamp" not in constantes.columns:
        return pd.DataFrame(columns=["timestamp", columna_valor])
    trabajo = constantes.copy()
    trabajo["timestamp"] = pd.to_datetime(trabajo["timestamp"], errors="coerce")
    validos = trabajo[columna_valor].notna()
    if "series_reales" in trabajo.columns:
        validos = validos & (
            trabajo["series_reales"]
            .fillna("")
            .astype(str)
            .str.split(";")
            .map(lambda series: clave in series)
        )
    return (
        trabajo.loc[validos, ["timestamp", columna_valor]]
        .dropna(subset=["timestamp", columna_valor])
        .sort_values("timestamp", kind="stable")
        .drop_duplicates(subset=["timestamp"], keep="last")
    )


def _lineas_constantes(datos, inicio, fin):
    """
    Ejecuta la lógica asociada a lineas constantes.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    constantes = datos.get("constantes")
    metadata = datos.get("series")
    if constantes is None or metadata is None or constantes.empty or metadata.empty:
        return [("Sin constantes vitales documentadas en este intervalo.", "normal")]

    lineas = []
    for _, serie in metadata.iterrows():
        clave = serie.get("serie")
        if not clave:
            continue
        columna_valor = f"{clave}__valor"
        mediciones = _mediciones_reales_constante(constantes, clave, columna_valor)
        tramo = _filtrar_intervalo(mediciones, inicio, fin)
        if tramo.empty:
            continue
        ultima = tramo.iloc[-1]
        variable = serie.get("variable")
        nombre = NOMBRES_VARIABLES.get(str(variable), str(variable or clave))
        unidad = _primer_texto(serie.get("unidad"), defecto="")
        sufijo = f" {unidad}" if unidad else ""
        lineas.append(
            (
                f"- {nombre}: {len(tramo)} medicion(es); ultimo valor "
                f"{_formatear_numero(ultima[columna_valor])}{sufijo} "
                f"({_formatear_fecha(ultima['timestamp'])}).",
                "normal",
            )
        )
    return lineas or [("Sin constantes vitales documentadas en este intervalo.", "normal")]


def _lineas_analisis(datos, inicio, fin):
    """
    Ejecuta la lógica asociada a lineas analisis.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    analisis = _filtrar_intervalo(datos.get("analisis"), inicio, fin)
    if analisis.empty:
        return [("Sin analisis clinicos documentados en este intervalo.", "normal")]
    if "variable" not in analisis:
        return [("Sin analisis clinicos documentados en este intervalo.", "normal")]

    analisis = analisis.sort_values("timestamp", kind="stable")
    lineas = []
    max_lineas = 32
    for _, fila in analisis.head(max_lineas).iterrows():
        valor = fila.get("valor")
        if pd.isna(valor):
            continue
        unidad = _primer_texto(fila.get("unidad"), defecto="")
        sufijo = f" {unidad}" if unidad else ""
        lineas.append(
            (
                f"- {_formatear_fecha(fila['timestamp'])}: "
                f"{_primer_texto(fila.get('variable'), defecto='Variable')} "
                f"{_formatear_numero(valor)}{sufijo}.",
                "normal",
            )
        )
    restantes = len(analisis) - max_lineas
    if restantes > 0:
        lineas.append((f"- {restantes} medicion(es) mas no incluidas en el resumen.", "normal"))
    return lineas or [("Sin analisis clinicos documentados en este intervalo.", "normal")]


def _lineas_perfusiones(datos, inicio, fin):
    """
    Ejecuta la lógica asociada a lineas perfusiones.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    perfusiones = datos.get("perfusiones")
    if perfusiones is None or perfusiones.empty or "farmaco" not in perfusiones:
        return [("Sin perfusiones documentadas en este intervalo.", "normal")]

    perfusiones = perfusiones.copy()
    perfusiones["timestamp"] = pd.to_datetime(perfusiones["timestamp"], errors="coerce")
    for columna in ["dosis_actual", "velocidad_bomba_ml_h"]:
        if columna not in perfusiones:
            perfusiones[columna] = pd.NA
        perfusiones[columna] = pd.to_numeric(perfusiones[columna], errors="coerce")

    perfusiones = perfusiones[
        perfusiones["timestamp"].notna()
        & perfusiones["timestamp"].le(pd.Timestamp(fin))
    ].copy()
    perfusiones = perfusiones.dropna(subset=["farmaco"]).sort_values(
        ["farmaco", "timestamp"],
        kind="stable",
    )
    lineas = []
    for farmaco, grupo in perfusiones.groupby("farmaco", sort=True):
        grupo_dosis = grupo[grupo["dosis_actual"].notna()]
        if grupo_dosis.empty:
            continue
        ultima = grupo_dosis.iloc[-1]
        cambios_intervalo = grupo_dosis[
            grupo_dosis["timestamp"].between(
                pd.Timestamp(inicio),
                pd.Timestamp(fin),
                inclusive="both",
            )
        ]
        unidad = _primer_texto(ultima.get("unidad_dosis"), defecto="")
        sufijo = f" {unidad}" if unidad else ""
        texto = (
            f"- {farmaco}: dosis activa "
            f"{_formatear_numero(ultima['dosis_actual'])}{sufijo} "
            f"desde {_formatear_fecha(ultima['timestamp'])}; "
            f"{len(cambios_intervalo)} cambio(s) documentado(s) dentro del intervalo"
        )
        if pd.notna(ultima.get("velocidad_bomba_ml_h")):
            texto += f"; bomba {_formatear_numero(ultima['velocidad_bomba_ml_h'])} mL/h"
        lineas.append((texto + ".", "normal"))
    return lineas or [("Sin perfusiones con dosis documentada en este intervalo.", "normal")]


def _lineas_icca(datos, inicio, fin):
    """
    Ejecuta la lógica asociada a lineas icca.

    Parámetros
    ----------
    datos : Any
        Datos de entrada que se van a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    if not datos:
        return [("No hay informacion ICCA disponible para esta sesion.", "normal")]

    lineas = []
    peso = datos.get("peso_kg")
    if peso is not None:
        lineas.append((f"Peso inicial registrado: {_formatear_numero(peso)} kg.", "normal"))
        lineas.append(("", "normal"))

    lineas.append(("Constantes vitales", "section"))
    lineas.extend(_lineas_constantes(datos, inicio, fin))
    lineas.append(("", "normal"))
    lineas.append(("Analisis clinicos", "section"))
    lineas.extend(_lineas_analisis(datos, inicio, fin))
    lineas.append(("", "normal"))
    lineas.append(("Perfusiones", "section"))
    lineas.extend(_lineas_perfusiones(datos, inicio, fin))
    return lineas


def _lineas_fuentes(registro):
    """
    Ejecuta la lógica asociada a lineas fuentes.

    Parámetros
    ----------
    registro : Any
        Datos del registro que se va a procesar.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    sesion = registro.get("sesion_paciente") or {}
    ruta_bis = _primer_texto(sesion.get("carpeta_bis_absoluta"), sesion.get("carpeta_bis"), defecto="")
    ruta_icca = _primer_texto(
        sesion.get("icca_auxiliar_absoluto"),
        sesion.get("excel_icca_auxiliar"),
        defecto="",
    )
    lineas = []
    if ruta_bis:
        lineas.append((f"Carpeta BIS: {ruta_bis}", "small"))
    if ruta_icca:
        lineas.append((f"Excel ICCA auxiliar: {ruta_icca}", "small"))
    return lineas or [("No se han registrado rutas de origen para esta sesion.", "small")]


def _lineas_resumen_final(registro, inicio, fin, duracion):
    """
    Ejecuta la lógica asociada a lineas resumen final.

    Parámetros
    ----------
    registro : Any
        Datos del registro que se va a procesar.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    duracion : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    lineas = [
        ("Resumen del caso", "section"),
    ]
    for etiqueta, valor in _datos_basicos(registro, inicio, fin, duracion):
        lineas.append((f"{etiqueta}: {valor}", "normal"))
    lineas.extend(
        [
            ("", "normal"),
            ("Fuentes", "section"),
            *_lineas_fuentes(registro),
            ("", "normal"),
            ("Resumen ICCA", "section"),
            *_lineas_icca(registro.get("icca"), inicio, fin),
        ]
    )
    return lineas


def _paginas_texto(pdf, titulo, lineas):
    """
    Ejecuta la lógica asociada a paginas texto.

    Parámetros
    ----------
    pdf : Any
        Documento PDF en construcción.

    titulo : Any
        Valor de entrada utilizado por la función.

    lineas : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    fig = None
    y = 0

    def nueva_pagina():
        """
        Ejecuta la lógica asociada a nueva pagina.

        Parámetros
        ----------
        Ninguno
            La función no recibe parámetros.

        Devuelve
        --------
        Any
            Resultado generado por la función.
        """
        nueva = Figure(figsize=A4_VERTICAL, dpi=150)
        nueva.patch.set_facecolor("#f6f9fc")
        nueva.patches.append(
            FancyBboxPatch(
                (0.065, 0.065),
                0.87,
                0.84,
                boxstyle="round,pad=0.014,rounding_size=0.018",
                transform=nueva.transFigure,
                facecolor="#ffffff",
                edgecolor=BORDE,
                linewidth=1.0,
            )
        )
        nueva.text(0.095, 0.935, titulo, fontsize=20, weight="bold", color=AZUL)
        nueva.text(
            0.095,
            0.905,
            "Informacion escrita del intervalo exportado.",
            fontsize=9,
            color="#607080",
        )
        return nueva, 0.855

    fig, y = nueva_pagina()
    for texto, estilo in lineas:
        if texto == "":
            y -= 0.012
            continue
        ancho = 76 if estilo == "small" else 82 if estilo == "normal" else 64
        fragmentos = textwrap.wrap(str(texto), width=ancho) or [""]
        alto = 0.023 * len(fragmentos) + (0.030 if estilo == "section" else 0.006)
        if y - alto < 0.115 or (estilo == "section" and y < 0.28):
            _guardar_pagina(pdf, fig)
            fig, y = nueva_pagina()
        if estilo == "section":
            fig.patches.append(
                FancyBboxPatch(
                    (0.09, y - 0.018),
                    0.79,
                    0.036,
                    boxstyle="round,pad=0.004,rounding_size=0.006",
                    transform=fig.transFigure,
                    facecolor=GRIS_CLARO,
                    edgecolor="#dce6ee",
                    linewidth=0.6,
                )
            )
        for indice, fragmento in enumerate(fragmentos):
            fig.text(
                0.11 if estilo == "section" else 0.115,
                y - indice * 0.023,
                fragmento,
                fontsize=10.5 if estilo == "section" else 7.8 if estilo == "small" else 8.8,
                weight="bold" if estilo == "section" else "normal",
                color=AZUL if estilo == "section" else GRIS_TEXTO,
            )
        y -= alto
    _texto_en_figura(
        fig,
        0.095,
        0.04,
        "Documento generado automaticamente desde la aplicacion BIS-ICCA. No sustituye la valoracion clinica ni la revision de los registros originales.",
        width=118,
        fontsize=7.5,
        color="#607080",
        line_height=0.014,
    )
    _guardar_pagina(pdf, fig)


def crear_informe_pdf(registro, vista, inicio, fin, duracion):
    """
    Crea informe pdf.

    Parámetros
    ----------
    registro : Any
        Datos del registro que se va a procesar.

    vista : Any
        Valor de entrada utilizado por la función.

    inicio : Any
        Instante inicial del intervalo.

    fin : Any
        Instante final del intervalo.

    duracion : Any
        Valor de entrada utilizado por la función.

    Devuelve
    --------
    Any
        Resultado generado por la función.
    """
    buffer = io.BytesIO()
    sesion = registro.get("sesion_paciente") or {}
    inicio_analisis = _primer_texto(sesion.get("inicio_bis"), defecto="")
    inicio_analisis = pd.Timestamp(inicio_analisis) if inicio_analisis else pd.Timestamp(inicio)
    with PdfPages(buffer) as pdf:
        _pagina_portada(pdf, registro, inicio, fin, duracion)
        _pagina_dsa(pdf, vista, inicio, fin)
        _pagina_constantes(pdf, registro.get("icca"), inicio, fin)
        _pagina_perfusiones(pdf, registro.get("icca"), inicio, fin)
        _pagina_tarjetas_analisis(pdf, registro.get("icca"), inicio_analisis, fin)
    return buffer.getvalue()
