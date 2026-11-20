"""Pruebas de integración del motor de simulación."""
import json
import random
from pathlib import Path

import pytest
from src.contrato_salida import validar_resultado
from src.engine import ejecutar_simulacion

CARPETA_EJEMPLOS = Path(__file__).resolve().parents[1] / 'examples/configs_ejemplo'


def _cargar_ejemplo(nombre_archivo: str) -> dict:
    """Carga un archivo JSON de examples/configs_ejemplo."""
    return json.loads((CARPETA_EJEMPLOS / nombre_archivo).read_text(encoding='utf-8'))


@pytest.fixture
def config():
    """Devuelve una copia del ejemplo compartido por los equipos (método paralelo)."""
    return _cargar_ejemplo('01_paralelo_cola_unica.json')


def test_contrato_fifo_y_servidores_sin_solapamientos(config):
    """Comprueba eventos completos, capacidad, orden FIFO y tiempos consistentes."""
    resultado = ejecutar_simulacion(config)
    assert validar_resultado(resultado, config) == []
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
    config_secuencial = _cargar_ejemplo('05_secuencial_cola_unica.json')
    resultado = ejecutar_simulacion(config_secuencial)
    assert validar_resultado(resultado, config_secuencial) == []

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


def test_colas_multiples_round_robin_paralelo():
    """Comprueba reparto round_robin y asignación 1-a-1 servidor-cola (ejemplo 02)."""
    cfg = _cargar_ejemplo('02_paralelo_colas_multiples.json')
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    assert resultado == ejecutar_simulacion(cfg)

    eventos = resultado['eventos_clientes']
    assert len(eventos) >= 6

    inicios_por_cola = {1: [], 2: [], 3: []}
    finales_por_servidor = {}
    for idx, cliente in enumerate(eventos):
        parada = cliente['paradas'][0]
        cola_esperada = (idx % 3) + 1
        assert parada['cola_asignada'] == cola_esperada
        assert parada['servidor_asignado'] == cola_esperada
        assert parada['tiempo_inicio_servicio'] >= finales_por_servidor.get(cola_esperada, 0)
        finales_por_servidor[cola_esperada] = parada['tiempo_fin_servicio']
        inicios_por_cola[cola_esperada].append(parada['tiempo_inicio_servicio'])

    for inicios in inicios_por_cola.values():
        assert inicios == sorted(inicios)


def test_colas_multiples_mas_corta_servidor_unico():
    """Comprueba servidor único con múltiples colas y reparto mas_corta (ejemplo 04)."""
    cfg = _cargar_ejemplo('04_paralelo_servidor_unico.json')
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []

    eventos = resultado['eventos_clientes']
    assert len(eventos) > 0

    colas_usadas = set()
    inicios = []
    for cliente in eventos:
        parada = cliente['paradas'][0]
        assert parada['servidor_asignado'] == 1
        assert parada['cola_asignada'] in (1, 2)
        colas_usadas.add(parada['cola_asignada'])
        inicios.append(parada['tiempo_inicio_servicio'])

    assert colas_usadas == {1, 2}
    assert inicios == sorted(inicios)


def test_colas_multiples_mas_corta_desempate_multi_servidor():
    """Verifica que mas_corta cuenta ocupación del servidor y desempata por menor cola."""
    cfg = {
        'simulacion': {
            'nombre': 'Desempate mas_corta multiples servidores',
            'metodo': 'paralelo',
            'duracion_minutos': 3,
            'semilla': 42,
            'llegada': {
                'distribucion': 'poisson',
                'lambda_por_hora': 600,
            },
        },
        'estaciones': [
            {
                'id': 'cajeros',
                'servidores': [
                    {'id': f's{i}', 'servicio': {'tipo': 'uniforme', 'min': 9.999, 'max': 10.001}}
                    for i in range(1, 4)
                ],
                'colas': {
                    'tipo': 'multiple',
                    'cantidad': 3,
                    'reparticion': 'mas_corta',
                },
                'salidas': [],
            },
        ],
    }

    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    eventos = resultado['eventos_clientes']
    assert len(eventos) >= 6

    # Ningún servicio termina antes de t=3 min, así que la carga crece equilibrada 1, 2, 3, 1, 2, 3...
    for idx, cliente in enumerate(eventos):
        parada = cliente['paradas'][0]
        esperada = (idx % 3) + 1
        assert parada['cola_asignada'] == esperada
        assert parada['servidor_asignado'] == esperada
        if idx < 3:
            assert parada['tiempo_inicio_servicio'] == parada['tiempo_inicio_espera']
        else:
            assert parada['tiempo_inicio_servicio'] > parada['tiempo_inicio_espera']


