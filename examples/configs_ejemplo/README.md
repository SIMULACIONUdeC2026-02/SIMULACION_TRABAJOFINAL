# Configuraciones de ejemplo

Cada archivo es una configuración válida según el contrato de entrada
(`docs/contratos.md`). Sirven de datos de prueba para todos los equipos.
`tests/test_config.py` recorre esta carpeta y comprueba que **todos** los
`.json` pasan `validar_config`; si agregas uno inválido, ese test falla.

Unidades: el tiempo se mide en **minutos**; la tasa de llegadas va en
**clientes por hora** (`lambda_por_hora`); `media`, `min` y `max` del servicio
van en minutos.

## Cómo se escribe cada variante

| Variante | Servidores | `colas` | Notas |
|---|---|---|---|
| Cola única, múltiples servidores | c servidores | `unica`, cantidad 1 | Todos toman de la misma cola |
| Colas múltiples, múltiples servidores | c servidores | `multiple`, cantidad = c, con `reparticion` | Una cola por servidor |
| Colas múltiples + preferenciales | c servidores | `preferencial`, cantidad 2 | Requiere `simulacion.clientes_preferenciales` |
| Colas múltiples, servidor único | 1 servidor | `multiple`, cantidad >= 2, con `reparticion` | El servidor atiende al que lleva más esperando |

Método 2 (`secuencial`): agrega `simulacion.estacion_entrada` y enlaza las
estaciones con `salidas`, por ejemplo
`"salidas": [{"hacia": "atencion", "probabilidad": 1}]`. La última estación
lleva `"salidas": []`.

## Estado

| Archivo | Método | Variante | Estado |
|---|---|---|---|
| `01_paralelo_cola_unica.json` | Paralelo | Cola única, múltiples servidores | Hecho (formato de referencia) |
| Las otras 7 variantes | | | Pendiente: Equipo 2 |

Nombres sugeridos para el resto: `02_paralelo_colas_multiples.json`,
`03_paralelo_preferencial.json`, `04_paralelo_servidor_unico.json` y
`05` a `08` con el mismo orden para Método 2 (secuencial).
