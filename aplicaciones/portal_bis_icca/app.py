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
        # bloque central del portal-> panel donde están: el título, los botones y la ruta.
        html.Section(
            [
                # cabecera
                html.Div(
                    [
                        # html.P: párrafo pequeño
                        html.P("Sistema BIS-ICCA", className="marca"),
                        # html.H1: título grande.
                        html.H1("Portal de pacientes"),
                    ],
                    className="cabecera-texto",
                ),
                # crear las dos tarjetas grandes
                html.Div(
                    [
                        # botón que lleva al organizador
                        _tarjeta(
                            "Anadir / gestionar pacientes",
                            "Crear pacientes y asociar sesiones BIS con registros ICCA.",
                            ORGANIZADOR_URL,
                        ),
                        # botón que lleva al visualizador
                        _tarjeta(
                            "Visualizar paciente",
                            "Consultar sesiones, DSA, reconstruccion e informacion ICCA.",
                            VISUALIZADOR_URL,
                        ),
                    ],
                    className="acciones",
                ),
                # 
                html.Div(
                    [
                        html.Strong("Repositorio comun"),
                        html.Code(PACIENTES_DIR),
                    ],
                    className="repositorio",
                ),
            ],
            className="panel",
        )
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
      .pantalla { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
      .panel { width: min(980px, 100%); display: grid; gap: 24px; }
      .cabecera-texto { display: grid; gap: 6px; }
      .marca { margin: 0; color: var(--azul); font-weight: 700; text-transform: uppercase; font-size: .82rem; }
      h1 { margin: 0; color: var(--azul-oscuro); font-size: 2rem; }
      .acciones { display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 16px; }
      .tarjeta-accion { display: grid; gap: 8px; min-height: 132px; padding: 22px; border: 1px solid var(--borde); border-radius: 8px; background: white; color: inherit; text-decoration: none; }
      .tarjeta-accion:hover { border-color: var(--azul); box-shadow: 0 8px 22px rgba(31, 78, 120, .12); }
      .tarjeta-accion strong { color: var(--azul-oscuro); font-size: 1.08rem; }
      .tarjeta-accion span { color: #536170; line-height: 1.45; }
      .repositorio { display: grid; gap: 7px; padding: 14px 16px; border: 1px solid var(--borde); border-radius: 8px; background: white; }
      .repositorio code { overflow-wrap: anywhere; color: var(--azul-oscuro); }
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