import os

from dash import Dash, html


def _env_int(nombre, valor_por_defecto):
    """
    Busca una variable de entorno llamada nombre. 
     - intenta leer TFG_PORTAL_PORT
     - Si existe y es un número, por ejemplo 9000, devuelve "9000"
     - Si no existe o está mal escrita, usa el valor_por_defecto, por ejemplo 8040.

    puerto: el número que va después de los dos puntos en la URL
      - http://127.0.0.1:8040 ->  8040 = puerto
      - Portal → puerto 8040
      - Visualizador → puerto 8050
      - Organizador  → puerto 8060
    """
    try: 
        # os.environ: diccionario con variables de entorno del sistema
        return int(os.environ.get(nombre, valor_por_defecto))
    except (TypeError, ValueError):
        return valor_por_defecto


def _url(nombre, puerto_por_defecto):
    """
    Busca una variable de entorno llamada nombre con una URL configurada. 
     - Si existe, por ejemplo TFG_ORGANIZADOR_URL, devuelve la URL configurada
     - Si no existe, estando en local, inventa una URL local con 127.0.0.1 y el puerto por defecto (http://127.0.0.1:8060/).
    """
    return os.environ.get(nombre) or f"http://127.0.0.1:{puerto_por_defecto}/"


ORGANIZADOR_URL = _url("TFG_ORGANIZADOR_URL", 8060)
VISUALIZADOR_URL = _url("TFG_VISUALIZADOR_URL", 8050)
PACIENTES_DIR = os.environ.get("TFG_PACIENTES_DIR", "No configurado")
HOST_DASH = os.environ.get("TFG_DASH_HOST", "127.0.0.1")
PUERTO_PORTAL = _env_int("TFG_PORTAL_PORT", 8040)


# creación de la app Dash del portal
app = Dash(__name__)
app.title = "Sistema BIS-ICCA"


def _tarjeta(titulo, descripcion, enlace):
    """.
    Crea los botones grandes del portal
    ejemplo: _tarjeta("Visualizar paciente", 
                        "Consultar sesiones, DSA, reconstrucción e información ICCA.",
                        "http://127.0.0.1:8050/")

    Devuelve:
     - un bloque clicable
    
    html.A crea un enlace HTML
     - []: crea el contenido visual de la tarjeta
     - título en negrita
     - debajo va una descripción más pequeña
     - href=enlace: dice a dónde va cuando haces clic (el visualizador o el organizador)
     - className="tarjeta-accion": pone una clase CSS para que tenga aspecto de tarjeta/botón grande. Esa clase se diseña luego en el CSS. 
    """
    return html.A(
        [
            html.Strong(titulo),
            html.Span(descripcion),
        ],
        href=enlace,
        className="tarjeta-accion",
    )


# Definir la pantalla completa del portal. Lo que Dash va a enseñar en Chrome.
# app.layout: interfaz de la aplicación

app.layout = html.Main(
    # contenedor principal de la página. Toda la pantalla del portal va aquí.
    [
        html.Header(
            html.Div(
                [
                    html.H1("Portal de pacientes BIS-ICCA"),
                    html.P("Acceso principal a organización y visualización."),
                ],
                className="cabecera-contenido",
            ),
            className="cabecera-aplicacion",
        ),
        # bloque central del portal-> panel donde están los botones y la ruta.
        html.Section(
            [
                html.Div(
                    [
                        html.H2("Ubicación de pacientes"),
                        html.Div(
                            [
                                html.Strong("Ruta configurada"),
                                html.Code(PACIENTES_DIR),
                            ],
                            className="ruta-configurada",
                        ),
                    ],
                    className="ubicacion-pacientes",
                ),
                # crear las dos tarjetas grandes
                html.Div(
                    [
                        # botón que lleva al organizador
                        _tarjeta(
                            "Añadir / gestionar pacientes",
                            "Crear pacientes y asociar sesiones BIS con registros ICCA.",
                            ORGANIZADOR_URL,
                        ),
                        # botón que lleva al visualizador
                        _tarjeta(
                            "Visualizar paciente",
                            "Consultar sesiones, DSA, reconstrucción e información ICCA.",
                            VISUALIZADOR_URL,
                        ),
                    ],
                    className="acciones",
                ),
            ],
            className="panel",
        ),
    ],
    # pone una clase CSS al contenedor principal para poder darle estilo: centrarlo, poner fondo, márgenes, etc.
    className="pantalla",
)

# plantilla html que usa dash para envolver la aplicación
# app.layout indica qué hay y app.index_string indica cómo se monta la página y cómo se ve
app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
      :root {
        --azul: #1f4e78;
        --azul-oscuro: #16364f;
        --borde: #cbd7e2;
        --fondo: #f4f7fa;
        --texto: #1d2730;
      }
      * { box-sizing: border-box; }
      body { margin: 0; background: var(--fondo); color: var(--texto); font-family: Arial, sans-serif; }
      .pantalla { min-height: 100vh; background: var(--fondo); }
      .cabecera-aplicacion { background: var(--azul); color: white; padding: 24px 30px; }
      .cabecera-contenido { width: min(1250px, 100%); margin: 0 auto; }
      .cabecera-contenido h1 { margin: 0; font-size: clamp(1.8rem, 2.6vw, 2.25rem); }
      .cabecera-contenido p { margin: 12px 0 0; font-weight: 700; }
      .panel { width: min(1250px, 100%); margin: 0 auto; padding: 24px; display: grid; gap: 18px; }
      .ubicacion-pacientes { display: grid; gap: 16px; background: white; border: 1px solid var(--borde); border-radius: 10px; padding: 22px; }
      .ubicacion-pacientes h2 { margin: 0; font-size: 1.35rem; color: black; }
      .ruta-configurada { display: grid; gap: 6px; background: #f7f9fb; border: 1px solid var(--borde); border-radius: 8px; padding: 12px; }
      .ruta-configurada code { overflow-wrap: anywhere; color: #173b59; font-size: .85rem; line-height: 1.35; }
      .acciones { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 18px; }
      .tarjeta-accion { display: grid; align-content: center; gap: 10px; min-height: 150px; padding: 24px; border: 1px solid var(--borde); border-radius: 8px; background: white; color: inherit; text-decoration: none; }
      .tarjeta-accion:hover { border-color: var(--azul); box-shadow: 0 8px 22px rgba(31, 78, 120, .12); }
      .tarjeta-accion strong { color: var(--azul-oscuro); font-size: 1.16rem; }
      .tarjeta-accion span { color: #536170; line-height: 1.45; }
      @media (max-width: 760px) {
        .cabecera-aplicacion { padding: 22px 18px; }
        .panel { padding: 18px; }
        .acciones { grid-template-columns: 1fr; }
        .tarjeta-accion { min-height: 136px; }
      }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""


# Arranca la aplicación Dash cuando se ejecuta el archivo directamente.
if __name__ == "__main__":
    app.run(host=HOST_DASH, port=PUERTO_PORTAL, debug=False)

"""
Si ejecuto este archivo como programa principal,
arranca la aplicación Dash en el host y puerto configurados.

Pero si otro archivo importa este app.py para hacer tests, 
no lo arranca automáticamente.

app.run(...): Arranca el servidor web de Dash
host=HOST_DASH: Indica desde dónde se puede acceder.
 - HOST_DASH = "127.0.0.1": Solo se abre en tu propio ordenador
 - HOST_DASH = "0.0.0.0": Acepta conexiones desde otros ordenadores de la intranet.

port=PUERTO_PORTAL: indica el puerto
  - PUERTO_PORTAL = 8040: la URL sería http://127.0.0.1:8040/
"""
