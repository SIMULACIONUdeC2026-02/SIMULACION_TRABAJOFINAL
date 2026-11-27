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
import json
from pathlib import Path

import pytest

from src import metrics
from src.contrato_salida import CLAVES_ESTACION, CLAVES_SISTEMA, validar_resultado
from src.engine import simular

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
    assert metrics.tiempo_promedio_en_sistema(eventos_base, DURACION) == pytest.approx(4.375)


def test_tiempo_promedio_de_un_solo_cliente():
    eventos = [_cliente(1, 2.3, 4.1, 9.6, 1)]
    assert metrics.tiempo_promedio_en_sistema(eventos, DURACION) == pytest.approx(7.3)


def test_tiempo_promedio_sin_clientes_es_cero():
    assert metrics.tiempo_promedio_en_sistema([], DURACION) == 0.0


def test_cliente_sin_salida_no_cuenta_como_atendido(eventos_base):
    sin_salida = _cliente(9, 18, 19, None, 3)
    eventos = eventos_base + [sin_salida]
    assert metrics.clientes_totales_atendidos(eventos, DURACION) == 8
    assert metrics.tiempo_promedio_en_sistema(eventos, DURACION) == pytest.approx(4.375)


def test_clientes_totales_atendidos(eventos_base):
    assert metrics.clientes_totales_atendidos(eventos_base, DURACION) == 8


def test_cliente_que_sale_despues_del_final_no_cuenta_como_atendido(eventos_base):
    """Regla de corte: atendido = salió antes de T. El que sale en 30 (T = 20) no cuenta."""
    sale_tarde = _cliente(9, 15, 15, 30, 1)
    eventos = eventos_base + [sale_tarde]
    assert metrics.clientes_totales_atendidos(eventos, DURACION) == 8
    assert metrics.tiempo_promedio_en_sistema(eventos, DURACION) == pytest.approx(4.375)


# --------------------------------------------------------------------------
# Clientes promedio en el sistema, Ley de Little (Issue #14)
# --------------------------------------------------------------------------

def test_clientes_promedio_por_ley_de_little(eventos_base):
    assert metrics.clientes_promedio_en_sistema(eventos_base, DURACION) == pytest.approx(1.75)


def test_little_coincide_con_la_integracion_de_n_t(eventos_base):
    """Si todos entran y salen dentro de [0, T], L = λ·W = (1/T)·∫N(t)dt."""
    little = metrics.clientes_promedio_en_sistema(eventos_base, DURACION)
    integral = metrics.clientes_promedio_por_integracion(eventos_base, DURACION)
    assert little == pytest.approx(integral)


def test_integracion_cuenta_al_que_sigue_dentro_hasta_el_final(eventos_base):
    sin_salida = _cliente(9, 18, 19, None, 3)
    eventos = eventos_base + [sin_salida]
    # 35 minutos de los 8 atendidos + 2 minutos (de 18 a 20) del que sigue dentro
    assert metrics.clientes_promedio_por_integracion(eventos, DURACION) == pytest.approx(37 / 20)


def test_integracion_recorta_lo_que_pasa_despues_del_final():
    eventos = [_cliente(1, 15, 15, 30, 1)]
    assert metrics.clientes_promedio_por_integracion(eventos, DURACION) == pytest.approx(5 / 20)


def test_cliente_que_sale_despues_del_final_en_little_y_en_integracion():
    """Caso de la revisión del PR #28: entra a los 15, sale a los 30, T = 20.

    No salió antes de T, así que no es atendido: Little da 0 (nadie terminó).
    La integración sí cuenta los 5 minutos que estuvo dentro de [0, T]: 0.25.
    """
    eventos = [_cliente(1, 15, 15, 30, 1)]
    assert metrics.clientes_totales_atendidos(eventos, DURACION) == 0
    assert metrics.tiempo_promedio_en_sistema(eventos, DURACION) == 0.0
    assert metrics.clientes_promedio_en_sistema(eventos, DURACION) == 0.0
    assert metrics.clientes_promedio_por_integracion(eventos, DURACION) == pytest.approx(5 / 20)


def test_salir_despues_del_final_equivale_a_seguir_dentro(eventos_base):
    """Salir en 30 con T = 20 da las mismas métricas que no haber salido (null)."""
    con_salida_tarde = eventos_base + [_cliente(9, 15, 15, 30, 1)]
    sin_salida = eventos_base + [_cliente(9, 15, 15, None, 1)]
    for funcion in (metrics.clientes_totales_atendidos,
                    metrics.tiempo_promedio_en_sistema,
                    metrics.clientes_promedio_en_sistema,
                    metrics.clientes_promedio_por_integracion):
        assert funcion(con_salida_tarde, DURACION) == pytest.approx(funcion(sin_salida, DURACION))


def test_clientes_promedio_sin_clientes_es_cero():
    assert metrics.clientes_promedio_en_sistema([], DURACION) == 0.0
    assert metrics.clientes_promedio_por_integracion([], DURACION) == 0.0


