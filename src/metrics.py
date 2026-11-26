"""
metrics.py - Cálculo de métricas a partir de los eventos de los clientes.

Responsables: Equipo 3 (Métricas). Revisa: Equipo 4 (UI).

Toma "eventos_clientes" (contrato de salida) y calcula el bloque "metricas":
tiempo promedio en el sistema, clientes promedio (Ley de Little), cola más
larga, utilización y tiempo ocioso por servidor, tiempo promedio de atención.
No depende de SimPy: se puede desarrollar con datos de ejemplo.

Supuestos (a confirmar con Engine, Issue #5):
- Un cliente que sigue dentro del sistema al terminar la simulación trae
  "tiempo_salida_sistema": None. No cuenta como atendido.
- Un servicio que no terminó trae "tiempo_fin_servicio": None.

Regla de corte en T = duracion_total_minutos:
- "Atendido" = salió del sistema dentro de la simulación (salida <= T).
  Un cliente que sale después de T se trata igual que uno que sigue dentro:
  no cuenta como atendido ni entra en W ni en la Ley de Little.
- Las métricas que suman tiempo (integración de N(t), ocupación de
  servidores) recortan cada intervalo a [0, T].
Vocabulario (igual que el contrato y el motor):
- estación: se identifica con su "id" de texto en la config
  (parada["estacion_id"], clave de "por_estacion"), p. ej. "cajeros".
- servidor: se identifica con su posición 1, 2, ... en la lista "servidores"
  de la estación (parada["servidor_asignado"], clave "servidor_N"). No se usa
  el "id" de texto del servidor de la config.
Las fórmulas están explicadas en docs/metricas.md.
"""


# --------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------

def clientes_atendidos(eventos_clientes: list[dict],
                       duracion_total_minutos: float) -> list[dict]:
    """
    Filtra los clientes que salieron del sistema antes de terminar la simulación.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        Los clientes cuyo "tiempo_salida_sistema" no es None y es <= T.
    """
    _validar_duracion(duracion_total_minutos)
    return [c for c in eventos_clientes
            if c.get("tiempo_salida_sistema") is not None
            and c["tiempo_salida_sistema"] <= duracion_total_minutos]


def tiempo_en_sistema(cliente: dict) -> float:
    """
    Tiempo total de un cliente en el sistema: salida - entrada.

    Args:
        cliente: un elemento de eventos_clientes que ya salió del sistema.

    Returns:
        Minutos entre su entrada y su salida.
    """
    return cliente["tiempo_salida_sistema"] - cliente["tiempo_entrada_sistema"]


def _validar_duracion(duracion_total_minutos: float) -> None:
    """Lanza ValueError si la duración no es un número mayor que 0."""
    if (isinstance(duracion_total_minutos, bool)
            or not isinstance(duracion_total_minutos, (int, float))
            or duracion_total_minutos <= 0):
        raise ValueError(
            "duracion_total_minutos debe ser un número mayor que 0, "
            f"recibido {duracion_total_minutos!r}"
        )


def _minutos_dentro(inicio: float, fin, duracion_total_minutos: float) -> float:
    """
    Minutos del intervalo [inicio, fin] que caen dentro de [0, duración].

    Args:
        inicio: instante de inicio.
        fin: instante de fin; None significa "no terminó" (se toma la duración).
        duracion_total_minutos: fin de la simulación.

    Returns:
        Longitud del intervalo recortado (0.0 si queda fuera).
    """
    if fin is None:
        fin = duracion_total_minutos
    inicio = max(inicio, 0.0)
    fin = min(fin, duracion_total_minutos)
    return max(fin - inicio, 0.0)


# --------------------------------------------------------------------------
# Sistema completo (Issues #13 y #14)
# --------------------------------------------------------------------------

def clientes_totales_atendidos(eventos_clientes: list[dict],
                               duracion_total_minutos: float) -> int:
    """
    Cuenta los clientes que completaron su paso por el sistema antes de T.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        Número de clientes con "tiempo_salida_sistema" definido y <= T.
    """
    return len(clientes_atendidos(eventos_clientes, duracion_total_minutos))


