import unittest

import numpy as np
import pandas as pd
from dash import html
from unittest.mock import patch

from app import _crear_componente_vista
from src.vistas_temporales import (
    crear_opciones_tramos_horarios,
    preparar_vista_temporal,
)


class VistasTemporalesTest(unittest.TestCase):
    def _registro(self):
        tiempo = pd.date_range("2026-05-01 10:00:00", periods=18001, freq="s")
        return {
            "modo": "unilateral",
            "tiempo": tiempo,
            "frecuencias": np.array([0.5]),
            "matriz": np.zeros((len(tiempo), 1)),
        }

    def test_la_vista_de_90_minutos_ya_no_esta_admitida(self):
        registro = self._registro()
        tramo = crear_opciones_tramos_horarios(registro["tiempo"])[0]["value"]

        with self.assertRaises(ValueError):
            preparar_vista_temporal(registro, tramo, "90m")

    def test_cuatro_horas_es_estatica_y_dos_horas_interactiva(self):
        registro = self._registro()
        tramo = crear_opciones_tramos_horarios(registro["tiempo"])[0]["value"]

        vista_2h, inicio_2h, fin_2h, completa_2h = preparar_vista_temporal(
            registro, tramo, "2h"
        )
        vista_4h, inicio_4h, fin_4h, completa_4h = preparar_vista_temporal(
            registro, tramo, "4h"
        )

        self.assertFalse(vista_2h["vista_estatica"])
        self.assertFalse(completa_2h)
        self.assertEqual(fin_2h - inicio_2h, pd.Timedelta(hours=2))
        self.assertTrue(vista_4h["vista_estatica"])
        self.assertFalse(completa_4h)
        self.assertEqual(fin_4h - inicio_4h, pd.Timedelta(hours=4))

        with patch(
            "app.crear_panoramica_estatica",
            return_value="data:image/png;base64,prueba",
        ):
            componente = _crear_componente_vista(vista_4h, completa_4h)
        self.assertIsInstance(componente, html.Img)


if __name__ == "__main__":
    unittest.main()