@pytest.mark.parametrize("duracion", [0, -5, None, True])
def test_duracion_invalida_lanza_error(eventos_base, duracion):
    with pytest.raises(ValueError):
        metrics.clientes_promedio_en_sistema(eventos_base, duracion)
    with pytest.raises(ValueError):
        metrics.tiempo_promedio_en_sistema(eventos_base, duracion)


# --------------------------------------------------------------------------
# Tiempo ocioso y utilización por servidor y por estación (Issue #15)
#
# Estación "cajeros"; los servidores se numeran por posición (1, 2, 3).
# Caso base, T = 20 (servicio = [inicio, salida]):
#   servidor 1: 0-5, 5-7, 7-12   -> ocupado 12, ocioso 8,  3 atendidos
#   servidor 2: 1-4, 4-10, 10-13 -> ocupado 12, ocioso 8,  3 atendidos
#   servidor 3: 2-8, 9-11        -> ocupado 8,  ocioso 12, 2 atendidos
# --------------------------------------------------------------------------

@pytest.fixture
def config_base():
    """Configuración mínima: estación "cajeros" con 3 servidores (posiciones 1-3)
    y estación "farmacia" con 1. Los "id" de texto de los servidores no se usan
    en las métricas: se identifican por posición."""
    servicio = {"tipo": "exponencial", "media": 2}
    return {"estaciones": [
        {"id": "cajeros", "servidores": [
            {"id": "s1", "servicio": servicio},
            {"id": "s2", "servicio": servicio},
            {"id": "s3", "servicio": servicio}]},
        {"id": "farmacia", "servidores": [{"id": "f1", "servicio": servicio}]},
    ]}


def _ocioso(eventos, servidor, duracion=DURACION, estacion="cajeros"):
    return metrics.calculo_ocioso_servidor(eventos, estacion, servidor, duracion)


@pytest.mark.parametrize("servidor, ocioso, atendidos",
                         [(1, 8, 3), (2, 8, 3), (3, 12, 2)])
def test_ocioso_servidor_caso_base(eventos_base, servidor, ocioso, atendidos):
    r = _ocioso(eventos_base, servidor)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(ocioso)
    assert r["utilizacion"] == pytest.approx((DURACION - ocioso) / DURACION)
    assert r["clientes_atendidos"] == atendidos


def test_ocioso_servidor_forma_del_contrato(eventos_base):
    assert set(_ocioso(eventos_base, 1)) == {
        "utilizacion", "tiempo_ocioso_minutos", "clientes_atendidos"}


def test_ocioso_mas_ocupado_es_la_duracion(eventos_base):
    for servidor in (1, 2, 3):
        r = _ocioso(eventos_base, servidor)
        ocupado = r["utilizacion"] * DURACION
        assert ocupado + r["tiempo_ocioso_minutos"] == pytest.approx(DURACION)


def test_ocioso_sin_eventos_es_toda_la_duracion():
    r = _ocioso([], 1)
    assert r == {"utilizacion": 0.0, "tiempo_ocioso_minutos": DURACION,
                 "clientes_atendidos": 0}


def test_ocioso_servidor_que_no_atendio_a_nadie(eventos_base):
    """La posición 4 no atiende a nadie en el caso base (solo hay servidores 1-3)."""
    r = _ocioso(eventos_base, 4)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(DURACION)
    assert r["utilizacion"] == 0.0
    assert r["clientes_atendidos"] == 0


def test_ocioso_ignora_otras_estaciones(eventos_base):
    eventos = eventos_base + [_cliente(9, 0, 0, 20, 1, estacion="farmacia")]
    assert _ocioso(eventos, 1)["tiempo_ocioso_minutos"] == pytest.approx(8)
    assert _ocioso(eventos, 1, estacion="farmacia")["utilizacion"] == pytest.approx(1.0)


def test_ocioso_estacion_sin_paradas_es_toda_la_duracion():
    r = _ocioso(eventos=[_cliente(1, 0, 0, 5, 1)], servidor=1, estacion="nada")
    assert r["tiempo_ocioso_minutos"] == pytest.approx(DURACION)


def test_ocioso_no_depende_del_orden_de_los_eventos(eventos_base):
    esperado = _ocioso(eventos_base, 3)
    assert _ocioso(list(reversed(eventos_base)), 3) == esperado


def test_ocioso_servidor_siempre_ocupado():
    eventos = [_cliente(1, 0, 0, 10, 1), _cliente(2, 5, 10, 20, 1)]
    r = _ocioso(eventos, 1)
    assert r["utilizacion"] == pytest.approx(1.0)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(0.0)
    assert r["clientes_atendidos"] == 2


def test_ocioso_con_servicio_que_cruza_el_final():
    """Servicio 15-30 con T = 20: ocupa 5 min dentro de T y no cuenta como atendido."""
    r = _ocioso([_cliente(1, 15, 15, 30, 1)], 1)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(15)
    assert r["utilizacion"] == pytest.approx(5 / 20)
    assert r["clientes_atendidos"] == 0


