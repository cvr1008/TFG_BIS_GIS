import base64
import io
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from PIL import Image

from src.informe_pdf import crear_informe_pdf, nombre_archivo_informe


class InformePdfTest(unittest.TestCase):
    def _data_url_png(self):
        buffer = io.BytesIO()
        Image.new("RGB", (24, 16), "white").save(buffer, format="PNG")
        contenido = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{contenido}"

    def _registro(self):
        tiempo = pd.date_range("2026-05-01 10:00:00", periods=5, freq="s")
        frecuencias = np.array([0.5, 4.0, 8.0, 13.0, 30.0])
        matriz = np.tile(np.linspace(50.0, 80.0, len(frecuencias)), (len(tiempo), 1))
        return {
            "modo": "unilateral",
            "origen": "fa",
            "tiempo": tiempo,
            "frecuencias": frecuencias,
            "matriz": matriz,
            "sef": np.linspace(9.0, 10.0, len(tiempo)),
            "mef": np.linspace(4.0, 5.0, len(tiempo)),
            "bis": np.linspace(40.0, 45.0, len(tiempo)),
            "emg": np.linspace(25.0, 26.0, len(tiempo)),
            "sr": np.zeros(len(tiempo)),
            "sesion_paciente": {
                "paciente_id": "PACIENTE_001",
                "nombre_carpeta": "SESION_001_TEST",
                "sesion_bis_id": "TEST01",
                "inicio_bis": "2026-05-01 10:00:00",
                "fin_bis": "2026-05-01 10:00:04",
                "carpeta_bis": "SESIONES/SESION_001_TEST/BIS/TEST01",
            },
            "icca": {
                "peso_kg": 70.0,
                "constantes": pd.DataFrame(
                    {
                        "timestamp": [pd.Timestamp("2026-05-01 10:00:01")],
                        "fc__valor": [82.0],
                        "series_reales": ["fc"],
                    }
                ),
                "series": pd.DataFrame(
                    {
                        "serie": ["fc"],
                        "variable": ["fc"],
                        "unidad": ["lpm"],
                    }
                ),
                "analisis": pd.DataFrame(
                    {
                        "timestamp": [pd.Timestamp("2026-05-01 10:00:02")],
                        "variable": ["Hemoglobina"],
                        "valor": [12.4],
                        "unidad": ["g/dL"],
                    }
                ),
                "perfusiones": pd.DataFrame(
                    {
                        "timestamp": [pd.Timestamp("2026-05-01 10:00:03")],
                        "farmaco": ["Midazolam"],
                        "dosis_actual": [2.5],
                        "unidad_dosis": ["mg/h"],
                        "velocidad_bomba_ml_h": [5.0],
                    }
                ),
            },
        }

    def test_crea_pdf_valido_del_intervalo_visualizado(self):
        registro = self._registro()
        inicio = pd.Timestamp("2026-05-01 10:00:00")
        fin = pd.Timestamp("2026-05-01 10:00:04")

        with patch(
            "src.informe_pdf.crear_panoramica_estatica",
            return_value=self._data_url_png(),
        ):
            contenido = crear_informe_pdf(registro, registro, inicio, fin, "1h")

        self.assertTrue(contenido.startswith(b"%PDF"))
        self.assertGreater(len(contenido), 2500)

    def test_nombre_archivo_usa_sesion(self):
        nombre = nombre_archivo_informe(
            self._registro(),
            pd.Timestamp("2026-05-01 10:00:00"),
            pd.Timestamp("2026-05-01 10:00:04"),
        )

        self.assertEqual(
            nombre,
            "Informe_BIS_ICCA_sesion_SESION_001_TEST.pdf",
        )


if __name__ == "__main__":
    unittest.main()
