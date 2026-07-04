import tempfile
import unittest
from pathlib import Path

from app import _tarjetas_seleccion, app, visualizar_paciente


def buscar_componente(componente, identificador):
    if getattr(componente, "id", None) == identificador:
        return componente
    hijos = getattr(componente, "children", None)
    if hijos is None:
        return None
    if not isinstance(hijos, (list, tuple)):
        hijos = [hijos]
    for hijo in hijos:
        encontrado = buscar_componente(hijo, identificador)
        if encontrado is not None:
            return encontrado
    return None


def _recorrer_componentes(componente):
    yield componente
    hijos = getattr(componente, "children", None)
    if hijos is None:
        return
    if not isinstance(hijos, (list, tuple)):
        hijos = [hijos]
    for hijo in hijos:
        yield from _recorrer_componentes(hijo)


class InterfazTest(unittest.TestCase):
    def test_layout_contiene_pestanas_y_selector_no_limpiable(self):
        pestanas = buscar_componente(app.layout, "pestanas")
        selector = buscar_componente(app.layout, "selector-paciente")
        edicion = next(
            componente
            for componente in _recorrer_componentes(app.layout)
            if getattr(componente, "className", None) == "desplegable-edicion"
        )

        self.assertIsNotNone(pestanas)
        self.assertEqual(pestanas.value, "nuevo")
        self.assertIsNotNone(selector)
        self.assertFalse(selector.clearable)
        self.assertFalse(bool(getattr(edicion, "open", False)))

    def test_cada_seleccion_tiene_su_boton_para_quitarla(self):
        ruta = r"C:\datos\ICCA_prueba.xlsx"
        tarjetas = _tarjetas_seleccion(
            [ruta],
            "quitar-icca",
            "Excel ICCA",
            "No hay Excel ICCA seleccionados.",
        )

        self.assertEqual(len(tarjetas), 1)
        boton = tarjetas[0].children[1]
        self.assertEqual(boton.id, {"type": "quitar-icca", "index": ruta})
        self.assertEqual(boton.children, "×")

    def test_sin_seleccion_no_afirma_que_falten_pacientes(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal) / "PACIENTE_001"
            carpeta.mkdir()
            (carpeta / "paciente.json").write_text(
                '{"paciente_id":"PACIENTE_001","carpeta":"",'
                '"creado":"2026-06-29 00:00:00","icca":[],"sesiones":[]}',
                encoding="utf-8",
            )

            resultado = visualizar_paciente(None, temporal, 0, 0)

        self.assertEqual(
            resultado.children,
            "Selecciona un paciente para consultar sus sesiones.",
        )

    def test_endpoints_dash_responden(self):
        cliente = app.server.test_client()
        self.assertEqual(cliente.get("/_dash-layout").status_code, 200)
        self.assertEqual(cliente.get("/_dash-dependencies").status_code, 200)


if __name__ == "__main__":
    unittest.main()