def test_ocioso_con_servicio_sin_fin_cuenta_hasta_el_final():
    r = _ocioso([_cliente(1, 15, 15, None, 1)], 1)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(15)
    assert r["clientes_atendidos"] == 0


def test_ocioso_servicio_que_empieza_en_o_despues_del_final_se_ignora():
    eventos = [_cliente(1, 0, 20, 25, 1), _cliente(2, 0, 22, 30, 1)]
    r = _ocioso(eventos, 1)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(DURACION)
    assert r["clientes_atendidos"] == 0


def test_ocioso_servicio_que_termina_exactamente_en_el_final_es_atendido():
    r = _ocioso([_cliente(1, 0, 10, 20, 1)], 1)
    assert r["clientes_atendidos"] == 1
    assert r["tiempo_ocioso_minutos"] == pytest.approx(10)


def test_ocioso_cliente_que_sigue_en_cola_no_ocupa_servidor():
    """Sin inicio de servicio ni servidor asignado: no cuenta para nadie."""
    en_cola = _cliente(1, 18, None, None, None)
    assert _ocioso([en_cola], 1)["tiempo_ocioso_minutos"] == pytest.approx(DURACION)


def test_ocioso_servicio_de_duracion_cero():
    r = _ocioso([_cliente(1, 5, 5, 5, 1)], 1)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(DURACION)
    assert r["clientes_atendidos"] == 1


def test_ocioso_servicios_solapados_no_cuentan_doble():
    """Datos incoherentes (un servidor, dos clientes a la vez): el solape no se suma dos veces."""
    eventos = [_cliente(1, 0, 0, 10, 1), _cliente(2, 0, 5, 8, 1)]
    assert _ocioso(eventos, 1)["tiempo_ocioso_minutos"] == pytest.approx(10)


def test_ocioso_cliente_con_varias_paradas_usa_solo_la_de_la_estacion():
    cliente = _cliente(1, 0, 0, 10, 1, estacion="cajeros")
    cliente["paradas"].append({
        "estacion_id": "farmacia", "tiempo_inicio_espera": 10,
        "tiempo_inicio_servicio": 12, "tiempo_fin_servicio": 16,
        "servidor_asignado": 1, "cola_asignada": 1})
    cliente["tiempo_salida_sistema"] = 16
    assert _ocioso([cliente], 1)["tiempo_ocioso_minutos"] == pytest.approx(10)
    assert _ocioso([cliente], 1, estacion="farmacia")["tiempo_ocioso_minutos"] == pytest.approx(16)


def test_ocioso_con_tiempos_decimales():
    eventos = [_cliente(1, 2.3, 4.1, 4.8, 2)]
    r = _ocioso(eventos, 2, duracion=480)
    assert r["tiempo_ocioso_minutos"] == pytest.approx(480 - 0.7)
    assert r["utilizacion"] == pytest.approx(0.7 / 480)


@pytest.mark.parametrize("duracion", [0, -5, None, True, "20"])
def test_ocioso_servidor_duracion_invalida(eventos_base, duracion):
    with pytest.raises(ValueError):
        _ocioso(eventos_base, 1, duracion=duracion)


# --- paradas_por_estacion ---

def test_paradas_por_estacion_filtra_por_id(eventos_base):
    eventos = eventos_base + [_cliente(9, 0, 0, 3, 1, estacion="farmacia")]
    assert len(metrics.paradas_por_estacion(eventos, "cajeros")) == 8
    assert len(metrics.paradas_por_estacion(eventos, "farmacia")) == 1
    assert metrics.paradas_por_estacion(eventos, "otra") == []


def test_paradas_por_estacion_cliente_sin_paradas():
    assert metrics.paradas_por_estacion([{"cliente_id": 1}], "cajeros") == []
    assert metrics.paradas_por_estacion([], "cajeros") == []


# --- calculo_ocioso_estacion ---

def test_ocioso_estacion_devuelve_un_bloque_por_servidor(eventos_base, config_base):
    r = metrics.calculo_ocioso_estacion(eventos_base, config_base, "cajeros", DURACION)
    assert list(r) == ["servidor_1", "servidor_2", "servidor_3"]
    assert r["servidor_1"]["tiempo_ocioso_minutos"] == pytest.approx(8)
    assert r["servidor_2"]["clientes_atendidos"] == 3
    assert r["servidor_3"]["utilizacion"] == pytest.approx(0.4)


def test_ocioso_estacion_coincide_con_cada_servidor(eventos_base, config_base):
    r = metrics.calculo_ocioso_estacion(eventos_base, config_base, "cajeros", DURACION)
    for i in (1, 2, 3):
        assert r[f"servidor_{i}"] == _ocioso(eventos_base, i)


def test_ocioso_estacion_clientes_atendidos_suman_el_total(eventos_base, config_base):
    r = metrics.calculo_ocioso_estacion(eventos_base, config_base, "cajeros", DURACION)
    assert sum(s["clientes_atendidos"] for s in r.values()) == 8


