import json
import unittest

import app


class SeleccionSesionTest(unittest.TestCase):
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