def test_colas_multiples_mas_corta_desempate_servidor_unico():
    """Verifica que mas_corta con servidor único cuenta solo espera y desempata por menor cola."""
    cfg = {
        'simulacion': {
            'nombre': 'Desempate mas_corta servidor unico',
            'metodo': 'paralelo',
            'duracion_minutos': 3,
            'semilla': 42,
            'llegada': {
                'distribucion': 'poisson',
                'lambda_por_hora': 600,
            },
        },
        'estaciones': [
            {
                'id': 'taquilla',
                'servidores': [
                    {'id': 's1', 'servicio': {'tipo': 'uniforme', 'min': 9.999, 'max': 10.001}},
                ],
                'colas': {
                    'tipo': 'multiple',
                    'cantidad': 3,
                    'reparticion': 'mas_corta',
                },
                'salidas': [],
            },
        ],
    }

    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    eventos = resultado['eventos_clientes']
    assert len(eventos) >= 5

    # Cliente 1 pasa directo a atención (colas en espera = [0, 0, 0] -> cola 1).
    # Clientes 2..5 esperan mientras el servidor sigue ocupado -> colas 1, 2, 3, 1.
    colas_primeros_cinco = [c['paradas'][0]['cola_asignada'] for c in eventos[:5]]
    assert colas_primeros_cinco == [1, 1, 2, 3, 1]
    assert all(c['paradas'][0]['servidor_asignado'] == 1 for c in eventos)

    inicios = [c['paradas'][0]['tiempo_inicio_servicio'] for c in eventos]
    assert inicios == sorted(inicios)


def test_secuencial_colas_multiples_ejemplo_06():
    """Comprueba método secuencial con colas múltiples y mas_corta (ejemplo 06)."""
    cfg = _cargar_ejemplo('06_secuencial_colas_multiples.json')
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []

    eventos = resultado['eventos_clientes']
    assert len(eventos) > 0

    colas_cajas = set()
    for cliente in eventos:
        assert len(cliente['paradas']) == 2
        p_recep, p_cajas = cliente['paradas']
        assert p_recep['estacion_id'] == 'recepcion'
        assert p_recep['cola_asignada'] == 1
        assert p_recep['servidor_asignado'] == 1
        assert p_cajas['estacion_id'] == 'cajas'
        assert p_cajas['cola_asignada'] in (1, 2)
        assert p_cajas['servidor_asignado'] == p_cajas['cola_asignada']
        colas_cajas.add(p_cajas['cola_asignada'])

    assert colas_cajas == {1, 2}


def test_secuencial_servidor_unico_aleatoria_ejemplo_08():
    """Comprueba método secuencial con servidor único y reparto aleatorio (ejemplo 08)."""
    cfg = _cargar_ejemplo('08_secuencial_servidor_unico.json')
    estado = random.getstate()
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    assert resultado == ejecutar_simulacion(cfg)
    assert random.getstate() == estado

    eventos = resultado['eventos_clientes']
    assert len(eventos) > 0

    colas_taquilla = set()
    for cliente in eventos:
        assert len(cliente['paradas']) == 2
        p_filtro, p_taquilla = cliente['paradas']
        assert p_filtro['estacion_id'] == 'filtro'
        assert p_filtro['cola_asignada'] == 1
        assert p_taquilla['estacion_id'] == 'taquilla'
        assert p_taquilla['servidor_asignado'] == 1
        assert p_taquilla['cola_asignada'] in (1, 2, 3)
        colas_taquilla.add(p_taquilla['cola_asignada'])

    assert colas_taquilla == {1, 2, 3}

    paradas_taquilla = sorted(
        (c['paradas'][1] for c in eventos),
        key=lambda p: p['tiempo_inicio_espera'],
    )
    inicios_taquilla = [p['tiempo_inicio_servicio'] for p in paradas_taquilla]
    assert inicios_taquilla == sorted(inicios_taquilla)


@pytest.mark.parametrize(
    'archivo',
    sorted(p.name for p in CARPETA_EJEMPLOS.glob('*.json')),
)
def test_todos_los_ejemplos_oficiales_corren_y_pasan_contrato(archivo):
    """Comprueba que los 8 ejemplos de configs_ejemplo corren y pasan validar_resultado."""
    cfg = _cargar_ejemplo(archivo)
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    assert len(resultado['eventos_clientes']) > 0