def test_ocioso_estacion_incluye_servidores_sin_clientes(config_base):
    r = metrics.calculo_ocioso_estacion([], config_base, "cajeros", DURACION)
    assert len(r) == 3
    assert all(s["tiempo_ocioso_minutos"] == pytest.approx(DURACION) for s in r.values())
    assert all(s["utilizacion"] == 0.0 for s in r.values())


def test_ocioso_estacion_un_solo_servidor(eventos_base, config_base):
    eventos = [_cliente(1, 0, 0, 10, 1, estacion="farmacia")]
    r = metrics.calculo_ocioso_estacion(eventos, config_base, "farmacia", DURACION)
    assert list(r) == ["servidor_1"]
    assert r["servidor_1"]["utilizacion"] == pytest.approx(0.5)


def test_ocioso_estacion_inexistente_lanza_error(eventos_base, config_base):
    with pytest.raises(ValueError):
        metrics.calculo_ocioso_estacion(eventos_base, config_base, "nada", DURACION)
    with pytest.raises(ValueError):
        metrics.calculo_ocioso_estacion(eventos_base, {}, "cajeros", DURACION)


@pytest.mark.parametrize("duracion", [0, -5, None, True])
def test_ocioso_estacion_duracion_invalida(eventos_base, config_base, duracion):
    with pytest.raises(ValueError):
        metrics.calculo_ocioso_estacion(eventos_base, config_base, "cajeros", duracion)


# --------------------------------------------------------------------------
# Longitud de las colas (Issue #16)
#
# Caso base, cola única (cola_1), T = 20. Esperan en cola:
#   cliente 4: 3-4    cliente 5: 4-5    cliente 6: 6-7
#   área = 3  ->  longitud promedio = 3 / 20 = 0.15
#   en t = 4 el cliente 4 pasa a servicio y entra el 5: longitud máxima = 1
# --------------------------------------------------------------------------

def _en_cola(cliente_id, espera, inicio, fin, cola, servidor=1, estacion="cajeros"):
    """Cliente de una parada que espera desde "espera" en la cola indicada."""
    cliente = _cliente(cliente_id, espera, inicio, fin, servidor, estacion=estacion)
    cliente["paradas"][0]["cola_asignada"] = cola
    return cliente


def _cola(eventos, cola=1, duracion=DURACION, estacion="cajeros"):
    return metrics.longitud_cola(eventos, estacion, cola, duracion)


def test_longitud_cola_caso_base(eventos_base):
    r = _cola(eventos_base)
    assert r["longitud_promedio"] == pytest.approx(0.15)
    assert r["longitud_maxima"] == 1


def test_longitud_cola_forma_del_contrato(eventos_base):
    assert set(_cola(eventos_base)) == {"longitud_promedio", "longitud_maxima"}


def test_longitud_cola_empate_primero_sale_y_luego_entra():
    """A las 4 uno pasa a servicio y otro llega: nunca hay 2 esperando a la vez."""
    eventos = [_en_cola(1, 0, 4, 6, 1), _en_cola(2, 4, 6, 8, 1)]
    r = _cola(eventos)
    assert r["longitud_maxima"] == 1
    assert r["longitud_promedio"] == pytest.approx(6 / 20)


def test_longitud_cola_clientes_esperando_a_la_vez():
    eventos = [_en_cola(1, 0, 6, 7, 1), _en_cola(2, 1, 7, 8, 1),
               _en_cola(3, 2, 8, 9, 1), _en_cola(4, 7, 9, 10, 1)]
    r = _cola(eventos)
    assert r["longitud_maxima"] == 3
    assert r["longitud_promedio"] == pytest.approx((6 + 6 + 6 + 2) / 20)


def test_longitud_cola_sin_espera_es_cero():
    eventos = [_en_cola(1, 0, 0, 5, 1), _en_cola(2, 6, 6, 9, 1)]
    assert _cola(eventos) == {"longitud_promedio": 0.0, "longitud_maxima": 0}


def test_longitud_cola_sin_eventos():
    assert _cola([]) == {"longitud_promedio": 0.0, "longitud_maxima": 0}


def test_longitud_cola_separa_las_colas_de_la_estacion():
    """Estación preferencial: cola_1 = preferenciales, cola_2 = normales."""
    eventos = [_en_cola(1, 0, 2, 5, 1), _en_cola(2, 1, 5, 8, 2),
               _en_cola(3, 2, 8, 9, 2)]
    assert _cola(eventos, cola=1) == {"longitud_promedio": pytest.approx(2 / 20),
                                      "longitud_maxima": 1}
    assert _cola(eventos, cola=2) == {"longitud_promedio": pytest.approx(10 / 20),
                                      "longitud_maxima": 2}


def test_longitud_cola_ignora_otras_estaciones(eventos_base):
    eventos = eventos_base + [_en_cola(9, 0, 10, 12, 1, estacion="farmacia")]
    assert _cola(eventos)["longitud_promedio"] == pytest.approx(0.15)
    assert _cola(eventos, estacion="farmacia")["longitud_promedio"] == pytest.approx(10 / 20)


