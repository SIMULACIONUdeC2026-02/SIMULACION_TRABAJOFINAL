"""Pruebas del motor. Responsables: Equipo 1 (Engine)."""
import random

import pytest
import simpy

from src import engine


def test_generar_intervalo_llegada_valida_lambda_positivo():
    """Lanza ValueError si lambda_por_hora no es estrictamente positivo."""
    with pytest.raises(ValueError):
        engine.generar_intervalo_llegada(0)
    with pytest.raises(ValueError):
        engine.generar_intervalo_llegada(-10)


def test_generar_intervalo_llegada_promedio():
    """
    Verifica que la media muestral de los intervalos converja a 60 / lambda.
    Para lambda = 60 clientes/hora, la media esperada es 1.0 minuto.
    """
    rng = random.Random(42)
    n = 10000
    intervalos = [engine.generar_intervalo_llegada(60, rng=rng) for _ in range(n)]
    media = sum(intervalos) / n
    assert media == pytest.approx(1.0, rel=0.05)


def test_determinar_es_preferencial():
    """Verifica asignación de clase preferencial según la proporción configurada."""
    rng = random.Random(123)
    # Proporción 0.0 -> ningún cliente preferencial
    assert not any(engine.determinar_es_preferencial(0.0, rng=rng) for _ in range(100))
    # Proporción 1.0 -> todos preferenciales
    assert all(engine.determinar_es_preferencial(1.0, rng=rng) for _ in range(100))

    # Proporción 0.3 -> aproximadamente 30%
    n = 2000
    conteo = sum(engine.determinar_es_preferencial(0.3, rng=rng) for _ in range(n))
    assert (conteo / n) == pytest.approx(0.3, abs=0.03)


def test_crear_registro_cliente_formato_contrato():
    """Verifica que el registro de cliente cumpla las claves del contrato de salida."""
    cliente = engine.crear_registro_cliente(1, 4.5, es_preferencial=True)
    assert set(cliente.keys()) == {
        "cliente_id",
        "es_preferencial",
        "tiempo_entrada_sistema",
        "tiempo_salida_sistema",
        "paradas",
    }
    assert cliente["cliente_id"] == 1
    assert cliente["es_preferencial"] is True
    assert cliente["tiempo_entrada_sistema"] == 4.5
    assert cliente["tiempo_salida_sistema"] is None
    assert cliente["paradas"] == []


def test_generador_llegadas_proceso_simpy():
    """
    Verifica que el proceso SimPy genere llegadas cronológicas respetando la duración.
    """
    env = simpy.Environment()
    config_simulacion = {
        "duracion_minutos": 120,
        "llegada": {"distribucion": "poisson", "lambda_por_hora": 30},
        "clientes_preferenciales": {"proporcion": 0.25},
    }
    registro = []
    rng = random.Random(42)

    env.process(
        engine.generador_llegadas(
            env,
            config_simulacion,
            registro_clientes=registro,
            rng=rng,
        )
    )
    env.run(until=120)

    # Para lambda = 30 clientes/hora en 2 horas (120 min), esperamos ~60 llegadas
    assert len(registro) > 0
    assert 40 <= len(registro) <= 80

    for i, c in enumerate(registro, start=1):
        assert c["cliente_id"] == i
        assert isinstance(c["es_preferencial"], bool)
        assert 0.0 <= c["tiempo_entrada_sistema"] <= 120.0
        assert c["tiempo_salida_sistema"] is None
        assert c["paradas"] == []

    # Verificar orden estrictamente cronológico de llegadas
    tiempos = [c["tiempo_entrada_sistema"] for c in registro]
    assert tiempos == sorted(tiempos)


def test_generador_llegadas_reproducibilidad_con_semilla():
    """Verifica que con la misma semilla se produzcan exactamente los mismos clientes y tiempos."""
    def simular(semilla: int):
        env = simpy.Environment()
        cfg = {
            "duracion_minutos": 60,
            "llegada": {"distribucion": "poisson", "lambda_por_hora": 40},
        }
        registro = []
        rng = random.Random(semilla)
        env.process(engine.generador_llegadas(env, cfg, registro_clientes=registro, rng=rng))
        env.run(until=60)
        return registro

    corrida1 = simular(999)
    corrida2 = simular(999)
    corrida_distinta = simular(888)

    assert corrida1 == corrida2
    assert corrida1 != corrida_distinta


def test_generador_llegadas_notifica_consumidor():
    """Verifica que el callback consumidor sea invocado por cada cliente llegado."""
    env = simpy.Environment()
    cfg = {
        "duracion_minutos": 30,
        "llegada": {"distribucion": "poisson", "lambda_por_hora": 20},
    }
    recibidos = []

    def consumidor(cliente):
        recibidos.append(cliente["cliente_id"])

    env.process(engine.generador_llegadas(env, cfg, consumidor=consumidor, rng=random.Random(1)))
    env.run(until=30)

    assert len(recibidos) > 0
    assert recibidos == list(range(1, len(recibidos) + 1))
