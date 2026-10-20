# Contratos de datos

Todo el proyecto gira alrededor de dos estructuras JSON. Cada equipo construye
su parte sabiendo qué recibe y qué devuelve; mientras estas formas no cambien,
nadie se rompe cuando otro equipo modifica su código por dentro.

```
Config (entrada) -> Equipo 2: topologías -> Motor (Equipo 1) -> Resultado (salida)
                                                                   |-> Equipo 3: métricas
                                                                   |-> Equipo 4: interfaz
```

**Unidades:** tiempo en minutos; tasa de llegadas en clientes por hora.

**Regla de cambios:** si un PR modifica alguno de estos contratos, debe
actualizar este archivo, marcar la casilla correspondiente en la plantilla de PR
y avisar a los líderes de los equipos que lo consumen.

---

## 1. Contrato de entrada (configuración)

Los comentarios `//` son explicativos; el JSON real no los lleva. El ejemplo es
un sistema secuencial con ramificación y clientes preferenciales, que usa casi
todos los campos.

```jsonc
{
  "simulacion": {
    "nombre": "Clínica - Escenario 1",          // opcional
    "metodo": "secuencial",                      // "paralelo" (Método 1) | "secuencial" (Método 2)
    "duracion_minutos": 480,
    "semilla": 42,                               // opcional, para reproducir resultados
    "llegada": {                                 // ÚNICA frontera de entrada al sistema
      "distribucion": "poisson",
      "lambda_por_hora": 40
    },
    "clientes_preferenciales": {                 // opcional: si falta, nadie es preferencial
      "proporcion": 0.2                          // 0.2 = 20 % de los clientes
    },
    "estacion_entrada": "triaje"                 // obligatoria en "secuencial"
  },

  "estaciones": [
    {
      "id": "triaje",
      "nombre": "Triaje inicial",                // opcional

      "servidores": [                            // cada servidor con su propio servicio
        {"id": "s1", "servicio": {"tipo": "exponencial", "media": 2}},
        {"id": "s2", "servicio": {"tipo": "uniforme", "min": 1, "max": 3}}
      ],
      // exponencial: {"tipo": "exponencial", "media": 2}
      // uniforme:    {"tipo": "uniforme", "min": 1, "max": 3}

      "colas": {
        "tipo": "multiple",                      // "unica" | "multiple" | "preferencial"
        "cantidad": 2,
        "reparticion": "mas_corta"               // solo "multiple": "round_robin" | "aleatoria" | "mas_corta"
      },

      "salidas": [                               // a dónde van los clientes al terminar aquí
        {"hacia": "medicina", "probabilidad": 0.6},
        {"hacia": "farmacia", "probabilidad": 0.4}
      ]                                          // lista vacía o ausente = salen del sistema
    }
    // ... estaciones "medicina" y "farmacia", con "salidas": []
  ]
}
```

En el método `paralelo` el JSON es más corto: una sola estación, sin
`estacion_entrada` y sin `salidas`. El ejemplo completo está en
`examples/configs_ejemplo/01_paralelo_cola_unica.json`.

### Cómo se comporta cada tipo de cola

El tipo de cola define quién atiende a quién. Dentro de cada cola el orden es
siempre FIFO (el primero en llegar es el primero en ser atendido).

| `tipo` | Colas | Qué ocurre |
|---|---|---|
| `unica` | 1 | Todos los servidores toman clientes de la misma cola. |
| `multiple` | k >= 2 | El cliente elige su cola al llegar según `reparticion` y no cambia de cola. Con varios servidores se exige k = número de servidores: la cola i la atiende el servidor i. Con un solo servidor, ese servidor atiende primero al cliente que lleva más tiempo esperando entre todas las colas. |
| `preferencial` | exactamente 2 | La cola 1 es preferencial y la cola 2 es normal. La clase del cliente decide su cola. Los servidores son compartidos y toman primero de la cola 1; la prioridad no interrumpe un servicio que ya empezó. |

