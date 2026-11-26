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
