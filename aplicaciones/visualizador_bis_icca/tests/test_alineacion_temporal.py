import unittest

import pandas as pd

from src.alineacion_temporal import (
    calcular_timeline_comun,
    crear_mascara_discontinuidades,
    deduplicar_dataframe_temporal,
)


class AlineacionTemporalTest(unittest.TestCase):
    def test_conserva_la_ultima_aparicion_de_un_segundo_duplicado(self):
        df = pd.DataFrame(
            {
                "Time": [
                    "2026-01-01 00:00:01",
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:01",
                ],
                "valor": [10, 20, 30],
            }
        )

        resultado = deduplicar_dataframe_temporal(df)

        self.assertEqual(resultado["valor"].tolist(), [20, 30])

    def test_interseca_raw_spa_y_fa_sin_prolongar_extremos(self):
        inicio_raw = pd.Timestamp("2026-01-01 00:00:00")
        spa = pd.to_datetime(
            [
                "2026-01-01 00:00:02",
                "2026-01-01 00:00:03",
                "2026-01-01 00:00:03",
                "2026-01-01 00:00:04",
                "2026-01-01 00:00:05",
                "2026-01-01 00:00:06",
                "2026-01-01 00:00:07",
            ]
        )
        fa = pd.date_range(
            "2026-01-01 00:00:03",
            "2026-01-01 00:00:05",
            freq="s",
        )

        resultado = calcular_timeline_comun(
            inicio_raw=inicio_raw,
            numero_muestras_raw=10 * 128 + 64,
            fs=128,
            tiempos_spa=spa,
            tiempos_fa=fa,
        )

        self.assertEqual(
            resultado["timeline"].tolist(),
            list(fa),
        )
        self.assertEqual(resultado["muestras_residuales_raw"], 64)
        self.assertEqual(
            resultado["fuentes"]["spa"]["duplicados_eliminados"],
            1,
        )
        self.assertEqual(
            resultado["fuentes"]["raw"]["proporcion_eliminada"],
            0.7,
        )
        self.assertEqual(
            resultado["fuentes"]["spa"]["proporcion_eliminada"],
            0.5,
        )
        self.assertTrue(resultado["fuentes"]["raw"]["alerta_recorte"])
        self.assertTrue(resultado["fuentes"]["spa"]["alerta_recorte"])
        self.assertFalse(resultado["fuentes"]["fa"]["alerta_recorte"])
        self.assertEqual(
            resultado["fuentes"]["raw"]["forma_recorte"],
            "dos_bloques_extremos",
        )
        self.assertEqual(
            resultado["fuentes"]["raw"]["numero_tramos_recortados"],
            2,
        )

    def test_distingue_bloque_inicial_de_hueco_interno(self):
        resultado = calcular_timeline_comun(
            inicio_raw=pd.Timestamp("2026-01-01 00:00:00"),
            numero_muestras_raw=10 * 128,
            fs=128,
            tiempos_spa=pd.to_datetime(
                [
                    "2026-01-01 00:00:05",
                    "2026-01-01 00:00:06",
                    "2026-01-01 00:00:08",
                    "2026-01-01 00:00:09",
                ]
            ),
        )

        raw = resultado["fuentes"]["raw"]
        spa = resultado["fuentes"]["spa"]
        self.assertEqual(raw["forma_recorte"], "bloque_continuo")
        self.assertEqual(raw["tramos_recortados"][0]["posicion"], "inicio")
        self.assertEqual(raw["tramos_recortados"][0]["segundos"], 5)
        self.assertTrue(raw["alerta_recorte"])
        self.assertEqual(spa["segundos_huecos_internos"], 1)
        self.assertEqual(spa["numero_tramos_huecos_internos"], 1)
        self.assertTrue(spa["discontinuidad_interna"])

    def test_marca_solo_los_segundos_ausentes_del_hueco(self):
        timeline = pd.date_range(
            "2026-01-01 10:40:35",
            "2026-01-01 10:40:42",
            freq="s",
        )
        tiempos_fuente = pd.to_datetime(
            [
                "2026-01-01 10:40:35",
                "2026-01-01 10:40:41",
                "2026-01-01 10:40:42",
            ]
        )

        mascara = crear_mascara_discontinuidades(
            timeline,
            tiempos_fuente,
        )

        self.assertEqual(
            mascara.tolist(),
            [False, True, True, True, True, True, False, False],
        )


if __name__ == "__main__":
    unittest.main()