def test_preferencial_paralelo_ejemplo_03():
    """Comprueba reparto de clase, prioridad no expropiativa y reproducibilidad (ejemplo 03)."""
    cfg = _cargar_ejemplo('03_paralelo_preferencial.json')
    estado = random.getstate()
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    assert resultado == ejecutar_simulacion(cfg)
    assert random.getstate() == estado

    eventos = resultado['eventos_clientes']
    preferenciales = [c for c in eventos if c['es_preferencial']]
    normales = [c for c in eventos if not c['es_preferencial']]
    assert preferenciales and normales

    proporcion_observada = len(preferenciales) / len(eventos)
    assert proporcion_observada == pytest.approx(0.2, abs=0.08)

    for c in preferenciales:
        assert c['paradas'][0]['cola_asignada'] == 1
    for c in normales:
        assert c['paradas'][0]['cola_asignada'] == 2

    # FIFO dentro de cada cola
    inicios_pref = [c['paradas'][0]['tiempo_inicio_servicio'] for c in preferenciales]
    inicios_norm = [c['paradas'][0]['tiempo_inicio_servicio'] for c in normales]
    assert inicios_pref == sorted(inicios_pref)
    assert inicios_norm == sorted(inicios_norm)

    # Prioridad estricta: ningún normal inicia antes que un preferencial que ya estaba esperando
    for n in normales:
        inicio_n = n['paradas'][0]['tiempo_inicio_servicio']
        for p in preferenciales:
            if p['paradas'][0]['tiempo_inicio_espera'] < inicio_n:
                assert p['paradas'][0]['tiempo_inicio_servicio'] <= inicio_n


def test_preferencial_prioridad_no_expropiativa():
    """Verifica que la prioridad adelanta a los normales en espera sin interrumpir el servicio."""
    cfg = {
        'simulacion': {
            'nombre': 'Prioridad no expropiativa controlada',
            'metodo': 'paralelo',
            'duracion_minutos': 3,
            'semilla': 1,
            'llegada': {
                'distribucion': 'poisson',
                'lambda_por_hora': 600,
            },
            'clientes_preferenciales': {
                'proporcion': 0.5,
            },
        },
        'estaciones': [
            {
                'id': 'atencion',
                'servidores': [
                    {'id': 's1', 'servicio': {'tipo': 'uniforme', 'min': 9.999, 'max': 10.001}},
                ],
                'colas': {
                    'tipo': 'preferencial',
                    'cantidad': 2,
                    'reparticion': None,
                },
                'salidas': [],
            },
        ],
    }

    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []
    eventos = resultado['eventos_clientes']
    assert len(eventos) >= 6

    # El primer cliente es normal y completa su servicio (~10 min) sin ser interrumpido
    primero = eventos[0]
    assert primero['es_preferencial'] is False
    p0 = primero['paradas'][0]
    assert p0['cola_asignada'] == 2
    assert p0['tiempo_inicio_servicio'] == p0['tiempo_inicio_espera']
    assert p0['tiempo_fin_servicio'] - p0['tiempo_inicio_servicio'] == pytest.approx(10, abs=0.01)

    # Todos los demás llegan antes de que termine el primero (t < 3 < 10)
    en_espera = eventos[1:]
    pref_espera = [c for c in en_espera if c['es_preferencial']]
    norm_espera = [c for c in en_espera if not c['es_preferencial']]
    assert pref_espera and norm_espera

    # Todos los preferenciales en espera son atendidos después del primero y antes que los normales
    ultimo_inicio_pref = max(c['paradas'][0]['tiempo_inicio_servicio'] for c in pref_espera)
    primer_inicio_norm = min(c['paradas'][0]['tiempo_inicio_servicio'] for c in norm_espera)
    assert min(c['paradas'][0]['tiempo_inicio_servicio'] for c in pref_espera) >= p0['tiempo_fin_servicio']
    assert ultimo_inicio_pref < primer_inicio_norm


def test_secuencial_preferencial_ejemplo_07():
    """Verifica triaje común (unica) seguido de especialistas con prioridad (ejemplo 07)."""
    cfg = _cargar_ejemplo('07_secuencial_preferencial.json')
    resultado = ejecutar_simulacion(cfg)
    assert validar_resultado(resultado, cfg) == []

    eventos = resultado['eventos_clientes']
    assert any(c['es_preferencial'] for c in eventos)
    assert any(not c['es_preferencial'] for c in eventos)

    # En triaje (cola unica) se ignora la clase: todos van a cola 1 en FIFO global
    inicios_triaje = [c['paradas'][0]['tiempo_inicio_servicio'] for c in eventos]
    assert inicios_triaje == sorted(inicios_triaje)

    paradas_esp_pref = []
    paradas_esp_norm = []
    for cliente in eventos:
        assert len(cliente['paradas']) == 2
        p_triaje, p_esp = cliente['paradas']
        assert p_triaje['estacion_id'] == 'triaje'
        assert p_triaje['cola_asignada'] == 1
        assert p_esp['estacion_id'] == 'especialistas'
        if cliente['es_preferencial']:
            assert p_esp['cola_asignada'] == 1
            paradas_esp_pref.append(p_esp)
        else:
            assert p_esp['cola_asignada'] == 2
            paradas_esp_norm.append(p_esp)

    # Prioridad respetada en especialistas
    for pn in paradas_esp_norm:
        for pp in paradas_esp_pref:
            if pp['tiempo_inicio_espera'] < pn['tiempo_inicio_servicio']:
                assert pp['tiempo_inicio_servicio'] <= pn['tiempo_inicio_servicio']


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
    assert validar_resultado(resultado, config_512) == []
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
