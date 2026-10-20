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
- Todo tiempo se recorta al intervalo [0, duracion_total_minutos].
Las fórmulas están explicadas en docs/metricas.md.
"""


# --------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------

def clientes_atendidos(eventos_clientes: list[dict]) -> list[dict]:
    """
    Filtra los clientes que salieron del sistema.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.

    Returns:
        Los clientes cuyo "tiempo_salida_sistema" no es None.
    """
    return [c for c in eventos_clientes
            if c.get("tiempo_salida_sistema") is not None]


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

def clientes_totales_atendidos(eventos_clientes: list[dict]) -> int:
    """
    Cuenta los clientes que completaron su paso por el sistema.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.

    Returns:
        Número de clientes con "tiempo_salida_sistema" definido.
    """
    return len(clientes_atendidos(eventos_clientes))


def tiempo_promedio_en_sistema(eventos_clientes: list[dict]) -> float:
    """
    Tiempo promedio en el sistema (W) de los clientes atendidos.

    W = promedio de (tiempo_salida_sistema - tiempo_entrada_sistema).

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.

    Returns:
        W en minutos. 0.0 si ningún cliente salió del sistema.
    """
    atendidos = clientes_atendidos(eventos_clientes)
    if not atendidos:
        return 0.0
    return sum(tiempo_en_sistema(c) for c in atendidos) / len(atendidos)


def clientes_promedio_en_sistema(eventos_clientes: list[dict],
                                 duracion_total_minutos: float) -> float:
    """
    Número promedio de clientes en el sistema (L) por la Ley de Little.

    L = λ · W, con λ = clientes atendidos / duración (clientes por minuto)
    y W = tiempo promedio en el sistema.

    Args:
        eventos_clientes: lista de eventos según el contrato de salida.
        duracion_total_minutos: duración simulada, mayor que 0.

    Returns:
        L (clientes). 0.0 si ningún cliente salió del sistema.
    """
    _validar_duracion(duracion_total_minutos)
    tasa = clientes_totales_atendidos(eventos_clientes) / duracion_total_minutos
    return tasa * tiempo_promedio_en_sistema(eventos_clientes)


def clientes_promedio_por_integracion(eventos_clientes: list[dict],
                                      duracion_total_minutos: float) -> float:
    """
    Número promedio de clientes en el sistema integrando N(t) en el tiempo.

    L = (1 / T) · ∫ N(t) dt, sobre [0, T]. Sirve para verificar la Ley de
    Little: si todos los clientes entran y salen dentro de [0, T], coincide
    con clientes_promedio_en_sistema. Incluye a los que no alcanzaron a salir.

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
