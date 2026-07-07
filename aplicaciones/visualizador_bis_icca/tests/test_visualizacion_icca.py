import unittest

import pandas as pd

from src.visualizacion_icca import (
    CONFIGURACION_GRAFICO_ICCA,
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

        self.assertEqual(figura.layout.margin.l, 205)
        self.assertEqual(figura.layout.margin.r, 390)
        self.assertEqual(tuple(figura.layout.xaxis.range), (inicio, fin))
        self.assertEqual(figura.layout.legend.x, 1.03)
        lineas = [traza for traza in figura.data if traza.mode == "lines"]
        marcadores = [traza for traza in figura.data if traza.mode == "markers"]
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0].line.shape, "hv")
        self.assertEqual(len(marcadores), 1)
        self.assertEqual(len(marcadores[0].x), 2)
        self.assertEqual(marcadores[0].marker.size, 8)
        self.assertFalse(marcadores[0].cliponaxis)
        self.assertFalse(marcadores[0].showlegend)
        self.assertIn("Medición real", str(lineas[0].customdata[0]))
        self.assertNotIn("valor documentado", str(lineas[0].name))
        self.assertNotIn("Ventilatoria", str(lineas[0].name))
        self.assertEqual(marcadores[0].hoverinfo, "skip")
        self.assertNotIn("%{x|", lineas[0].hovertemplate)
        self.assertLess(figura.layout.yaxis.range[0], 70)
        self.assertGreater(figura.layout.yaxis.range[1], 72)

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

    def test_perfusiones_muestran_dosis_activa_escalonada(self):
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
        self.assertEqual(len(lineas), 1)
        self.assertEqual(pd.Timestamp(lineas[0].x[0]), inicio)
        self.assertEqual(pd.Timestamp(lineas[0].x[-1]), fin)
        self.assertIn("Dosis administrada (mg/h)", str(lineas[0].name))
        self.assertEqual(lineas[0].line.shape, "hv")
        self.assertEqual([float(valor) for valor in lineas[0].y], [5.0, 7.0, 6.0, 6.0])
        marcadores = [traza for traza in figura.data if traza.mode == "markers"]
        self.assertEqual(len(marcadores), 1)
        self.assertEqual(len(marcadores[0].x), 2)
        self.assertEqual(marcadores[0].marker.line.color, "#1f2d3a")
        self.assertFalse(marcadores[0].cliponaxis)
        self.assertEqual(lineas[0].hoverinfo, "skip")
        self.assertIsNone(lineas[0].hovertemplate)
        self.assertIn("Bomba documentada: 3.00 mL/h", str(marcadores[0].customdata[0]))
        self.assertIn("Dosis desde este instante: 7.00 mg/h", str(marcadores[0].customdata[0]))
        self.assertNotIn("Dosis activa:", str(marcadores[0].customdata[0]))
        self.assertNotIn("Registro real:", str(marcadores[0].customdata[0]))
        self.assertNotIn("2026", str(marcadores[0].customdata[0]))
        self.assertEqual(figura.layout.hovermode, "x unified")
        self.assertEqual(figura.layout.legend.orientation, "h")
        self.assertGreaterEqual(figura.layout.height, 520)
        self.assertFalse(CONFIGURACION_GRAFICO_ICCA["scrollZoom"])

    def test_perfusiones_sin_dosis_no_representan_solo_velocidad_de_bomba(self):
        inicio = pd.Timestamp("2026-04-30 19:00:00")
        fin = pd.Timestamp("2026-04-30 20:00:00")
        datos = {
            "perfusiones": pd.DataFrame(
                {
                    "timestamp": [
                        inicio,
                        inicio + pd.Timedelta(minutes=30),
                    ],
                    "farmaco": ["Noradrenalina"] * 2,
                    "dosis_actual": [None, None],
                    "unidad_dosis": ["mcg/kg/min"] * 2,
                    "velocidad_bomba_ml_h": [2.0, 3.0],
                }
            ),
        }

        figura = _crear_figura_perfusiones(datos, inicio, fin)

        self.assertIsNone(figura)

    def test_perfusiones_arrastran_ultima_dosis_previa_al_intervalo(self):
        inicio = pd.Timestamp("2026-04-30 10:00:00")
        fin = pd.Timestamp("2026-04-30 11:00:00")
        datos = {
            "perfusiones": pd.DataFrame(
                {
                    "timestamp": [
                        pd.Timestamp("2026-04-29 09:00:00"),
                        inicio + pd.Timedelta(minutes=15),
                    ],
                    "farmaco": ["Labetalol"] * 2,
                    "dosis_actual": [0.5, 0.5],
                    "unidad_dosis": ["mg/min"] * 2,
                    "velocidad_bomba_ml_h": [6.0, None],
                }
            ),
        }

        figura = _crear_figura_perfusiones(datos, inicio, fin)

        linea = next(traza for traza in figura.data if traza.mode == "lines")
        self.assertIn("Dosis administrada (mg/min)", str(linea.name))
        self.assertEqual([float(valor) for valor in linea.y], [0.5, 0.5, 0.5])

    def test_perfusiones_mantienen_cero_si_icca_documenta_suspension(self):
        inicio = pd.Timestamp("2026-04-30 07:50:00")
        fin = pd.Timestamp("2026-04-30 08:10:00")
        datos = {
            "perfusiones": pd.DataFrame(
                {
                    "timestamp": [inicio, pd.Timestamp("2026-04-30 08:00:00")],
                    "farmaco": ["Noradrenalina", "Noradrenalina"],
                    "dosis_actual": [0.05, 0.0],
                    "unidad_dosis": ["mcg/kg/min", "mcg/kg/min"],
                }
            )
        }

        figura = _crear_figura_perfusiones(datos, inicio, fin)

        linea = next(traza for traza in figura.data if traza.mode == "lines")
        self.assertEqual([float(valor) for valor in linea.y], [0.05, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
