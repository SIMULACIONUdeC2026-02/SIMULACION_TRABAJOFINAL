# Resultados de ejemplo (contrato de salida)

Datos de prueba escritos a mano para que **Métricas** y **UI** trabajen sin
esperar al motor (Issue #12). Cada resultado va emparejado con la configuración
que lo habría producido:

| Archivo | Qué es |
|---|---|
| `01_paralelo_cola_unica_config.json` | Método 1: 3 cajeros, cola única, 20 min |
| `01_paralelo_cola_unica_resultado.json` | 8 clientes, con sus `paradas` y `metricas` |
| `02_secuencial_preferencial_config.json` | Método 2: triaje (1 servidor) → atención (2 servidores, cola preferencial), 30 min |
| `02_secuencial_preferencial_resultado.json` | 5 clientes (2 preferenciales), 2 paradas cada uno |

Los tiempos son números redondos para poder revisar las métricas con lápiz y
papel. `tests/test_resultados_ejemplo.py` comprueba que los archivos respetan
el contrato de salida, que la configuración pasa `validar_config` y que las
métricas del sistema cuadran con los eventos. Si se agrega un par nuevo
(`NN_nombre_config.json` + `NN_nombre_resultado.json`), el test lo revisa solo.

Para la UI: `metricas.sistema_completo` alimenta las 3 tarjetas de la vista de
resultados, `metricas.por_estacion` la tabla resumen, `por_cola` la gráfica de
comparación de colas y `por_servidor` la de utilización.

## Cálculo a mano del ejemplo 01

| Cliente | Entra | Inicia servicio | Sale | Servidor | Espera | En sistema |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 5 | 1 | 0 | 5 |
| 2 | 1 | 1 | 4 | 2 | 0 | 3 |
| 3 | 2 | 2 | 8 | 3 | 0 | 6 |
| 4 | 3 | 4 | 10 | 2 | 1 | 7 |
| 5 | 4 | 5 | 7 | 1 | 1 | 3 |
| 6 | 6 | 7 | 12 | 1 | 1 | 6 |
| 7 | 9 | 9 | 11 | 3 | 0 | 2 |
| 8 | 10 | 10 | 13 | 2 | 0 | 3 |

- W = 35 / 8 = **4.375 min**; λ = 8 / 20 = 0.4 clientes/min; L = λ·W = **1.75**.
- Servidor 1: ocupado 5 + 2 + 5 = 12 min → utilización 0.6, ocioso 8 min.
- Servidor 2: ocupado 3 + 6 + 3 = 12 min → utilización 0.6, ocioso 8 min.
- Servidor 3: ocupado 6 + 2 = 8 min → utilización 0.4, ocioso 12 min.
- Cola: esperan los clientes 4, 5 y 6 un minuto cada uno → área 3,
  longitud promedio 3 / 20 = **0.15**, longitud máxima **1** (en t = 4 el
  cliente 4 sale de la cola en el mismo instante en que entra el 5).

## Cálculo a mano del ejemplo 02

- Tiempos en el sistema: 8, 6, 10.5, 6 y 4 → W = 34.5 / 5 = **6.9 min**;
  L = 34.5 / 30 = **1.15**.
- Triaje: esperas 0, 1, 1.5, 1, 0 → 0.7 min; servidor ocupado 7 de 30 min
  (utilización 0.2333).
- Atención: el cliente 4 (preferencial) llega a las 6 y el 3 (normal) espera
  desde las 5; a las 7 se libera el servidor 2 y atiende primero al
  preferencial (cola 1). Cada servidor queda ocupado 10 de 30 min (0.3333).

## Criterios usados en `metricas` (a confirmar en el Issue #17)

- `longitud_promedio_cola` de la estación = suma de las longitudes promedio de
  sus colas; `longitud_maxima_cola` = máximo de clientes esperando a la vez en
  todas sus colas juntas.
- En un empate de tiempos, primero sale el cliente que pasa a servicio y luego
  entra el que llega.
- `cola_mas_larga` = la de mayor `longitud_promedio` (empate → menor número).
- Valores redondeados a 4 decimales.
