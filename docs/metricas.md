# Métricas: definiciones y supuestos (Equipo 3)

Complementa la sección "Definiciones de métricas" de `docs/contratos.md`.
Todo se calcula en `src/metrics.py` a partir de `eventos_clientes`; la UI solo
muestra los resultados. Unidades: minutos.

## Supuestos sobre `eventos_clientes` (a confirmar con Engine, Issue #5)

- Un cliente que sigue dentro del sistema al terminar la simulación trae
  `tiempo_salida_sistema: null`. No cuenta como atendido.
- Un servicio que no terminó trae `tiempo_fin_servicio: null`; un cliente que
  sigue en cola trae `tiempo_inicio_servicio: null` y `servidor_asignado: null`.

## Regla de corte en `T = duracion_total_minutos` (revisión del PR #28)

- **Atendido = salió del sistema antes de terminar la simulación**
  (`tiempo_salida_sistema` definido y `<= T`). Un cliente que sale después de
  `T` se trata igual que uno que sigue dentro (`null`): no cuenta como
  atendido, no entra en W ni en la Ley de Little.
- **W no se recorta:** es el tiempo real (`salida - entrada`) de los atendidos.
- **Lo que suma tiempo sí se recorta a `[0, T]`:** la integración de N(t) (y,
  en el Issue #15, la ocupación de cada servidor) solo cuenta los minutos que
  caen dentro de la simulación.

Ejemplo (el de la revisión): un cliente entra a los 15 y sale a los 30, con
`T = 20`. No es atendido, así que W = 0, atendidos = 0 y L por Little = 0; la
integración cuenta sus 5 minutos dentro de `[0, 20]` y da L = 5 / 20 = 0.25.
Las dos L difieren porque el sistema no está vacío al final: en ese caso la
integración es la más fiel. Lo comprueban los tests
`test_cliente_que_sale_despues_del_final_*` y
`test_salir_despues_del_final_equivale_a_seguir_dentro`.

## Sistema completo (Issues #13 y #14)

| Métrica | Función | Fórmula |
|---|---|---|
| `clientes_totales_atendidos` | `clientes_totales_atendidos()` | clientes con `tiempo_salida_sistema` definido y `<= T` |
| `tiempo_promedio_en_sistema` (W) | `tiempo_promedio_en_sistema()` | promedio de `salida - entrada` de los atendidos (sin recortar) |
| `clientes_promedio_en_sistema` (L) | `clientes_promedio_en_sistema()` | Ley de Little: `L = λ · W`, con `λ = atendidos / T` |
| L por integración (verificación) | `clientes_promedio_por_integracion()` | `(1/T) · ∫ N(t) dt` = suma de minutos que cada cliente pasó dentro de `[0, T]` dividido por `T` |

Todas reciben `duracion_total_minutos` (mayor que 0; si no, `ValueError`) y
devuelven 0 cuando no hay clientes.

Si todos los clientes entran y salen dentro de `[0, T]`, las dos formas de
calcular L dan lo mismo (lo comprueba `tests/test_metrics.py`). Si quedan
clientes dentro al final, o salen después de `T`, la integración es más fiel
porque los cuenta.

## Colas (Issue #16)

Una cola se identifica con `(estacion_id, cola_asignada)`. Un cliente está en
la cola desde `tiempo_inicio_espera` hasta `tiempo_inicio_servicio`; Lq(t) es
la cantidad de clientes esperando en el instante t. Un cliente que no esperó
(`inicio_espera == inicio_servicio`) no cuenta.

| Métrica | Función | Fórmula |
|---|---|---|
| `por_cola[cola_N].longitud_promedio` | `longitud_cola()` | `(1/T) · ∫ Lq(t) dt` sobre `[0, T]` = suma de los minutos que cada cliente esperó en esa cola, dividida por `T` |
| `por_cola[cola_N].longitud_maxima` | `longitud_cola()` | mayor cantidad de clientes esperando a la vez en esa cola |
| `por_cola` completo | `metricas_por_cola()` | una entrada por cada cola de la configuración (`colas.cantidad`), aunque nadie haya esperado en ella |
| `longitud_promedio_cola` | `longitud_cola_estacion()` | lo mismo con todas las colas de la estación juntas; es igual a la suma de los promedios de sus colas |
| `longitud_maxima_cola` | `longitud_cola_estacion()` | mayor cantidad de clientes esperando a la vez en **toda** la estación. No es la suma de los máximos de cada cola, porque pueden ocurrir en momentos distintos |
| `cola_mas_larga` | `cola_mas_larga()` | ver el criterio abajo |

**Criterio de `cola_mas_larga` (para que UI lo muestre igual):** es la cola con
mayor `longitud_promedio`, no la de mayor `longitud_maxima`. En un empate gana
la de menor número (`cola_1` antes que `cola_2`); si todas están vacías, es
`cola_1`. Es el criterio de los resultados de ejemplo.

Numeración de las colas, según el tipo:

- `unica`: solo `cola_1`.
- `multiple`: `cola_1` ... `cola_k`, en el orden de la configuración.
- `preferencial`: `cola_1` = preferenciales y `cola_2` = normales.

Reglas de tiempo:

- En un empate de tiempos, primero sale el cliente que pasa a servicio y luego
  entra el que llega (así lo calculan los ejemplos a mano: en el ejemplo 01, en
  t = 4 la cola sigue en 1, no en 2).
- La espera se recorta a `[0, T]`, igual que la integración de N(t). Un cliente
  que sigue en cola al final (`tiempo_inicio_servicio: null`) cuenta hasta `T`.

Ejemplo 01 (cola única, T = 20): esperan los clientes 4 (3-4), 5 (4-5) y 6
(6-7) → área 3, longitud promedio 3 / 20 = **0.15**, longitud máxima **1**.

## Por estación y resumen completo (Issue #17)

| Métrica | Función | Fórmula |
|---|---|---|
| `tiempo_promedio_espera_cola` (Wq) | `tiempo_promedio_espera_cola()` | promedio de `tiempo_inicio_servicio - tiempo_inicio_espera` de las paradas de la estación que empezaron a ser atendidas antes de `T` |
| `tiempo_promedio_atencion` | `tiempo_promedio_atencion()` | promedio de `tiempo_fin_servicio - tiempo_inicio_servicio` de las paradas cuyo servicio terminó antes de `T` |
| `longitud_promedio_cola`, `longitud_maxima_cola`, `por_cola`, `cola_mas_larga` | ver la sección **Colas** | |
| `por_servidor` | `calculo_ocioso_estacion()` | utilización, tiempo ocioso y clientes atendidos (Issue #15) |

Todas usan `paradas_por_estacion()`: un cliente que pasa por varias estaciones
aporta a cada una solo su parada en esa estación. Con una sola estación,
`Wq + tiempo de atención = W`.

### `calcular_metricas(eventos_clientes, config, duracion_total_minutos)`

Arma el bloque `metricas` completo de `docs/contratos.md`:

- `sistema_completo`: `tiempo_promedio_en_sistema`, `clientes_promedio_en_sistema`
  (Little) y `clientes_totales_atendidos`.
- `por_estacion`: una entrada por **cada estación de la configuración**, en el
  mismo orden, con las 7 claves del contrato (`metricas_estacion()`). Una
  estación por la que no pasó nadie aparece con sus valores en 0, sus servidores
  ociosos todo el tiempo y `cola_mas_larga = "cola_1"`.

Los valores no se redondean: la interfaz decide cuántos decimales mostrar.

`simular(config)` (src/engine.py) ya la llama, así que la interfaz recibe el
bloque `metricas` en cada simulación. Las pruebas lo comprueban con los 8
ejemplos de `examples/configs_ejemplo/`: el resultado pasa
`validar_resultado(..., exigir_metricas=True)` y la L por Little coincide con la
L por integración (el motor atiende a todos antes de `T`). También reproducen
las métricas calculadas a mano en `examples/resultados_ejemplo/`.
