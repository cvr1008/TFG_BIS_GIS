import unittest

import numpy as np
import pandas as pd

from src.figuras import (
    crear_figura_dsa_bilateral_interactiva,
    crear_figura_dsa_unilateral_interactiva,
)


class HoverExactoTest(unittest.TestCase):
    def _assert_cursor_vertical_compartido(self, figura, ejes_x):
        self.assertEqual(figura.layout.hovermode, "x unified")
        self.assertEqual(figura.layout.hoversubplots, "axis")
        for nombre_eje in ejes_x:
            eje = getattr(figura.layout, nombre_eje)
            self.assertTrue(eje.showspikes)
            self.assertEqual(eje.spikemode, "across")
            self.assertEqual(eje.spikesnap, "cursor")
            self.assertEqual(eje.spikedash, "dot")

    def test_no_sustituye_un_nan_por_el_valor_del_segundo_vecino(self):
        tiempo = pd.date_range("2026-05-14 13:30:12", periods=2, freq="s")
        frecuencias = np.arange(0.5, 30.5, 0.5)
        matriz = np.full((2, len(frecuencias)), 70.0)

        figura = crear_figura_dsa_bilateral_interactiva(
            tiempo=tiempo,
            frecuencias=frecuencias,
            matriz_izq=matriz,
            matriz_der=matriz,
            sef_izq=np.array([np.nan, 22.0]),
            mef_izq=np.array([np.nan, 7.5]),
            sef_der=np.array([17.5, 17.5]),
            mef_der=np.array([4.4, 4.4]),
            asimetria=np.array([np.nan, 58.9]),
            bis_izq=np.array([np.nan, 96.3]),
            bis_der=np.array([96.3, 96.7]),
            emg_izq=np.array([np.nan, 50.6]),
            emg_der=np.array([47.0, 47.1]),
            sr_izq=np.array([np.nan, 0.0]),
            sr_der=np.array([0.0, 0.0]),
        )

        textos_hover = [
            np.asarray(traza.customdata, dtype=object)
            for traza in figura.data
            if traza.customdata is not None
        ]
        primer_instante = [
            str(textos[0])
            for textos in textos_hover
        ]

        self.assertIn("BIS izquierda: Sin dato", primer_instante)
        self.assertIn("BIS derecha: 96.3", primer_instante)
        self.assertIn("SEF izquierda: Sin dato", primer_instante)
        self.assertIn("MEF izquierda: Sin dato", primer_instante)
        self.assertIn(
            "SR izquierda (últimos 63 s): Sin dato",
            primer_instante,
        )

        trazas_hover_dsa = [
            traza
            for traza in figura.data
            if traza.customdata is not None
            and str(traza.xaxis) == "x"
        ][:3]
        self.assertEqual(
            [
                (traza.marker.color, traza.marker.symbol)
                for traza in trazas_hover_dsa
            ],
            [
                ("white", "square"),
                ("#9c27b0", "square"),
                ("#e91e63", "circle"),
            ],
        )

        resumen = next(
            anotacion
            for anotacion in figura.layout.annotations
            if "Ratio alfa-delta izquierdo" in anotacion.text
        )
        titulos = [anotacion.text for anotacion in figura.layout.annotations]
        self.assertIn("Asimetría bilateral (ASYM09)", titulos)
        self.assertIn("Electromiograma frontal (EMGLOW01)", titulos)
        self.assertEqual(resumen.width, 235)
        self.assertEqual(resumen.borderpad, 14)
        self.assertEqual(resumen.x, 1.07)
        self.assertIn("ADR\xa0alfa/delta", resumen.text)
        self.assertNotIn("dB/Hz", resumen.text)
        self.assertNotIn("Delta:", resumen.text)
        self.assertNotIn("Theta:", resumen.text)
        self.assertNotIn("Alpha:", resumen.text)
        self.assertNotIn("Beta:", resumen.text)
        self.assertIn("Consolas", resumen.font.family)
        self.assertEqual(figura.layout.margin.l, 170)
        self.assertEqual(figura.layout.margin.r, 390)
        self.assertEqual(figura.layout.xaxis.rangeselector.to_plotly_json(), {})
        self._assert_cursor_vertical_compartido(
            figura,
            ("xaxis", "xaxis2", "xaxis3", "xaxis4", "xaxis5"),
        )

    def test_cursor_vertical_unilateral_cubre_dsa_bis_y_emg(self):
        tiempo = pd.date_range("2026-05-14 13:30:12", periods=3, freq="s")
        frecuencias = np.arange(0.5, 30.5, 0.5)
        matriz = np.full((3, len(frecuencias)), 70.0)

        figura = crear_figura_dsa_unilateral_interactiva(
            tiempo=tiempo,
            frecuencias=frecuencias,
            matriz=matriz,
            sef=np.array([15.0, 15.2, 15.4]),
            mef=np.array([4.5, 4.7, 4.9]),
            bis=np.array([60.0, 61.0, 62.0]),
            emg=np.array([30.0, 31.0, 32.0]),
            sr=np.array([0.0, 0.0, 0.0]),
        )

        titulos = [anotacion.text for anotacion in figura.layout.annotations]
        self.assertIn("Electromiograma frontal (EMGLOW01)", titulos)
        self._assert_cursor_vertical_compartido(
            figura,
            ("xaxis", "xaxis2", "xaxis3"),
        )



if __name__ == "__main__":
    unittest.main()