`reparticion` (solo para `multiple`): `round_robin` reparte por turnos,
`aleatoria` elige al azar con igual probabilidad, `mas_corta` elige la cola con
menos clientes (en caso de empate, la de menor número).

Las 4 variantes de cada método se escriben así:

| Variante | Servidores | `colas` |
|---|---|---|
| Cola única, múltiples servidores | c | `unica`, cantidad 1 |
| Colas múltiples, múltiples servidores | c | `multiple`, cantidad c |
| Colas múltiples + preferenciales | c | `preferencial`, cantidad 2 |
| Colas múltiples, servidor único | 1 | `multiple`, cantidad >= 2 |

### Clientes preferenciales

Ser preferencial es una propiedad del **cliente**, no de la estación. El cliente
recibe su clase al llegar al sistema (con la `proporcion` definida en
`simulacion`) y la conserva en todas las estaciones. Cada estación solo decide
si la usa: una estación `preferencial` da prioridad; una `unica` o `multiple`
la ignora. Por eso el triaje puede ser común y la estación siguiente dar
prioridad.

### Rutas entre estaciones

`salidas` describe a dónde va el cliente al terminar en una estación. Es una
lista de `{hacia, probabilidad}`: la cadena lineal es el caso de una sola salida
con probabilidad 1, y una ramificación reparte según las probabilidades. Los
clientes solo avanzan hacia adelante: no se permiten ciclos.

### Reglas de validación

`src/config.py` las implementa en `validar_config(config)`, que devuelve una
lista de mensajes de error (vacía si la configuración es válida). Cualquier
configuración nueva, escrita a mano o generada por `topologias.py`, debe pasarla.

- Se rechaza cualquier clave que no esté en el contrato (detecta errores de
  escritura como `reparticon`).
- **Sistema:** `metodo` es `paralelo` o `secuencial`; `duracion_minutos` > 0;
  `semilla` es un entero si está; `llegada.distribucion` es `poisson` y
  `lambda_por_hora` > 0; `clientes_preferenciales.proporcion` está entre 0 y 1
  sin incluirlos.
- **Método `paralelo`:** exactamente 1 estación, sin `salidas`.
- **Método `secuencial`:** al menos 2 estaciones; `estacion_entrada` existe;
  las probabilidades de `salidas` de cada estación suman 1; todos los destinos
  existen; no hay ciclos; todas las estaciones se alcanzan desde la entrada.
- **Estaciones:** `id` de estación y de servidor son textos no vacíos y no se
  repiten (el de servidor, dentro de su estación); hay al menos 1 servidor.
- **Servicio:** `exponencial` con `media` > 0; `uniforme` con `min` >= 0,
  `max` > 0 y `min` < `max`.
- **Colas:** las reglas de la tabla anterior. Además, `preferencial` exige que
  `simulacion.clientes_preferenciales` esté definido.

### Por qué está estructurado así

- **`llegada` y `clientes_preferenciales` viven en `simulacion`.** El sistema
  tiene una sola frontera de entrada: los clientes nacen ahí, con su clase. Las
  estaciones no generan llegadas propias ni definen proporciones distintas.
- **`servidores` es una lista.** Cada servidor puede tener su propia
  distribución de servicio; los servidores idénticos son solo el caso en que se
  repite lo mismo.
- **El tipo de cola fija quién atiende a quién.** Así el motor no inventa reglas
  y los equipos no divergen.
- **`salidas` en lugar de una cadena fija.** La cadena lineal es un caso
  particular, y permitir ramificación ahora evita rehacer todos los ejemplos
  después.

### Lo que todavía no está en el contrato

Queda para cuando haga falta, y cada cosa se agrega como campo opcional:
`replicas` (varias corridas con distinta semilla) y `calentamiento_minutos`
(descartar el arranque con el sistema vacío), una advertencia cuando la llegada
supera la capacidad de atención (la cola crecería sin límite), y una capacidad
máxima de cola.

