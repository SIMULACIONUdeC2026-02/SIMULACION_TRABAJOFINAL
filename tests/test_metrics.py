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
