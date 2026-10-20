"""Pruebas de métricas. Responsables: Equipo 3 (Métricas).

Caso base (calculado a mano): estación "cajeros", 3 servidores, cola única,
duración 20 minutos, 8 clientes. Es el mismo de
examples/resultados_ejemplo/01_paralelo_cola_unica_resultado.json.

    cliente  entra  inicia  sale  servidor  en sistema
       1       0      0      5       1         5
       2       1      1      4       2         3
       3       2      2      8       3         6
       4       3      4     10       2         7
       5       4      5      7       1         3
       6       6      7     12       1         6
       7       9      9     11       3         2
       8      10     10     13       2         3
                                    total     35

    W = 35 / 8 = 4.375      λ = 8 / 20 = 0.4      L = λ·W = 1.75
"""
import pytest

from src import metrics

DURACION = 20

# (entrada, inicio_servicio, salida, servidor)
_CASO_BASE = [(0, 0, 5, 1), (1, 1, 4, 2), (2, 2, 8, 3), (3, 4, 10, 2),
              (4, 5, 7, 1), (6, 7, 12, 1), (9, 9, 11, 3), (10, 10, 13, 2)]


def _cliente(cliente_id, entrada, inicio, salida, servidor, estacion="cajeros"):
    """Arma un cliente de una sola parada según el contrato de salida."""
    return {
        "cliente_id": cliente_id,
        "es_preferencial": False,
        "tiempo_entrada_sistema": entrada,
        "tiempo_salida_sistema": salida,
        "paradas": [{
            "estacion_id": estacion,
            "tiempo_inicio_espera": entrada,
            "tiempo_inicio_servicio": inicio,
            "tiempo_fin_servicio": salida,
            "servidor_asignado": servidor,
            "cola_asignada": 1,
        }],
    }


@pytest.fixture
def eventos_base():
    """Los 8 clientes del caso base."""
    return [_cliente(i, *fila) for i, fila in enumerate(_CASO_BASE, start=1)]


# --------------------------------------------------------------------------
# Tiempo promedio en el sistema (Issue #13)
# --------------------------------------------------------------------------

def test_tiempo_promedio_en_sistema_con_datos_conocidos(eventos_base):
    assert metrics.tiempo_promedio_en_sistema(eventos_base) == pytest.approx(4.375)


def test_tiempo_promedio_de_un_solo_cliente():
    eventos = [_cliente(1, 2.3, 4.1, 9.6, 1)]
    assert metrics.tiempo_promedio_en_sistema(eventos) == pytest.approx(7.3)


def test_tiempo_promedio_sin_clientes_es_cero():
    assert metrics.tiempo_promedio_en_sistema([]) == 0.0


def test_cliente_sin_salida_no_cuenta_como_atendido(eventos_base):
    sin_salida = _cliente(9, 18, 19, None, 3)
    eventos = eventos_base + [sin_salida]
    assert metrics.clientes_totales_atendidos(eventos) == 8
    assert metrics.tiempo_promedio_en_sistema(eventos) == pytest.approx(4.375)


def test_clientes_totales_atendidos(eventos_base):
    assert metrics.clientes_totales_atendidos(eventos_base) == 8
