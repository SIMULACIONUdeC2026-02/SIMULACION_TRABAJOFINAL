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