def tiempo_promedio_en_sistema(eventos_clientes: list[dict],
                               duracion_total_minutos: float) -> float:
    """
    Tiempo promedio en el sistema (W) de los clientes atendidos.

    W = promedio de (tiempo_salida_sistema - tiempo_entrada_sistema) de los
    clientes que salieron antes de T. Su tiempo no se recorta: es el tiempo
    real que pasaron en el sistema.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        W en minutos. 0.0 si ningún cliente salió del sistema antes de T.
    """
    atendidos = clientes_atendidos(eventos_clientes, duracion_total_minutos)
    if not atendidos:
        return 0.0
    return sum(tiempo_en_sistema(c) for c in atendidos) / len(atendidos)


def clientes_promedio_en_sistema(eventos_clientes: list[dict],
                                 duracion_total_minutos: float) -> float:
    """
    Número promedio de clientes en el sistema (L) por la Ley de Little.

    L = λ · W, con λ = clientes atendidos / duración (clientes por minuto)
    y W = tiempo promedio en el sistema. Solo usa a los que salieron antes
    de T (ver clientes_atendidos).

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        duracion_total_minutos: duración simulada, mayor que 0.

    Returns:
        L (clientes). 0.0 si ningún cliente salió del sistema.
    """
    _validar_duracion(duracion_total_minutos)
    tasa = (clientes_totales_atendidos(eventos_clientes, duracion_total_minutos)
            / duracion_total_minutos)
    return tasa * tiempo_promedio_en_sistema(eventos_clientes,
                                             duracion_total_minutos)


def clientes_promedio_por_integracion(eventos_clientes: list[dict],
                                      duracion_total_minutos: float) -> float:
    """
    Número promedio de clientes en el sistema integrando N(t) en el tiempo.

    L = (1 / T) · ∫ N(t) dt, sobre [0, T]. Sirve para verificar la Ley de
    Little: si todos los clientes entran y salen dentro de [0, T], coincide
    con clientes_promedio_en_sistema. Incluye a los que no alcanzaron a salir
    antes de T, contando solo los minutos que estuvieron dentro de [0, T].

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        L (clientes) promediado en el tiempo.
    """
    _validar_duracion(duracion_total_minutos)
    area = sum(
        _minutos_dentro(c["tiempo_entrada_sistema"],
                        c.get("tiempo_salida_sistema"),
                        duracion_total_minutos)
        for c in eventos_clientes
    )
    return area / duracion_total_minutos

# --------------------------------------------------------------------------
# Por estacion y por servidor (Issue #15)
# --------------------------------------------------------------------------
def paradas_por_estacion(eventos_clientes: list[dict], estacion_id: str) -> list[dict]:
    """
    Reúne las paradas de todos los clientes en una estación.

    Args:
        eventos_clientes: la lista de eventos de clientes.
        estacion_id: el "id" de texto de la estación a filtrar.

    Returns:
        Lista de paradas (contrato de salida) cuyo "estacion_id" coincide.
    """
    return [p for cliente in eventos_clientes
            for p in cliente.get("paradas", [])
            if p.get("estacion_id") == estacion_id]


