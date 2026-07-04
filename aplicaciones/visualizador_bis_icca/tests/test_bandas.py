import unittest

import numpy as np

from src.bandas import (
    BANDAS_EEG,
    calcular_densidad_espectral_media_bandas,
)


def _fila_con_proporciones(proporciones, escala_total=1.0):
    frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)
    potencia = np.zeros_like(frecuencias, dtype=float)

    for indice, (_nombre, inferior, superior) in enumerate(BANDAS_EEG):
        if indice == len(BANDAS_EEG) - 1:
            mascara = (frecuencias >= inferior) & (frecuencias <= superior)
        else:
            mascara = (frecuencias >= inferior) & (frecuencias < superior)
        potencia[mascara] = (
            escala_total * proporciones[indice] / mascara.sum()
        )

    return 10 * np.log10(potencia)


class TestDensidadEspectralMediaBandas(unittest.TestCase):
    def test_calcula_media_lineal_y_convierte_a_db_al_final(self):
        frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)
        # Todas las bandas tienen la misma densidad lineal, aunque contienen
        # distinto número de bins. Deben devolver el mismo valor.
        potencia_por_bin = np.full(len(frecuencias), 0.5 * 1e7)
        fila = 10 * np.log10(potencia_por_bin)
        matriz = np.vstack(
            [fila, fila + 10 * np.log10(3.0), np.full(len(frecuencias), np.nan)]
        )

        resumen = calcular_densidad_espectral_media_bandas(
            matriz,
            frecuencias,
        )

        self.assertEqual(resumen["segundos_validos"], 2)
        self.assertEqual(resumen["segundos_totales"], 3)
        esperado_db = 10 * np.log10(2e7)
        for banda, valor in resumen["valores_db"].items():
            self.assertAlmostEqual(
                valor,
                esperado_db,
            )
        # Con densidad idéntica, la potencia integrada depende del número de
        # bins: alfa contiene 10 y delta 7.
        self.assertAlmostEqual(
            resumen["ratio_alpha_delta"],
            10 / 7,
        )

    def test_adr_suma_potencia_del_intervalo_antes_de_dividir(self):
        frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)
        fila_1 = _fila_con_proporciones([0.4, 0.1, 0.4, 0.1])
        fila_2 = _fila_con_proporciones(
            [0.5, 0.1, 0.2, 0.2],
            escala_total=10.0,
        )
        matriz = np.vstack([fila_1, fila_2])

        resumen = calcular_densidad_espectral_media_bandas(
            matriz,
            frecuencias,
        )

        # Alfa total = 0.4 + 2.0; delta total = 0.4 + 5.0.
        self.assertAlmostEqual(
            resumen["ratio_alpha_delta"],
            2.4 / 5.4,
        )

    def test_rechaza_forma_incompatible(self):
        frecuencias = np.arange(0.5, 30.0 + 0.5, 0.5)

        with self.assertRaisesRegex(ValueError, "frecuencias"):
            calcular_densidad_espectral_media_bandas(
                np.zeros((2, len(frecuencias) - 1)),
                frecuencias,
            )


if __name__ == "__main__":
    unittest.main()