def test_longitud_cola_cliente_que_sigue_en_cola_cuenta_hasta_el_final():
    eventos = [_en_cola(1, 15, None, None, 1, servidor=None)]
    r = _cola(eventos)
    assert r["longitud_promedio"] == pytest.approx(5 / 20)
    assert r["longitud_maxima"] == 1


def test_longitud_cola_recorta_la_espera_que_cruza_el_final():
    r = _cola([_en_cola(1, 18, 25, 30, 1)])
    assert r["longitud_promedio"] == pytest.approx(2 / 20)
    assert r["longitud_maxima"] == 1


def test_longitud_cola_espera_que_empieza_en_el_final_se_ignora():
    assert _cola([_en_cola(1, 20, 25, 30, 1)]) == {"longitud_promedio": 0.0,
                                                   "longitud_maxima": 0}


def test_longitud_cola_no_depende_del_orden_de_los_eventos(eventos_base):
    assert _cola(list(reversed(eventos_base))) == _cola(eventos_base)


def test_longitud_cola_con_tiempos_decimales():
    r = _cola([_en_cola(1, 2.3, 4.1, 4.8, 1)], duracion=480)
    assert r["longitud_promedio"] == pytest.approx(1.8 / 480)


@pytest.mark.parametrize("duracion", [0, -5, None, True, "20"])
def test_longitud_cola_duracion_invalida(eventos_base, duracion):
    with pytest.raises(ValueError):
        _cola(eventos_base, duracion=duracion)


# --- metricas_por_cola ---

@pytest.fixture
def config_colas():
    """Estación "atencion" preferencial (2 colas) y "cajeros" con cola única."""
    servicio = {"tipo": "exponencial", "media": 2}
    return {"estaciones": [
        {"id": "atencion",
         "servidores": [{"id": "a1", "servicio": servicio},
                        {"id": "a2", "servicio": servicio}],
         "colas": {"tipo": "preferencial", "cantidad": 2}},
        {"id": "cajeros",
         "servidores": [{"id": "s1", "servicio": servicio}],
         "colas": {"tipo": "unica", "cantidad": 1}},
    ]}


def test_por_cola_una_entrada_por_cola(config_colas):
    eventos = [_en_cola(1, 0, 4, 6, 2, estacion="atencion")]
    r = metrics.metricas_por_cola(eventos, config_colas, "atencion", DURACION)
    assert list(r) == ["cola_1", "cola_2"]
    assert r["cola_1"] == {"longitud_promedio": 0.0, "longitud_maxima": 0}
    assert r["cola_2"] == {"longitud_promedio": pytest.approx(4 / 20),
                           "longitud_maxima": 1}


def test_por_cola_coincide_con_cada_cola(eventos_base, config_colas):
    r = metrics.metricas_por_cola(eventos_base, config_colas, "cajeros", DURACION)
    assert r == {"cola_1": _cola(eventos_base)}


def test_por_cola_sin_bloque_colas_usa_una_sola(eventos_base, config_base):
    r = metrics.metricas_por_cola(eventos_base, config_base, "cajeros", DURACION)
    assert list(r) == ["cola_1"]


def test_por_cola_estacion_inexistente_lanza_error(config_colas):
    with pytest.raises(ValueError):
        metrics.metricas_por_cola([], config_colas, "nada", DURACION)


# --- longitud_cola_estacion y cola_mas_larga ---

def test_cola_estacion_caso_base(eventos_base):
    r = metrics.longitud_cola_estacion(eventos_base, "cajeros", DURACION)
    assert r == {"longitud_promedio_cola": pytest.approx(0.15),
                 "longitud_maxima_cola": 1}


def test_cola_estacion_promedio_es_la_suma_de_sus_colas(config_colas):
    eventos = [_en_cola(1, 0, 2, 5, 1, estacion="atencion"),
               _en_cola(2, 1, 5, 8, 2, estacion="atencion"),
               _en_cola(3, 2, 8, 9, 2, estacion="atencion")]
    por_cola = metrics.metricas_por_cola(eventos, config_colas, "atencion", DURACION)
    r = metrics.longitud_cola_estacion(eventos, "atencion", DURACION)
    assert r["longitud_promedio_cola"] == pytest.approx(
        sum(c["longitud_promedio"] for c in por_cola.values()))


def test_cola_estacion_maxima_cuenta_todas_las_colas_a_la_vez():
    """Cada cola tiene máximo 1, pero entre 1 y 2 esperan dos clientes juntos."""
    eventos = [_en_cola(1, 0, 2, 5, 1), _en_cola(2, 1, 5, 8, 2)]
    assert _cola(eventos, cola=1)["longitud_maxima"] == 1
    assert _cola(eventos, cola=2)["longitud_maxima"] == 1
    r = metrics.longitud_cola_estacion(eventos, "cajeros", DURACION)
    assert r["longitud_maxima_cola"] == 2