def calculo_ocioso_servidor(eventos_clientes: list[dict], estacion_id: str,
                            servidor: int,
                            duracion_total_minutos: float) -> dict:
    """
    Utilización y tiempo ocioso de un servidor de una estación.

    El tiempo ocioso es la suma de los tiempos muertos del servidor: desde 0
    hasta su primer inicio de servicio, entre el fin de un servicio y el inicio
    del siguiente (espera por la llegada del próximo cliente) y desde su último
    fin de servicio hasta T. Equivale a T menos los minutos atendiendo.
    Los intervalos se recortan a [0, T]; un servicio sin fin cuenta hasta T.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        estacion_id: "id" de texto de la estación.
        servidor: posición del servidor (1, 2, ...) en la lista "servidores"
            de esa estación; es el valor de "servidor_asignado" en las paradas.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        {"utilizacion", "tiempo_ocioso_minutos", "clientes_atendidos"},
        la forma de una entrada de "por_servidor" en el contrato.
    """
    _validar_duracion(duracion_total_minutos)
    T = duracion_total_minutos
    servicios = sorted(
        (p for p in paradas_por_estacion(eventos_clientes, estacion_id)
         if p.get("servidor_asignado") == servidor
         and p.get("tiempo_inicio_servicio") is not None),
        key=lambda p: p["tiempo_inicio_servicio"],
    )

    ocioso = 0.0
    cursor = 0.0  # instante hasta el que el servidor ya está contabilizado
    atendidos = 0
    for p in servicios:
        inicio = max(p["tiempo_inicio_servicio"], 0.0)
        fin = p.get("tiempo_fin_servicio")
        fin = T if fin is None else min(fin, T)
        if inicio >= T:
            break
        if inicio > cursor:
            ocioso += inicio - cursor  # tiempo muerto antes de este servicio
        cursor = max(cursor, fin)
        if p.get("tiempo_fin_servicio") is not None and p["tiempo_fin_servicio"] <= T:
            atendidos += 1
    ocioso += max(T - cursor, 0.0)  # tiempo muerto final

    return {
        "utilizacion": (T - ocioso) / T,
        "tiempo_ocioso_minutos": ocioso,
        "clientes_atendidos": atendidos,
    }


def calculo_ocioso_estacion(eventos_clientes: list[dict], config: dict,
                            estacion_id: str,
                            duracion_total_minutos: float) -> dict:
    """
    Tiempo ocioso y utilización de todos los servidores de una estación.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        config: configuración usada (da la lista "servidores" de la estación).
        estacion_id: "id" de texto de la estación.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        El bloque "por_servidor" del contrato:
        {"servidor_1": {...}, "servidor_2": {...}, ...}, donde N es la posición
        del servidor en la estación. Incluye también a los servidores que no atendieron a nadie (ociosos todo el tiempo).

    Raises:
        ValueError: si la estación no existe en la configuración.
    """
    estacion = next((e for e in config.get("estaciones", [])
                     if e.get("id") == estacion_id), None)
    if estacion is None:
        raise ValueError(f"La estación {estacion_id!r} no existe en la configuración")
    return {
        f"servidor_{i}": calculo_ocioso_servidor(
            eventos_clientes, estacion_id, i, duracion_total_minutos)
        for i in range(1, len(estacion.get("servidores", [])) + 1)
    }



# --------------------------------------------------------------------------
# Longitud de las colas (Issue #16)
#
# Una cola se identifica con (estacion_id, cola_asignada). Un cliente está en
# esa cola desde "tiempo_inicio_espera" hasta "tiempo_inicio_servicio".
# Lq(t) = clientes esperando en la cola en el instante t.
# --------------------------------------------------------------------------

def _buscar_estacion(config: dict, estacion_id: str) -> dict:
    """
    Busca una estación de la configuración por su "id".

    Args:
        config: configuración según el contrato de entrada.
        estacion_id: "id" de texto de la estación.

    Returns:
        El diccionario de la estación.

    Raises:
        ValueError: si la estación no existe en la configuración.
    """
    estacion = next((e for e in config.get("estaciones", [])
                     if e.get("id") == estacion_id), None)
    if estacion is None:
        raise ValueError(f"La estación {estacion_id!r} no existe en la configuración")
    return estacion


def _intervalos_en_cola(paradas: list[dict],
                        duracion_total_minutos: float) -> list[tuple[float, float]]:
    """
    Intervalos de tiempo en que cada parada estuvo esperando en cola.

    Cada intervalo es [tiempo_inicio_espera, tiempo_inicio_servicio], recortado
    a [0, T]. Si el cliente sigue en cola al final (inicio de servicio None),
    cuenta hasta T. Los clientes que no esperaron (intervalo de largo 0) no
    aparecen.

    Args:
        paradas: paradas de una cola (contrato de salida).
        duracion_total_minutos: duración simulada (T).

    Returns:
        Lista de tuplas (inicio, fin) con fin > inicio.
    """
    intervalos = []
    for p in paradas:
        inicio = max(p["tiempo_inicio_espera"], 0.0)
        fin = p.get("tiempo_inicio_servicio")
        fin = duracion_total_minutos if fin is None else min(fin, duracion_total_minutos)
        if fin > inicio:
            intervalos.append((inicio, fin))
    return intervalos


