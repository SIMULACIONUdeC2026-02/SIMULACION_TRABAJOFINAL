"""Pruebas de simular(config): recorrido completo que usa la interfaz (Issue #5)."""
import json
from pathlib import Path

import pytest

import src.engine as engine
from examples import ejecutar_engine
from src.contrato_salida import CLAVES_SISTEMA, validar_resultado
from src.engine import simular

CARPETA_EJEMPLOS = Path(__file__).resolve().parents[1] / 'examples/configs_ejemplo'
EJEMPLOS = sorted(p.name for p in CARPETA_EJEMPLOS.glob('*.json'))


def _cargar(nombre: str) -> dict:
    """Carga un ejemplo de examples/configs_ejemplo."""
    return json.loads((CARPETA_EJEMPLOS / nombre).read_text(encoding='utf-8'))


@pytest.fixture
def metricas_pendientes(monkeypatch):
    """Simula el estado actual de Métricas (#17): calcular_metricas aún no implementado."""
    def _pendiente(*_args, **_kwargs):
        raise NotImplementedError('Pendiente #17')
    monkeypatch.setattr(engine, 'calcular_metricas', _pendiente)


@pytest.mark.parametrize('archivo', EJEMPLOS)
def test_simular_los_8_ejemplos_devuelve_formato_de_la_ui(archivo, metricas_pendientes):
    """Cada ejemplo devuelve {"resultado": ...} válido y sin "metricas" mientras falte #17."""
    config = _cargar(archivo)
    salida = simular(config)

    assert set(salida) == {'resultado'}
    resultado = salida['resultado']
    assert set(resultado) == {'simulacion_id', 'duracion_total_minutos', 'eventos_clientes'}
    assert resultado['eventos_clientes']
    assert validar_resultado(resultado, config) == []


def test_simular_es_reproducible_y_serializable_a_json(metricas_pendientes):
    """La misma config y semilla producen la misma salida, y se puede escribir como JSON."""
    config = _cargar('05_secuencial_cola_unica.json')
    salida = simular(config)
    assert salida == simular(config)
    assert json.loads(json.dumps(salida)) == salida


def test_simular_incluye_metricas_cuando_estan_disponibles(monkeypatch):
    """Cuando Métricas implemente calcular_metricas, su bloque se agrega al resultado."""
    metricas = {
        'sistema_completo': {clave: 0 for clave in CLAVES_SISTEMA},
        'por_estacion': {},
    }
    llamadas = []

    def _calcular(eventos, config, duracion):
        llamadas.append((len(eventos), duracion))
        return metricas

    monkeypatch.setattr(engine, 'calcular_metricas', _calcular)
    salida = simular(_cargar('01_paralelo_cola_unica.json'))

    resultado = salida['resultado']
    assert resultado['metricas'] == metricas
    assert llamadas == [(len(resultado['eventos_clientes']), resultado['duracion_total_minutos'])]


def test_simular_config_invalida_lanza_value_error_con_la_lista(monkeypatch):
    """Una config inválida se rechaza antes de simular, con todos los errores en el mensaje."""
    def _no_debe_llamarse(_config):
        raise AssertionError('no debe ejecutar el motor con una config inválida')
    monkeypatch.setattr(engine, 'ejecutar_simulacion', _no_debe_llamarse)

    config = _cargar('01_paralelo_cola_unica.json')
    config['simulacion']['duracion_minutos'] = -5
    config['estaciones'][0]['id'] = ''

    with pytest.raises(ValueError) as error:
        simular(config)
    mensaje = str(error.value)
    assert 'simulacion.duracion_minutos' in mensaje
    assert 'estaciones[0].id' in mensaje


def test_simular_resultado_fuera_de_contrato_lanza_runtime_error(monkeypatch, metricas_pendientes):
    """Si la salida del motor no pasa validar_resultado, se informa en vez de devolverla."""
    monkeypatch.setattr(engine, 'validar_resultado', lambda _r, _c: ['error de prueba'])
    with pytest.raises(RuntimeError, match='error de prueba'):
        simular(_cargar('01_paralelo_cola_unica.json'))


@pytest.mark.parametrize('argumento, esperado', [
    ('03', '03_paralelo_preferencial.json'),
    ('07_secuencial_preferencial', '07_secuencial_preferencial.json'),
    ('08_secuencial_servidor_unico.json', '08_secuencial_servidor_unico.json'),
])
def test_ejecutar_engine_resuelve_el_ejemplo(argumento, esperado):
    """El script acepta número, nombre sin extensión o nombre de archivo."""
    assert ejecutar_engine.resolver_ejemplo(argumento).name == esperado


def test_ejecutar_engine_imprime_el_ejemplo_pedido(capsys, metricas_pendientes):
    """Con un argumento corre ese ejemplo y escribe {"resultado": ...} en consola."""
    assert ejecutar_engine.main(['05']) == 0
    salida = json.loads(capsys.readouterr().out)
    config = _cargar('05_secuencial_cola_unica.json')
    assert validar_resultado(salida['resultado'], config) == []
    assert salida['resultado']['eventos_clientes'][0]['paradas'][0]['estacion_id'] == 'triaje'


def test_ejecutar_engine_sin_argumento_usa_el_01(capsys, metricas_pendientes):
    """Sin argumentos mantiene el comportamiento anterior: corre el ejemplo 01."""
    assert ejecutar_engine.main([]) == 0
    salida = json.loads(capsys.readouterr().out)
    assert salida['resultado']['eventos_clientes'][0]['paradas'][0]['estacion_id'] == 'cajeros'


def test_ejecutar_engine_ejemplo_inexistente(capsys):
    """Un nombre que no existe termina con código 1 y lista los disponibles."""
    assert ejecutar_engine.main(['99']) == 1
    assert '01_paralelo_cola_unica.json' in capsys.readouterr().err
