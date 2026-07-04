import unittest

import numpy as np
import pandas as pd

from src.alineacion_temporal import crear_mascara_discontinuidades
from src.lectura_spa import preparar_dsa_unilateral_con_spa


class MascaraComunVistasTest(unittest.TestCase):
    def test_dos_matrices_distintas_reutilizan_la_misma_mascara(self):
        tiempo = pd.date_range("2026-01-01", periods=4, freq="s")
        frecuencias = np.arange(0.5, 30.5, 0.5)
        dsa_fa = pd.DataFrame(
            np.full((4, len(frecuencias)), 70.0),
            columns=frecuencias,
        )
        dsa_raw = pd.DataFrame(
            np.full((4, len(frecuencias)), 80.0),
            columns=frecuencias,
        )
        df_spa = pd.DataFrame(
            {
                "Time": tiempo,
                "SEF08": [15.0, 16.0, 17.0, 18.0],
                "MEDFRQ08": [5.0, 6.0, 7.0, 8.0],
                "SQI10": [100.0] * 4,
                "TOTPOW08": [70.0] * 4,
                "DB13U01": [40.0, 41.0, 42.0, 43.0],
                "EMGLOW01": [30.0, 31.0, 32.0, 33.0],
                "SR12": [0.0, 1.0, 2.0, 3.0],
            }
        )
        mascara = pd.Series([False, True, False, True])

        fa, variables_fa, mascara_fa = preparar_dsa_unilateral_con_spa(
            tiempo,
            dsa_fa,
            df_spa,
            mask_comun=mascara,
        )
        raw, variables_raw, mascara_raw = preparar_dsa_unilateral_con_spa(
            tiempo,
            dsa_raw,
            df_spa,
            mask_comun=mascara,
        )

        self.assertEqual(mascara_fa.tolist(), mascara.tolist())
        self.assertEqual(mascara_raw.tolist(), mascara.tolist())
        self.assertEqual(
            fa.isna().all(axis=1).tolist(),
            mascara.tolist(),
        )
        self.assertEqual(
            raw.isna().all(axis=1).tolist(),
            mascara.tolist(),
        )
        for columna in [
            "SEF08",
            "MEDFRQ08",
            "DB13U01",
            "EMGLOW01",
            "SR12",
        ]:
            np.testing.assert_array_equal(
                variables_fa[columna].isna().to_numpy(),
                variables_raw[columna].isna().to_numpy(),
            )

    def test_fa_genera_filas_ausentes_y_conserva_la_reanudacion(self):
        timeline = pd.date_range(
            "2026-01-01 10:40:35",
            "2026-01-01 10:40:42",
            freq="s",
        )
        tiempo_fa = pd.to_datetime(
            [
                "2026-01-01 10:40:35",
                "2026-01-01 10:40:41",
                "2026-01-01 10:40:42",
            ]
        )
        frecuencias = np.arange(0.5, 30.5, 0.5)
        dsa_fa = pd.DataFrame(
            np.full((3, len(frecuencias)), 70.0),
            columns=frecuencias,
        )
        df_spa = pd.DataFrame(
            {
                "Time": timeline,
                "SEF08": [15.0] * len(timeline),
                "MEDFRQ08": [5.0] * len(timeline),
                "SQI10": [100.0] * len(timeline),
                "TOTPOW08": [70.0] * len(timeline),
                "DB13U01": [40.0] * len(timeline),
                "EMGLOW01": [30.0] * len(timeline),
                "SR12": [0.0] * len(timeline),
            }
        )
        mascara = crear_mascara_discontinuidades(timeline, tiempo_fa)

        dsa_plot, variables, mascara_final = (
            preparar_dsa_unilateral_con_spa(
                tiempo_fa,
                dsa_fa,
                df_spa,
                mask_comun=mascara,
                timeline_comun=timeline,
            )
        )

        esperado = [False, True, True, True, True, True, False, False]
        self.assertEqual(mascara_final.tolist(), esperado)
        self.assertEqual(dsa_plot.isna().all(axis=1).tolist(), esperado)
        self.assertEqual(
            variables["DB13U01"].isna().tolist(),
            esperado,
        )


if __name__ == "__main__":
    unittest.main()
