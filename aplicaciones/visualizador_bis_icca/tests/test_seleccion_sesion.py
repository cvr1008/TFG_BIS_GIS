import json
import unittest

import app


def _contiene_texto(componente, texto):
    if componente == texto:
        return True
    if isinstance(componente, (list, tuple)):
        return any(_contiene_texto(hijo, texto) for hijo in componente)
    if hasattr(componente, "children"):
        return _contiene_texto(componente.children, texto)
    return False


class SeleccionSesionTest(unittest.TestCase):
    def test_rueda_raton_no_hace_zoom_en_graficas(self):
        self.assertFalse(app.CONFIGURACION_GRAFICO["scrollZoom"])

    def test_tarjeta_sesion_seleccionada_usa_clase_visual(self):
        tarjeta = app._crear_tarjeta_sesion(
            {"nombre_carpeta": "SESION_001", "sesion_bis_id": "L04301923"},
            seleccionada=True,
        )

        self.assertIn("tarjeta-sesion-seleccionada", tarjeta.className)

    def test_textos_principales_del_visualizador(self):
        self.assertTrue(_contiene_texto(app.app.layout, "Ubicación de pacientes"))
        self.assertTrue(_contiene_texto(app.app.layout, "BIS - ICCA"))
        self.assertFalse(_contiene_texto(app.app.layout, "Repositorio de pacientes"))

    def test_fondo_principal_del_visualizador_es_blanco(self):
        self.assertEqual(app.ESTILO_PANTALLA["backgroundColor"], "white")
        self.assertIn("body { margin: 0; background: #ffffff; }", app.app.index_string)

    def test_deteccion_de_sesion_no_contiene_referencia_circular(self):
        deteccion = {
            "base": "PRUEBA01",
            "modo": "unilateral",
            "origen_forzado": "fa",
            "origenes": ["fa"],
        }
        sesion = {
            "nombre_carpeta": "SESION_001_PRUEBA01",
            "deteccion_bis": deteccion,
            "icca_auxiliar_absoluto": "ICCA.xlsx",
        }

        resultado = app.analizar_carpeta(sesion)

        json.dumps(resultado[0])
        self.assertNotIn(
            "deteccion_bis",
            resultado[0]["sesion_paciente"],
        )
        self.assertNotIn("sesion_paciente", deteccion)


if __name__ == "__main__":
    unittest.main()
