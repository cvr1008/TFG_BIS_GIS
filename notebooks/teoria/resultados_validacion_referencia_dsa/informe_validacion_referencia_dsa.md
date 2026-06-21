# Validación de la referencia en decibelios de la DSA

## Objetivo

Se compararon dos conversiones de la potencia integrada en cada bin de
0,5 Hz:

```python
# A. Referencia de amplitud indicada para la DSA
dsa_a = 10 * np.log10(potencia_bin_uv2 / (0.0001 ** 2))

# B. Referencia de potencia indicada para TOTPOW y EMG
dsa_b = 10 * np.log10(potencia_bin_uv2 / 0.0001)
```

La potencia de cada bin se obtuvo a partir de la densidad espectral de
Welch:

```python
potencia_bin_uv2 = psd_uv2_hz * 0.5
```

Se mantuvieron iguales el canal, filtro pasa-altos, Welch, suavizado
`SpSmooth`, máscaras y desplazamiento temporal de la aplicación.

## Unidades

1. Señal cruda calibrada: `µV`.
2. Densidad espectral de Welch: `µV²/Hz`.
3. Potencia integrada del bin: `µV²`.
4. Referencia A expresada como potencia:
   `(0,0001 µV RMS)² = 10⁻⁸ µV²`.
5. Referencia B expresada como potencia:
   `0,0001 µV² = 10⁻⁴ µV²`.

Por tanto:

```text
A - B = 10 log10(10⁻⁴ / 10⁻⁸) = 40 dB
```

La diferencia se comprobó en todas las celdas válidas, con desviación
numérica máxima inferior a `9e-14 dB`.

## Resultados frente a `.f_a`

| Registro | Lado | Pearson A | MAE A | RMSE A | Sesgo A | MAE B | RMSE B | Sesgo B |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| L03041035 | Unilateral | 0,7260 | 3,7113 | 5,0219 | +2,9516 | 37,0484 | 37,2705 | -37,0484 |
| L05141322 | Izquierdo | 0,9397 | 1,5902 | 2,2933 | +0,5219 | 39,4781 | 39,5412 | -39,4781 |
| L05141322 | Derecho | 0,9459 | 1,7373 | 2,3748 | +0,8682 | 39,1318 | 39,1941 | -39,1318 |
| L04301923 | Izquierdo | 0,9871 | 0,8624 | 1,5297 | -0,2284 | 40,2285 | 40,2569 | -40,2284 |
| L04301923 | Derecho | 0,9802 | 0,9896 | 1,7866 | -0,0321 | 40,0321 | 40,0719 | -40,0321 |

Ponderando por el número de celdas válidas:

- Fórmula A: MAE aproximado `1,00 dB`, RMSE global `1,80 dB` y sesgo
  `-0,04 dB`.
- Fórmula B: MAE aproximado `40,04 dB`, RMSE global `40,08 dB` y sesgo
  `-40,04 dB`.

Pearson es idéntico para A y B porque ambas matrices solo difieren en una
constante de 40 dB.

## Comparación con `TOTPOW08`

Se calculó:

```python
potencia_total_uv2 = potencia_bin_uv2.sum(axis=1)
totpow_db = 10 * np.log10(potencia_total_uv2 / 0.0001)
```

| Registro | Lado | Pearson | MAE | RMSE | Sesgo |
|---|---|---:|---:|---:|---:|
| L03041035 | Unilateral | 0,6210 | 2,6879 | 3,3945 | -1,9856 |
| L05141322 | Izquierdo | 0,7600 | 4,0316 | 4,3913 | -4,0148 |
| L05141322 | Derecho | 0,7975 | 3,8093 | 4,1634 | -3,8043 |
| L04301923 | Izquierdo | 0,5918 | 7,2325 | 7,3483 | -7,2269 |
| L04301923 | Derecho | 0,3712 | 6,5212 | 6,6921 | -6,5203 |

La referencia de TOTPOW proporciona el orden de magnitud correcto, pero
la suma de los bins reconstruidos no reproduce exactamente `TOTPOW08`.
La discrepancia permanece al derivar la potencia total directamente desde
`.f_a`, por lo que no puede atribuirse a la elección entre A y B.

## Interpretación del archivo `.f_a`

- Los valores se almacenan como enteros y deben dividirse entre 100.
- Después de ese escalado, los datos están expresados en dB y pueden superar
  los límites de visualización de 49-94 dB.
- Los límites 49-94 dB corresponden a la representación gráfica, no a un
  recorte de los datos exportados.
- El sesgo prácticamente nulo de A en los registros bilaterales largos no
  muestra evidencia de un offset constante adicional en `.f_a`.

## Conclusiones

1. La referencia que reproduce `.f_a` es la fórmula A:
   `10 log10(potencia_bin_uv2 / (0.0001²))`.
2. La fórmula B deja toda la DSA aproximadamente 40 dB por debajo.
3. La referencia `0,0001 µV²` es adecuada para situar TOTPOW en su escala,
   pero no basta para replicar el algoritmo propietario de `TOTPOW08`.
4. Los resultados no demuestran una errata documental. Los manuales utilizan
   referencias distintas: amplitud RMS para la DSA y potencia para TOTPOW.
5. La aplicación debe conservar la fórmula A para la DSA reconstruida.
6. Debe indicarse que la validación se limita a tres registros únicos y que
   no se conoce por completo el preprocesamiento propietario utilizado para
   `TOTPOW08` y la generación del espectro exportado.
