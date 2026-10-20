# Métricas: definiciones y supuestos (Equipo 3)

Complementa la sección "Definiciones de métricas" de `docs/contratos.md`.
Todo se calcula en `src/metrics.py` a partir de `eventos_clientes`; la UI solo
muestra los resultados. Unidades: minutos.

## Supuestos sobre `eventos_clientes` (a confirmar con Engine, Issue #5)

- Un cliente que sigue dentro del sistema al terminar la simulación trae
  `tiempo_salida_sistema: null`. No cuenta como atendido.
- Un servicio que no terminó trae `tiempo_fin_servicio: null`; un cliente que
  sigue en cola trae `tiempo_inicio_servicio: null` y `servidor_asignado: null`.
- Todo intervalo se recorta a `[0, duracion_total_minutos]`.

## Sistema completo (Issues #13 y #14)

| Métrica | Función | Fórmula |
|---|---|---|
| `clientes_totales_atendidos` | `clientes_totales_atendidos()` | clientes con `tiempo_salida_sistema` definido |
| `tiempo_promedio_en_sistema` (W) | `tiempo_promedio_en_sistema()` | promedio de `salida - entrada` de los atendidos |
| `clientes_promedio_en_sistema` (L) | `clientes_promedio_en_sistema()` | Ley de Little: `L = λ · W`, con `λ = atendidos / T` |
| L por integración (verificación) | `clientes_promedio_por_integracion()` | `(1/T) · ∫ N(t) dt` = suma de minutos que cada cliente pasó dentro de `[0, T]` dividido por `T` |

Si todos los clientes entran y salen dentro de `[0, T]`, las dos formas de
calcular L dan lo mismo (lo comprueba `tests/test_metrics.py`). Si quedan
clientes dentro al final, la integración es más fiel porque los cuenta.
