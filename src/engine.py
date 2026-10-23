"""
engine.py - Motor de simulación (SimPy).

Responsables: Equipo 1 (Engine). Revisa: Equipo 2 (Topologías).

Recibe una configuración (contrato de entrada) y devuelve los eventos de cada
cliente (contrato de salida). Debe funcionar para cualquier configuración,
sin saber qué variante de topología se está simulando. Las firmas de abajo
son una propuesta inicial: Equipo 1 puede ajustarlas por PR avisando a los
equipos que las consumen.
"""
from __future__ import annotations

import random
from typing import Any, Callable, Generator

import simpy


def generar_intervalo_llegada(
    lambda_por_hora: float,
    rng: random.Random | None = None
) -> float:
    """
    Genera el tiempo entre llegadas sucesivas (en minutos) para un proceso Poisson.

    En teoría de colas, si la tasa de llegadas es de λ clientes por hora,
    la tasa por minuto es λ_min = λ / 60. El intervalo entre llegadas
    sigue una distribución exponencial con media (60 / λ) minutos.

    Args:
        lambda_por_hora: tasa promedio de llegadas por hora (debe ser > 0).
        rng: generador de números aleatorios (instancia de random.Random opcional).
            Si no se proporciona, se usa el módulo random global.

    Returns:
        Tiempo en minutos hasta la siguiente llegada (float > 0).

    Raises:
        ValueError: si lambda_por_hora no es un número mayor que 0.
    """
    if lambda_por_hora <= 0:
        raise ValueError(
            f"lambda_por_hora debe ser mayor que 0, recibido: {lambda_por_hora!r}"
        )

    lambda_por_minuto = lambda_por_hora / 60.0
    generador = rng if rng is not None else random
    return generador.expovariate(lambda_por_minuto)


def determinar_es_preferencial(
    proporcion: float,
    rng: random.Random | None = None
) -> bool:
    """
    Determina si un cliente que llega al sistema pertenece a la clase preferencial.

    Args:
        proporcion: fracción entre 0.0 y 1.0 que indica la probabilidad
            de ser cliente preferencial.
        rng: generador de números aleatorios opcional.

    Returns:
        True si el cliente es preferencial, False de lo contrario.
    """
    if proporcion <= 0.0:
        return False
    if proporcion >= 1.0:
        return True

    generador = rng if rng is not None else random
    return generador.random() < proporcion


def crear_registro_cliente(
    cliente_id: int,
    tiempo_entrada: float,
    es_preferencial: bool
) -> dict[str, Any]:
    """
    Inicializa la estructura de datos de un cliente según el contrato de salida.

    Args:
        cliente_id: identificador numérico único (1-indexed).
        tiempo_entrada: instante de llegada al sistema en minutos.
        es_preferencial: indica si tiene condición de cliente preferencial.

    Returns:
        Diccionario con las claves requeridas por el contrato de salida:
        "cliente_id", "es_preferencial", "tiempo_entrada_sistema",
        "tiempo_salida_sistema" (inicialmente None) y "paradas" (lista vacía).
    """
    return {
        "cliente_id": cliente_id,
        "es_preferencial": es_preferencial,
        "tiempo_entrada_sistema": tiempo_entrada,
        "tiempo_salida_sistema": None,
        "paradas": [],
    }


def generador_llegadas(
    env: simpy.Environment,
    config_simulacion: dict,
    consumidor: Callable[[dict[str, Any]], Any] | None = None,
    registro_clientes: list[dict[str, Any]] | None = None,
    rng: random.Random | None = None,
) -> Generator[simpy.Event, None, None]:
    """
    Proceso SimPy que genera las llegadas de clientes al sistema.

    Modela la única frontera de entrada del sistema de colas. Genera llegadas
    siguiendo un proceso Poisson continuo hasta que la simulación termine.
    Por cada cliente generado, registra sus datos y notifica al consumidor
    (por ejemplo, la primera estación o cola del sistema).

    Args:
        env: entorno de simulación SimPy.
        config_simulacion: bloque "simulacion" del contrato de entrada.
            Contiene "llegada" (con "lambda_por_hora"), opcionalmente
            "clientes_preferenciales" (con "proporcion"), y "duracion_minutos".
        consumidor: función o callback que recibe el registro del cliente
            recién llegado para asignarlo a su primera estación/cola.
        registro_clientes: lista opcional donde se añaden cronológicamente
            todos los clientes nacidos en la simulación.
        rng: generador de números aleatorios opcional para reproducibilidad.

    Yields:
        simpy.Event (timeout) por cada lapso de espera entre llegadas consecutivas.
    """
    llegada_cfg = config_simulacion.get("llegada", {})
    lambda_por_hora = llegada_cfg.get("lambda_por_hora", 0)
    duracion = config_simulacion.get("duracion_minutos", float("inf"))

    preferenciales_cfg = config_simulacion.get("clientes_preferenciales")
    proporcion_pref = (
        preferenciales_cfg.get("proporcion", 0.0)
        if isinstance(preferenciales_cfg, dict)
        else 0.0
    )

    cliente_id = 1

    while env.now < duracion:
        delta_t = generar_intervalo_llegada(lambda_por_hora, rng=rng)
        yield env.timeout(delta_t)

        if env.now > duracion:
            break

        cliente = crear_registro_cliente(
            cliente_id=cliente_id,
            tiempo_entrada=env.now,
            es_preferencial=determinar_es_preferencial(proporcion_pref, rng=rng),
        )

        if registro_clientes is not None:
            registro_clientes.append(cliente)

        if consumidor is not None:
            consumidor(cliente)

        cliente_id += 1


def ejecutar_simulacion(config: dict) -> dict:
    """
    Corre una simulación completa de eventos discretos.

    Args:
        config: configuración válida según el contrato de entrada
            (docs/contratos.md). Incluye la llegada Poisson única en
            config["simulacion"]["llegada"].

    Returns:
        Diccionario con "simulacion_id", "duracion_total_minutos" y la lista
        "eventos_clientes" (un registro por cliente, con sus "paradas").
        Las métricas agregadas las calcula metrics.py, no el motor.
    """
    raise NotImplementedError(
        "Pendiente: Las estaciones y servidores están en construcción. "
        "El generador de llegadas Poisson ya está disponible en generador_llegadas()."
    )
