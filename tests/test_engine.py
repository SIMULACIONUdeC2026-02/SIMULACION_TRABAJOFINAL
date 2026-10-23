"""Pruebas de integración del motor de la primera entrega."""
import json
import random
from pathlib import Path

import pytest
from src.engine import ejecutar_simulacion


@pytest.fixture
def config():
    """Devuelve una copia del ejemplo compartido por los equipos."""
    ruta = Path(__file__).resolve().parents[1] / 'examples/configs_ejemplo/01_paralelo_cola_unica.json'
    return json.loads(ruta.read_text(encoding='utf-8'))


def test_contrato_fifo_y_servidores_sin_solapamientos(config):
    """Comprueba eventos completos, capacidad, orden FIFO y tiempos consistentes."""
    resultado = ejecutar_simulacion(config)
    eventos = resultado['eventos_clientes']
    assert eventos
    assert set(resultado) == {'simulacion_id', 'duracion_total_minutos', 'eventos_clientes'}
    inicios = []
    finales = {}
    for numero, cliente in enumerate(eventos, 1):
        assert cliente['cliente_id'] == numero
        assert cliente['es_preferencial'] is False
        assert len(cliente['paradas']) == 1
        parada = cliente['paradas'][0]
        entrada = cliente['tiempo_entrada_sistema']
        inicio = parada['tiempo_inicio_servicio']
        fin = parada['tiempo_fin_servicio']
        servidor = parada['servidor_asignado']
        assert 0 <= entrada < config['simulacion']['duracion_minutos']
        assert entrada == parada['tiempo_inicio_espera'] <= inicio < fin
        assert fin == cliente['tiempo_salida_sistema'] <= resultado['duracion_total_minutos']
        assert 1 <= servidor <= len(config['estaciones'][0]['servidores'])
        assert parada['cola_asignada'] == 1
        assert parada['estacion_id'] == 'cajeros'
        assert inicio >= finales.get(servidor, 0)
        finales[servidor] = fin
        inicios.append(inicio)
    assert inicios == sorted(inicios)
    assert len(finales) == len(config['estaciones'][0]['servidores'])


def test_semilla_reproducible_sin_alterar_random_global(config):
    """Comprueba que la semilla reproduce resultados y mantiene el azar global."""
    estado = random.getstate()
    assert ejecutar_simulacion(config) == ejecutar_simulacion(config)
    assert random.getstate() == estado


def test_vaciado_y_servicio_uniforme(config):
    """Comprueba que servicios largos terminan después del cierre de llegadas."""
    config['simulacion'].update(duracion_minutos=1)
    config['simulacion']['llegada']['lambda_por_hora'] = 600
    for srv in config['estaciones'][0]['servidores']:
        srv['servicio'] = {'tipo': 'uniforme', 'min': 9.999, 'max': 10.001}
    resultado = ejecutar_simulacion(config)
    assert resultado['duracion_total_minutos'] > 1
    for evento in resultado['eventos_clientes']:
        parada = evento['paradas'][0]
        assert parada['tiempo_fin_servicio'] - parada['tiempo_inicio_servicio'] == pytest.approx(10, abs=0.01)
    assert any(e['paradas'][0]['tiempo_inicio_servicio'] > e['tiempo_entrada_sistema'] for e in resultado['eventos_clientes'])


def test_sin_llegadas(config):
    """Comprueba un horizonte tan corto que no llega ningún cliente con semilla 42."""
    config['simulacion']['duracion_minutos'] = 1e-12
    resultado = ejecutar_simulacion(config)
    assert resultado['eventos_clientes'] == []
    assert resultado['duracion_total_minutos'] == 1e-12


@pytest.mark.parametrize('valor', [0, -1, float('nan'), float('inf'), True])
def test_tasa_invalida(config, valor):
    """Rechaza tasas que no permiten un proceso de llegadas válido."""
    config['simulacion']['llegada']['lambda_por_hora'] = valor
    with pytest.raises(ValueError):
        ejecutar_simulacion(config)


def test_variante_pendiente():
    """Rechaza explícitamente variantes fuera de la primera entrega con un ejemplo secuencial real."""
    ruta = Path(__file__).resolve().parents[1] / 'examples/configs_ejemplo/05_secuencial_cola_unica.json'
    config_secuencial = json.loads(ruta.read_text(encoding='utf-8'))
    with pytest.raises(NotImplementedError):
        ejecutar_simulacion(config_secuencial)


def test_config_incompleta():
    """Expone un error claro cuando falta el contrato de entrada."""
    with pytest.raises(ValueError):
        ejecutar_simulacion({})
