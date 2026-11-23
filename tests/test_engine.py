"""Pruebas de integración del motor de simulación."""
import json
import random
from pathlib import Path

import pytest
from src.engine import ejecutar_simulacion


@pytest.fixture
def config():
    """Devuelve una copia del ejemplo compartido por los equipos (método paralelo)."""
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


def test_secuencial_cola_unica_dos_estaciones():
    """Comprueba simulación secuencial con múltiples estaciones (ejemplo 05)."""
    ruta = Path(__file__).resolve().parents[1] / 'examples/configs_ejemplo/05_secuencial_cola_unica.json'
    config_secuencial = json.loads(ruta.read_text(encoding='utf-8'))
    resultado = ejecutar_simulacion(config_secuencial)

    eventos = resultado['eventos_clientes']
    assert len(eventos) > 0
    assert resultado['duracion_total_minutos'] >= config_secuencial['simulacion']['duracion_minutos']

    for cliente in eventos:
        assert len(cliente['paradas']) == 2
        p1, p2 = cliente['paradas']
        assert p1['estacion_id'] == 'triaje'
        assert p2['estacion_id'] == 'atencion'
        assert cliente['tiempo_entrada_sistema'] == p1['tiempo_inicio_espera']
        assert cliente['tiempo_salida_sistema'] == p2['tiempo_fin_servicio']
        assert p1['tiempo_fin_servicio'] <= p2['tiempo_inicio_espera']
        for p in (p1, p2):
            assert p['tiempo_inicio_espera'] <= p['tiempo_inicio_servicio'] <= p['tiempo_fin_servicio']
            assert p['cola_asignada'] == 1


def test_variantes_pendientes_etapa_2_y_3():
    """Verifica que colas múltiples y preferenciales señalen que están pendientes."""
    ruta_base = Path(__file__).resolve().parents[1] / 'examples/configs_ejemplo'

    # Ejemplo 02: colas múltiples
    cfg_multiples = json.loads((ruta_base / '02_paralelo_colas_multiples.json').read_text(encoding='utf-8'))
    with pytest.raises(NotImplementedError, match='tipo de cola'):
        ejecutar_simulacion(cfg_multiples)

    # Ejemplo 03: preferenciales
    cfg_pref = json.loads((ruta_base / '03_paralelo_preferencial.json').read_text(encoding='utf-8'))
    with pytest.raises(NotImplementedError, match='preferenciales'):
        ejecutar_simulacion(cfg_pref)


def test_ejercicio_5_12_convergencia_teorica():
    """Valida el criterio del ejercicio 5.12 contra los valores teóricos.

    Teoría:
    - Estación 1 (M/M/1): W1 = 6.00 min, Lq1 = 4/3 ≈ 1.3333
    - Estación 2 (M/G/1 uniforme [1,2]): W2 = 41/18 ≈ 2.2778 min, Lq2 = 7/27 ≈ 0.2593
    - Sistema completo: W ≈ 8.2778 min
    - Lq1 > Lq2 (la cola de la estación 1 es la mayor)
    """
    config_512 = {
        'simulacion': {
            'nombre': 'Ejercicio 5.12 - Dos estaciones en serie',
            'metodo': 'secuencial',
            'duracion_minutos': 200000,
            'semilla': 12345,
            'llegada': {
                'distribucion': 'poisson',
                'lambda_por_hora': 20,
            },
            'estacion_entrada': 'estacion_1',
        },
        'estaciones': [
            {
                'id': 'estacion_1',
                'nombre': 'Primera estación (M/M/1)',
                'servidores': [
                    {'id': 's1_1', 'servicio': {'tipo': 'exponencial', 'media': 2}},
                ],
                'colas': {
                    'tipo': 'unica',
                    'cantidad': 1,
                },
                'salidas': [
                    {'hacia': 'estacion_2', 'probabilidad': 1.0},
                ],
            },
            {
                'id': 'estacion_2',
                'nombre': 'Segunda estación (M/G/1 uniforme)',
                'servidores': [
                    {'id': 's2_1', 'servicio': {'tipo': 'uniforme', 'min': 1, 'max': 2}},
                ],
                'colas': {
                    'tipo': 'unica',
                    'cantidad': 1,
                },
                'salidas': [],
            },
        ],
    }

    resultado = ejecutar_simulacion(config_512)
    eventos = resultado['eventos_clientes']
    duracion = resultado['duracion_total_minutos']

    assert len(eventos) > 5000

    tiempos_sistema = [c['tiempo_salida_sistema'] - c['tiempo_entrada_sistema'] for c in eventos]
    w_sistema = sum(tiempos_sistema) / len(tiempos_sistema)

    t_est1 = [c['paradas'][0]['tiempo_fin_servicio'] - c['paradas'][0]['tiempo_inicio_espera'] for c in eventos]
    w1 = sum(t_est1) / len(t_est1)

    t_cola1 = [c['paradas'][0]['tiempo_inicio_servicio'] - c['paradas'][0]['tiempo_inicio_espera'] for c in eventos]
    wq1 = sum(t_cola1) / len(t_cola1)

    t_est2 = [c['paradas'][1]['tiempo_fin_servicio'] - c['paradas'][1]['tiempo_inicio_espera'] for c in eventos]
    w2 = sum(t_est2) / len(t_est2)

    t_cola2 = [c['paradas'][1]['tiempo_inicio_servicio'] - c['paradas'][1]['tiempo_inicio_espera'] for c in eventos]
    wq2 = sum(t_cola2) / len(t_cola2)

    lam_efectiva = len(eventos) / duracion
    lq1 = lam_efectiva * wq1
    lq2 = lam_efectiva * wq2

    # Verificaciones contra la teoría (con margen de tolerancia estadística < 5%)
    assert w_sistema == pytest.approx(8.28, rel=0.05)
    assert w1 == pytest.approx(6.00, rel=0.05)
    assert w2 == pytest.approx(2.28, rel=0.05)
    assert lq1 == pytest.approx(1.33, rel=0.07)
    assert lq2 == pytest.approx(0.26, rel=0.07)

    # La cola de la estación 1 es la mayor
    assert lq1 > lq2


def test_config_incompleta():
    """Expone un error claro cuando falta el contrato de entrada."""
    with pytest.raises(ValueError):
        ejecutar_simulacion({})