def test_cola_estacion_maxima_no_es_la_suma_de_maximos():
    """Los máximos de cada cola ocurren en momentos distintos."""
    eventos = [_en_cola(1, 0, 2, 3, 1), _en_cola(2, 5, 7, 8, 2)]
    r = metrics.longitud_cola_estacion(eventos, "cajeros", DURACION)
    assert r["longitud_maxima_cola"] == 1


def test_cola_estacion_sin_eventos():
    r = metrics.longitud_cola_estacion([], "cajeros", DURACION)
    assert r == {"longitud_promedio_cola": 0.0, "longitud_maxima_cola": 0}


@pytest.mark.parametrize("duracion", [0, -5, None, True])
def test_cola_estacion_duracion_invalida(eventos_base, duracion):
    with pytest.raises(ValueError):
        metrics.longitud_cola_estacion(eventos_base, "cajeros", duracion)


def test_cola_mas_larga_es_la_de_mayor_promedio():
    por_cola = {"cola_1": {"longitud_promedio": 0.2, "longitud_maxima": 5},
                "cola_2": {"longitud_promedio": 0.7, "longitud_maxima": 2}}
    assert metrics.cola_mas_larga(por_cola) == "cola_2"


def test_cola_mas_larga_empate_gana_la_de_menor_numero():
    por_cola = {"cola_2": {"longitud_promedio": 0.5, "longitud_maxima": 1},
                "cola_1": {"longitud_promedio": 0.5, "longitud_maxima": 3}}
    assert metrics.cola_mas_larga(por_cola) == "cola_1"


def test_cola_mas_larga_ordena_por_numero_y_no_por_texto():
    por_cola = {f"cola_{i}": {"longitud_promedio": 0.0, "longitud_maxima": 0}
                for i in (10, 2, 1)}
    por_cola["cola_10"]["longitud_promedio"] = 0.1
    assert metrics.cola_mas_larga(por_cola) == "cola_10"
    por_cola["cola_10"]["longitud_promedio"] = 0.0
    assert metrics.cola_mas_larga(por_cola) == "cola_1"


def test_cola_mas_larga_todas_vacias_es_la_primera(config_colas):
    por_cola = metrics.metricas_por_cola([], config_colas, "atencion", DURACION)
    assert metrics.cola_mas_larga(por_cola) == "cola_1"


def test_cola_mas_larga_sin_colas():
    assert metrics.cola_mas_larga({}) is None


# --- Las colas de los resultados de ejemplo (calculadas a mano) ---

def _cargar_ejemplo(nombre):
    carpeta = Path(__file__).resolve().parents[1] / "examples" / "resultados_ejemplo"
    resultado = json.loads((carpeta / f"{nombre}_resultado.json").read_text(encoding="utf-8"))
    config = json.loads((carpeta / f"{nombre}_config.json").read_text(encoding="utf-8"))
    return resultado["resultado"], config


@pytest.mark.parametrize("nombre", ["01_paralelo_cola_unica", "02_secuencial_preferencial"])
def test_colas_coinciden_con_los_resultados_de_ejemplo(nombre):
    """Los JSON de ejemplo están redondeados a 4 decimales."""
    resultado, config = _cargar_ejemplo(nombre)
    eventos = resultado["eventos_clientes"]
    duracion = resultado["duracion_total_minutos"]
    for estacion_id, esperado in resultado["metricas"]["por_estacion"].items():
        por_cola = metrics.metricas_por_cola(eventos, config, estacion_id, duracion)
        assert por_cola == {
            cola: {"longitud_promedio": pytest.approx(datos["longitud_promedio"], abs=1e-4),
                   "longitud_maxima": datos["longitud_maxima"]}
            for cola, datos in esperado["por_cola"].items()}
        estacion = metrics.longitud_cola_estacion(eventos, estacion_id, duracion)
        assert estacion["longitud_promedio_cola"] == pytest.approx(
            esperado["longitud_promedio_cola"], abs=1e-4)
        assert estacion["longitud_maxima_cola"] == esperado["longitud_maxima_cola"]
        assert metrics.cola_mas_larga(por_cola) == esperado["cola_mas_larga"]


# --------------------------------------------------------------------------
# Espera en cola y tiempo de atención por estación (Issue #17)
#
# Caso base: esperan 1 minuto los clientes 4, 5 y 6 -> Wq = 3 / 8 = 0.375
# Atención (salida - inicio): 5+3+6+6+2+5+2+3 = 32 -> 32 / 8 = 4.0
# --------------------------------------------------------------------------

def _espera(eventos, duracion=DURACION, estacion="cajeros"):
    return metrics.tiempo_promedio_espera_cola(eventos, estacion, duracion)


def _atencion(eventos, duracion=DURACION, estacion="cajeros"):
    return metrics.tiempo_promedio_atencion(eventos, estacion, duracion)


def test_espera_cola_caso_base(eventos_base):
    assert _espera(eventos_base) == pytest.approx(0.375)


def test_atencion_caso_base(eventos_base):
    assert _atencion(eventos_base) == pytest.approx(4.0)


