# Integración de señales BIS y variables clínicas para análisis retrospectivo en UCI

Este proyecto nace de una necesidad concreta del entorno de UCI: interpretar señales de neuromonitorización no como valores aislados, sino dentro del contexto clínico real del paciente. Para ello se trabaja con exportaciones del monitor BIS, matrices de densidad espectral (DSA), variables procesadas del dispositivo y, de forma progresiva, variables clínicas procedentes de sistemas hospitalarios como ICCA.

El objetivo principal es desarrollar una herramienta que permita revisar registros BIS de forma temporal, visual e integrada, facilitando el análisis retrospectivo de la actividad cerebral monitorizada en pacientes de UCI.

De forma más concreta, el trabajo aborda:

- lectura y exploración de archivos exportados por el monitor BIS;
- reconstrucción y visualización de la matriz de densidad espectral (DSA);
- representación sincronizada de parámetros como BIS, Spectral Edge Frequency, Median Frequency, Electromiograma, Tasa de Supresión o Asimetría;
- integración de variables clínicas procedentes de ICCA para contextualizar la neuromonitorización.

## Contexto

El índice BIS resume la actividad EEG en un valor numérico, pero su interpretación en pacientes críticos puede verse condicionada por la calidad de señal, artefactos, fármacos, sedación profunda, supresión de ráfagas o situación neurológica del paciente.

Por este motivo, el proyecto no se limita a representar el valor BIS. También reconstruye y visualiza información espectral, especialmente la DSA, que permite observar la evolución de la potencia del EEG por bandas de frecuencia a lo largo del tiempo.

La finalidad no es sustituir el criterio clínico, sino proporcionar una herramienta de apoyo para revisar los datos de forma más clara, contextualizada y trazable.

### Autora
Cristina Velázquez Romano
Grado en Ingeniería de la Salud, Escuela Politécnica Superior (Campus Milanera) - Universidad de Burgos
