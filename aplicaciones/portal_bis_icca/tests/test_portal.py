import unittest

from app import app


def _contiene_texto(componente, texto):
    if componente == texto:
        return True
    if isinstance(componente, (list, tuple)):
        return any(_contiene_texto(hijo, texto) for hijo in componente)
    if hasattr(componente, "children"):
        return _contiene_texto(componente.children, texto)
    return False


class PortalTest(unittest.TestCase):
    def test_endpoints_dash_responden(self):
        cliente = app.server.test_client()
        self.assertEqual(cliente.get("/_dash-layout").status_code, 200)
        self.assertEqual(cliente.get("/_dash-dependencies").status_code, 200)

    def test_muestra_ubicacion_de_pacientes(self):
        self.assertTrue(_contiene_texto(app.layout, "Ubicación de pacientes"))
        self.assertFalse(_contiene_texto(app.layout, "Repositorio comun"))


if __name__ == "__main__":
    unittest.main()