---

## 2. Contrato de salida (resultado)

```jsonc
{
  "resultado": {
    "simulacion_id": "banco_escenario_1",
    "duracion_total_minutos": 480,

    // DATOS CRUDOS: los produce el motor (Equipo 1). Un registro por cliente.
    "eventos_clientes": [
      {
        "cliente_id": 1,
        "es_preferencial": false,
        "tiempo_entrada_sistema": 2.3,   // único punto de entrada
        "tiempo_salida_sistema": 9.6,    // único punto de salida
        "paradas": [                     // 1 elemento en Método 1, 2 o más en Método 2
          {
            "estacion_id": "cajeros",
            "tiempo_inicio_espera": 2.3,
            "tiempo_inicio_servicio": 4.1,
            "tiempo_fin_servicio": 4.8,
            "servidor_asignado": 2,      // posición (1, 2, ...) en la lista "servidores"
            "cola_asignada": 1           // posición (1, 2, ...) entre las colas de la estación
          }
        ]
      }
    ],

    // RESUMEN: lo calcula metrics.py (Equipo 3); la interfaz solo lo muestra.
    "metricas": {
      "sistema_completo": {
        "tiempo_promedio_en_sistema": 5.2,    // promedio de (salida - entrada)
        "clientes_promedio_en_sistema": 4.1,
        "clientes_totales_atendidos": 351
      },
      "por_estacion": {
        "cajeros": {
          "tiempo_promedio_espera_cola": 1.8,
          "tiempo_promedio_atencion": 3.4,
          "longitud_promedio_cola": 2.3,
          "longitud_maxima_cola": 7,
          "por_servidor": {
            "servidor_1": {"utilizacion": 0.82, "tiempo_ocioso_minutos": 86.4, "clientes_atendidos": 118}
          },
          "por_cola": {
            "cola_1": {"longitud_promedio": 2.1, "longitud_maxima": 6}
          },
          "cola_mas_larga": "cola_1"
        }
      }
    }
  }
}
```

**Numeración:** `servidor_asignado = 2` y la clave `servidor_2` se refieren al
segundo servidor de la lista `servidores` de la configuración; `cola_asignada`
y `cola_N` siguen el mismo criterio. En una estación `preferencial`, la cola 1 es
la preferencial y la cola 2 la normal.

### Por qué está estructurado así

- **`tiempo_entrada_sistema` y `tiempo_salida_sistema` únicos por cliente.** El
  tiempo total en el sistema es `salida - entrada`, sin sumar por estación. Es
  el mismo principio del contrato de entrada: lo que pertenece al sistema
  completo se define una sola vez.
- **`paradas` es una lista que crece sola.** Con una estación tiene un elemento;
  con triaje más atención específica tiene dos. El motor no necesita lógica
  distinta por método: agrega una parada por cada estación que recorre el cliente.
- **`eventos_clientes` es la fuente de verdad; `metricas` es el resumen.** Si
  hace falta una métrica nueva, se calcula desde los datos crudos sin tocar el
  motor. La interfaz nunca debería calcular nada: si lo necesita, falta un campo
  en `metricas`.
- **Separación `sistema_completo` / `por_estacion`.** Distingue el tiempo total
  del cliente del rendimiento de una estación, que son preguntas distintas.
  `por_servidor` responde al rendimiento y la hora ociosa; `por_cola` y
  `cola_mas_larga` responden a cuál cola es mayor.

---

## Definiciones de métricas

- **Tiempo ocioso de un servidor:** `duracion_total_minutos` menos la suma de
  minutos que estuvo atendiendo.
- **Utilización:** `tiempo_ocupado / duracion_total_minutos`.
- **Clientes promedio en el sistema:** por la Ley de Little, `L = λ · W`,
  que también se puede verificar integrando el número de clientes en el tiempo.