def test_espera_y_atencion_suman_el_tiempo_en_la_estacion(eventos_base):
    """Con una sola parada, Wq + tiempo de atención = W."""
    w = metrics.tiempo_promedio_en_sistema(eventos_base, DURACION)
    assert _espera(eventos_base) + _atencion(eventos_base) == pytest.approx(w)


def test_espera_y_atencion_sin_eventos_son_cero():
    assert _espera([]) == 0.0
    assert _atencion([]) == 0.0


def test_espera_sin_nadie_que_espere():
    eventos = [_cliente(1, 0, 0, 5, 1), _cliente(2, 6, 6, 9, 1)]
    assert _espera(eventos) == 0.0
    assert _atencion(eventos) == pytest.approx(4.0)


def test_espera_y_atencion_ignoran_otras_estaciones(eventos_base):
    eventos = eventos_base + [_cliente(9, 0, 10, 20, 1, estacion="farmacia")]
    assert _espera(eventos) == pytest.approx(0.375)
    assert _espera(eventos, estacion="farmacia") == pytest.approx(10)
    assert _atencion(eventos, estacion="farmacia") == pytest.approx(10)


def test_espera_y_atencion_usan_la_parada_de_cada_estacion():
    cliente = _cliente(1, 0, 1, 4, 1, estacion="triaje")
    cliente["paradas"].append({
        "estacion_id": "atencion", "tiempo_inicio_espera": 4,
        "tiempo_inicio_servicio": 7, "tiempo_fin_servicio": 9,
        "servidor_asignado": 1, "cola_asignada": 1})
    cliente["tiempo_salida_sistema"] = 9
    assert _espera([cliente], estacion="triaje") == pytest.approx(1)
    assert _atencion([cliente], estacion="triaje") == pytest.approx(3)
    assert _espera([cliente], estacion="atencion") == pytest.approx(3)
    assert _atencion([cliente], estacion="atencion") == pytest.approx(2)


def test_espera_cliente_que_sigue_en_cola_no_entra_en_el_promedio():
    eventos = [_cliente(1, 0, 2, 5, 1), _cliente(2, 15, None, None, None)]
    assert _espera(eventos) == pytest.approx(2)


def test_espera_servicio_que_empieza_despues_del_final_no_cuenta():
    eventos = [_cliente(1, 0, 2, 5, 1), _cliente(2, 18, 25, 30, 1)]
    assert _espera(eventos) == pytest.approx(2)


def test_atencion_servicio_sin_terminar_no_entra_en_el_promedio():
    eventos = [_cliente(1, 0, 0, 4, 1), _cliente(2, 15, 16, None, 1),
               _cliente(3, 16, 17, 25, 2)]
    assert _atencion(eventos) == pytest.approx(4)
    assert _espera(eventos) == pytest.approx((0 + 1 + 1) / 3)


def test_atencion_termina_exactamente_en_el_final_si_cuenta():
    assert _atencion([_cliente(1, 0, 10, 20, 1)]) == pytest.approx(10)


@pytest.mark.parametrize("duracion", [0, -5, None, True, "20"])
def test_espera_y_atencion_duracion_invalida(eventos_base, duracion):
    with pytest.raises(ValueError):
        _espera(eventos_base, duracion=duracion)
    with pytest.raises(ValueError):
        _atencion(eventos_base, duracion=duracion)


# --------------------------------------------------------------------------
# calcular_metricas: bloque "metricas" completo (Issue #17)
# --------------------------------------------------------------------------

CARPETA_CONFIGS = Path(__file__).resolve().parents[1] / "examples" / "configs_ejemplo"
CONFIGS_EJEMPLO = sorted(p.name for p in CARPETA_CONFIGS.glob("*.json"))


def _aproximado(valor):
    """Compara números con la precisión de los ejemplos (4 decimales)."""
    if isinstance(valor, dict):
        return {clave: _aproximado(v) for clave, v in valor.items()}
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return pytest.approx(valor, abs=1e-4)
    return valor


def test_calcular_metricas_forma_del_contrato(eventos_base, config_base):
    r = metrics.calcular_metricas(eventos_base, config_base, DURACION)
    assert set(r) == {"sistema_completo", "por_estacion"}
    assert set(r["sistema_completo"]) == CLAVES_SISTEMA
    assert list(r["por_estacion"]) == ["cajeros", "farmacia"]
    for datos in r["por_estacion"].values():
        assert set(datos) == CLAVES_ESTACION


def test_calcular_metricas_caso_base(eventos_base, config_base):
    r = metrics.calcular_metricas(eventos_base, config_base, DURACION)
    assert r["sistema_completo"] == {
        "tiempo_promedio_en_sistema": pytest.approx(4.375),
        "clientes_promedio_en_sistema": pytest.approx(1.75),
        "clientes_totales_atendidos": 8,
    }
    cajeros = r["por_estacion"]["cajeros"]
    assert cajeros["tiempo_promedio_espera_cola"] == pytest.approx(0.375)
    assert cajeros["tiempo_promedio_atencion"] == pytest.approx(4.0)
    assert cajeros["longitud_promedio_cola"] == pytest.approx(0.15)
    assert cajeros["longitud_maxima_cola"] == 1
    assert cajeros["por_servidor"]["servidor_3"]["utilizacion"] == pytest.approx(0.4)
    assert cajeros["cola_mas_larga"] == "cola_1"


