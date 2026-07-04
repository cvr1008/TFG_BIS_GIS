import unittest

import pandas as pd

from src.visualizacion_icca import (
    _crear_figura_constantes,
    _crear_figura_perfusiones,
    _crear_tarjetas_analisis,
)


def _textos_componente(componente):
    if componente is None:
        return []
    if isinstance(componente, str):
        return [componente]
    if isinstance(componente, (list, tuple)):
        textos = []
        for hijo in componente:
            textos.extend(_textos_componente(hijo))
        return textos
    return _textos_componente(getattr(componente, "children", None))


class VisualizacionIccaTest(unittest.TestCase):
    def test_constantes_comparten_intervalo_y_margenes_con_dsa(self):
        inicio = pd.Timestamp("2026-04-30 19:00:00")
        fin = pd.Timestamp("2026-04-30 20:00:00")
        datos = {
            "constantes": pd.DataFrame(
                {
                    "timestamp": [inicio, fin],
                    "fc_ventilatoria__valor": [70.0, 72.0],
                    "series_reales": ["fc_ventilatoria", "fc_ventilatoria"],
                }
            ),
            "series": pd.DataFrame(
                {
                    "serie": ["fc_ventilatoria"],
                    "variable": ["fc"],
                    "fuente": ["Ventilatoria"],
                    "unidad": ["lpm"],
                }
            ),
        }

        figura = _crear_figura_constantes(datos, inicio, fin)

        self.assertEqual(figura.layout.margin.l, 170)
        self.assertEqual(figura.layout.margin.r, 390)
        self.assertEqual(tuple(figura.layout.xaxis.range), (inicio, fin))
        self.assertEqual(figura.layout.legend.x, 1.03)

    def test_misma_variable_y_timestamp_se_muestra_una_sola_vez(self):
        instante = pd.Timestamp("2026-04-30 19:50:00")
        datos = {
            "analisis": pd.DataFrame(
                {
                    "timestamp": [instante, instante, instante, instante],
                    "variable": ["Hemoglobina", "Hemoglobina", "Sodio", "Sodio"],
                    "valor": [10.6, 10.6, None, 138.0],
                    "unidad": ["g/dL", "g/dL", "mEq/L", "mEq/L"],
                }
            )
        }

        componente = _crear_tarjetas_analisis(
            datos,
            instante - pd.Timedelta(minutes=1),
            instante + pd.Timedelta(minutes=1),
        )
        textos = _textos_componente(componente)

        self.assertEqual(textos.count("Hemoglobina"), 1)
        self.assertEqual(textos.count("Sodio"), 1)
        self.assertTrue(any("138 mEq/L" in texto for texto in textos))

    def test_perfusiones_escalonadas_comparten_intervalo(self):
        inicio = pd.Timestamp("2026-04-30 19:00:00")
        fin = pd.Timestamp("2026-04-30 20:00:00")
        datos = {
            "perfusiones": pd.DataFrame(
                {
                    "timestamp": [
                        inicio - pd.Timedelta(minutes=10),
                        inicio + pd.Timedelta(minutes=15),
                        inicio + pd.Timedelta(minutes=40),
                    ],
                    "farmaco": ["Midazolam"] * 3,
                    "dosis_actual": [5.0, 7.0, 6.0],
                    "unidad_dosis": ["mg/h"] * 3,
                    "velocidad_bomba_ml_h": [2.0, 3.0, 2.5],
                }
            )
        }

        figura = _crear_figura_perfusiones(datos, inicio, fin)

        self.assertIsNotNone(figura)
        self.assertEqual(tuple(figura.layout.xaxis.range), (inicio, fin))
        lineas = [traza for traza in figura.data if traza.mode == "lines"]
        self.assertEqual(len(lineas), 3)
        acumulado = [
            traza
            for traza in lineas
            if "acumulado desde 08:00" in str(traza.name)
        ]
        self.assertEqual(len(acumulado), 1)
        escalonadas = [traza for traza in lineas if traza not in acumulado]
        self.assertTrue(all(traza.line.shape == "hv" for traza in escalonadas))
        self.assertEqual(pd.Timestamp(lineas[0].x[0]), inicio)
        self.assertEqual(pd.Timestamp(lineas[0].x[-1]), fin)
        self.assertEqual(acumulado[0].line.shape, "linear")


if __name__ == "__main__":
    unittest.main()
