import unittest

import numpy as np
import pandas as pd

from src.reconstruccion import (
    _ajustar_reconstruida_a_timeline,
    _calcular_mascara_final_comun,
    _detectar_perdidas_raw_por_segundo,
    _proyectar_mascara_raw_a_timeline_dsa,
    _suavizar_y_desplazar,
)


class ReconstruccionMascarasTest(unittest.TestCase):
    def test_reindexado_crea_solo_el_borde_inicial_nan(self):
        timeline = pd.Series(
            pd.date_range("2026-01-01", periods=3, freq="s")
        )
        matriz = np.array(
            [
                [10.0, 11.0],
                [20.0, 21.0],
            ]
        )

        resultado = _ajustar_reconstruida_a_timeline(
            matriz=matriz,
            frecuencias=np.array([0.5, 1.0]),
            tiempos_s=np.array([1.0, 2.0]),
            timeline_spa=timeline,
        )

        self.assertTrue(resultado.iloc[0].isna().all())
        np.testing.assert_allclose(
            resultado.iloc[1:].to_numpy(),
            matriz,
        )

    def test_ceros_aislados_no_se_confunden_con_perdida(self):
        fs = 4
        raw = np.ones((3 * fs, 2), dtype=np.int16)
        raw[0, 0] = 0
        raw[fs : fs + 2, 0] = 0
        info = {
            "fs": fs,
            "muestras_objetivo": len(raw),
            "muestras_copiadas": len(raw),
            "origen_inicio": 0,
            "destino_inicio": 0,
        }

        mascara, diagnostico = _detectar_perdidas_raw_por_segundo(
            raw,
            canal=0,
            info_alineacion=info,
            umbral_ceros=0.5,
        )

        self.assertEqual(mascara.tolist(), [False, True, False])
        self.assertEqual(diagnostico["segundos_ceros_elevados"], 1)

    def test_perdida_raw_invalida_las_ventanas_welch_afectadas(self):
        timeline = pd.Series(pd.date_range("2026-01-01", periods=3, freq="s"))
        mascara = _proyectar_mascara_raw_a_timeline_dsa(
            mascara_segundos=[False, True, False],
            tiempos_s=np.array([1.0, 2.0]),
            timeline_spa=timeline,
            fs=4,
            ventana_seg=2,
            paso_seg=1,
        )

        self.assertEqual(mascara.tolist(), [False, True, True])

    def test_rolling_excluye_segundos_invalidos(self):
        dsa = pd.DataFrame({"0.5": [1.0, 100.0, 3.0, 5.0]})
        mascara = pd.Series([False, True, False, False])

        resultado = _suavizar_y_desplazar(
            dsa,
            ventana_s=3,
            shift_s=0,
            mascara_inicial=mascara,
        )

        np.testing.assert_allclose(
            resultado["0.5"].to_numpy(),
            np.array([1.0, 1.0, 2.0, 4.0]),
        )

    def test_mascara_final_incluye_disponibilidad_tras_shift(self):
        mascara_base = pd.Series([True, False, False, True, False])

        resultado = _calcular_mascara_final_comun(
            mascara_base,
            ventana_s=2,
            shift_s=1,
            excluir_invalidos_suavizado=True,
        )

        self.assertEqual(
            resultado.tolist(),
            [True, True, False, True, False],
        )


if __name__ == "__main__":
    unittest.main()