def test_calcular_metricas_reutiliza_las_funciones_de_cada_metrica(eventos_base, config_base):
    cajeros = metrics.calcular_metricas(eventos_base, config_base, DURACION)["por_estacion"]["cajeros"]
    assert cajeros["por_servidor"] == metrics.calculo_ocioso_estacion(
        eventos_base, config_base, "cajeros", DURACION)
    assert cajeros["por_cola"] == metrics.metricas_por_cola(
        eventos_base, config_base, "cajeros", DURACION)


def test_calcular_metricas_estacion_sin_clientes(eventos_base, config_base):
    """"farmacia" está en la config pero nadie pasó por ella."""
    farmacia = metrics.calcular_metricas(eventos_base, config_base, DURACION)["por_estacion"]["farmacia"]
    assert farmacia["tiempo_promedio_espera_cola"] == 0.0
    assert farmacia["tiempo_promedio_atencion"] == 0.0
    assert farmacia["longitud_maxima_cola"] == 0
    assert farmacia["por_servidor"]["servidor_1"]["tiempo_ocioso_minutos"] == pytest.approx(DURACION)
    assert farmacia["cola_mas_larga"] == "cola_1"


def test_calcular_metricas_sin_eventos(config_base):
    r = metrics.calcular_metricas([], config_base, DURACION)
    assert r["sistema_completo"] == {"tiempo_promedio_en_sistema": 0.0,
                                     "clientes_promedio_en_sistema": 0.0,
                                     "clientes_totales_atendidos": 0}


@pytest.mark.parametrize("duracion", [0, -5, None, True])
def test_calcular_metricas_duracion_invalida(eventos_base, config_base, duracion):
    with pytest.raises(ValueError):
        metrics.calcular_metricas(eventos_base, config_base, duracion)


@pytest.mark.parametrize("nombre", ["01_paralelo_cola_unica", "02_secuencial_preferencial"])
def test_calcular_metricas_coincide_con_los_resultados_de_ejemplo(nombre):
    """Las métricas calculadas a mano en examples/resultados_ejemplo/."""
    resultado, config = _cargar_ejemplo(nombre)
    calculadas = metrics.calcular_metricas(resultado["eventos_clientes"], config,
                                           resultado["duracion_total_minutos"])
    assert calculadas == _aproximado(resultado["metricas"])


# --- Integración con el motor: simular() ya entrega "metricas" ---

def _simular_ejemplo(nombre):
    config = json.loads((CARPETA_CONFIGS / nombre).read_text(encoding="utf-8"))
    return simular(config)["resultado"], config


@pytest.mark.parametrize("archivo", CONFIGS_EJEMPLO)
def test_simular_los_8_ejemplos_incluye_metricas_validas(archivo):
    resultado, config = _simular_ejemplo(archivo)
    assert validar_resultado(resultado, config, exigir_metricas=True) == []
    metricas = resultado["metricas"]
    assert set(metricas["por_estacion"]) == {e["id"] for e in config["estaciones"]}
    for datos in metricas["por_estacion"].values():
        for servidor in datos["por_servidor"].values():
            assert 0.0 <= servidor["utilizacion"] <= 1.0
        assert datos["longitud_maxima_cola"] >= max(
            c["longitud_maxima"] for c in datos["por_cola"].values())
        assert datos["cola_mas_larga"] in datos["por_cola"]


@pytest.mark.parametrize("archivo", CONFIGS_EJEMPLO)
def test_simular_little_coincide_con_la_integracion(archivo):
    """El motor atiende a todos antes de T: L por Little = L integrando N(t)."""
    resultado, _ = _simular_ejemplo(archivo)
    eventos, duracion = resultado["eventos_clientes"], resultado["duracion_total_minutos"]
    assert resultado["metricas"]["sistema_completo"]["clientes_promedio_en_sistema"] == pytest.approx(
        metrics.clientes_promedio_por_integracion(eventos, duracion))


def test_simular_clientes_atendidos_cuadran_con_los_servidores():
    resultado, _ = _simular_ejemplo("05_secuencial_cola_unica.json")
    metricas = resultado["metricas"]
    total = metricas["sistema_completo"]["clientes_totales_atendidos"]
    assert total == len(resultado["eventos_clientes"])
    for datos in metricas["por_estacion"].values():
        atendidos = sum(s["clientes_atendidos"] for s in datos["por_servidor"].values())
        assert atendidos <= total


def test_simular_metricas_se_pueden_escribir_como_json():
    resultado, _ = _simular_ejemplo("03_paralelo_preferencial.json")
    assert json.loads(json.dumps(resultado["metricas"])) == resultado["metricas"]