def _maximo_simultaneo(intervalos: list[tuple[float, float]]) -> int:
    """
    Mayor cantidad de intervalos abiertos al mismo tiempo.

    Recorre los cambios en orden de tiempo: +1 cuando un cliente entra a la
    cola y -1 cuando pasa a servicio. En un empate de tiempos primero sale el
    que pasa a servicio y luego entra el que llega (el -1 va antes del +1).

    Args:
        intervalos: lista de tuplas (inicio, fin).

    Returns:
        Longitud máxima de la cola (0 si no hay intervalos).
    """
    cambios = sorted([(fin, -1) for _, fin in intervalos]
                     + [(inicio, 1) for inicio, _ in intervalos])
    actual = maximo = 0
    for _, cambio in cambios:
        actual += cambio
        maximo = max(maximo, actual)
    return maximo


def longitud_cola(eventos_clientes: list[dict], estacion_id: str, cola: int,
                  duracion_total_minutos: float) -> dict:
    """
    Longitud promedio y máxima de una cola de una estación.

    La longitud promedio es en el tiempo: (1 / T) · ∫ Lq(t) dt sobre [0, T],
    igual que clientes_promedio_por_integracion pero con el tiempo en cola.
    La integral es la suma de los minutos que cada cliente esperó.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        estacion_id: "id" de texto de la estación.
        cola: posición de la cola (1, 2, ...); es el valor de "cola_asignada".
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        {"longitud_promedio", "longitud_maxima"}, la forma de una entrada de
        "por_cola" en el contrato.
    """
    _validar_duracion(duracion_total_minutos)
    paradas = [p for p in paradas_por_estacion(eventos_clientes, estacion_id)
               if p.get("cola_asignada") == cola]
    intervalos = _intervalos_en_cola(paradas, duracion_total_minutos)
    area = sum(fin - inicio for inicio, fin in intervalos)
    return {
        "longitud_promedio": area / duracion_total_minutos,
        "longitud_maxima": _maximo_simultaneo(intervalos),
    }


def metricas_por_cola(eventos_clientes: list[dict], config: dict,
                      estacion_id: str, duracion_total_minutos: float) -> dict:
    """
    Longitud promedio y máxima de todas las colas de una estación.

    Sirve para todos los tipos de cola: "unica" (cola_1), "multiple"
    (cola_1 ... cola_k) y "preferencial" (cola_1 = preferenciales,
    cola_2 = normales).

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        config: configuración usada (da "colas.cantidad" de la estación).
        estacion_id: "id" de texto de la estación.
        duracion_total_minutos: duración simulada (T), mayor que 0.

    Returns:
        El bloque "por_cola" del contrato: {"cola_1": {...}, "cola_2": {...}},
        con una entrada por cada cola de la configuración, aunque esté vacía.

    Raises:
        ValueError: si la estación no existe en la configuración.
    """
    estacion = _buscar_estacion(config, estacion_id)
    cantidad = estacion.get("colas", {}).get("cantidad", 1)
    return {
        f"cola_{i}": longitud_cola(eventos_clientes, estacion_id, i,
                                   duracion_total_minutos)
        for i in range(1, cantidad + 1)
    }


# --------------------------------------------------------------------------
# Resumen completo (se completa con los Issues #16 y #17)
# --------------------------------------------------------------------------

def calcular_metricas(eventos_clientes: list[dict], config: dict,
                      duracion_total_minutos: float) -> dict:
    """
    Calcula las métricas del sistema completo y de cada estación.

    Args:
        eventos_clientes: un dict por cliente, con tiempo_entrada_sistema,
            tiempo_salida_sistema y la lista "paradas".
        config: la configuración usada (sirve para saber servidores y colas).
        duracion_total_minutos: duración simulada, necesaria para utilización
            y tiempo ocioso.

    Returns:
        Diccionario "metricas" con "sistema_completo" y "por_estacion",
        según docs/contratos.md.
    """
    raise NotImplementedError(
        "Pendiente: Equipo 3 (longitud de colas #16 y resumen completo #17)"
    )
