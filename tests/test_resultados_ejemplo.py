"""Pruebas de los resultados de ejemplo. Responsables: Equipo 3 (Métricas).

Comprueban que cada archivo de examples/resultados_ejemplo/ respeta el
contrato de salida (docs/contratos.md) y que es coherente con la
configuración con la que va emparejado. Así Equipo 3 y Equipo 4 pueden
trabajar con datos de prueba mientras el motor no está listo.
"""
import json
from pathlib import Path

import pytest

from src.config import validar_config

CARPETA = Path(__file__).resolve().parent.parent / "examples" / "resultados_ejemplo"
RESULTADOS = sorted(CARPETA.glob("*_resultado.json"))

CLAVES_CLIENTE = {"cliente_id", "es_preferencial", "tiempo_entrada_sistema",
                  "tiempo_salida_sistema", "paradas"}
CLAVES_PARADA = {"estacion_id", "tiempo_inicio_espera", "tiempo_inicio_servicio",
                 "tiempo_fin_servicio", "servidor_asignado", "cola_asignada"}
CLAVES_ESTACION = {"tiempo_promedio_espera_cola", "tiempo_promedio_atencion",
                   "longitud_promedio_cola", "longitud_maxima_cola",
                   "por_servidor", "por_cola", "cola_mas_larga"}


def _cargar(ruta: Path) -> dict:
    """Lee un JSON en UTF-8 y lo devuelve como diccionario."""
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def _par(ruta_resultado: Path) -> tuple[dict, dict]:
    """Devuelve (resultado, config) de un archivo *_resultado.json."""
    ruta_config = ruta_resultado.with_name(
        ruta_resultado.name.replace("_resultado.json", "_config.json"))
    return _cargar(ruta_resultado)["resultado"], _cargar(ruta_config)


def test_hay_resultados_de_ejemplo():
    assert RESULTADOS, "examples/resultados_ejemplo/ no tiene *_resultado.json"


@pytest.mark.parametrize("ruta", RESULTADOS, ids=lambda r: r.name)
def test_config_emparejada_es_valida(ruta):
    _, config = _par(ruta)
    assert validar_config(config) == []


@pytest.mark.parametrize("ruta", RESULTADOS, ids=lambda r: r.name)
def test_forma_del_contrato_de_salida(ruta):
    resultado, config = _par(ruta)
    assert set(resultado) == {"simulacion_id", "duracion_total_minutos",
                              "eventos_clientes", "metricas"}
    assert resultado["duracion_total_minutos"] == config["simulacion"]["duracion_minutos"]

    ids = [c["cliente_id"] for c in resultado["eventos_clientes"]]
    assert len(ids) == len(set(ids)), "cliente_id repetido"

    for cliente in resultado["eventos_clientes"]:
        assert set(cliente) == CLAVES_CLIENTE
        assert isinstance(cliente["es_preferencial"], bool)
        assert cliente["paradas"], "cada cliente tiene al menos una parada"
        for parada in cliente["paradas"]:
            assert set(parada) == CLAVES_PARADA

    metricas = resultado["metricas"]
    assert set(metricas["sistema_completo"]) == {
        "tiempo_promedio_en_sistema", "clientes_promedio_en_sistema",
        "clientes_totales_atendidos"}
    for estacion in metricas["por_estacion"].values():
        assert set(estacion) == CLAVES_ESTACION


@pytest.mark.parametrize("ruta", RESULTADOS, ids=lambda r: r.name)
def test_tiempos_ordenados_y_coherentes(ruta):
    resultado, _ = _par(ruta)
    duracion = resultado["duracion_total_minutos"]
    for cliente in resultado["eventos_clientes"]:
        paradas = cliente["paradas"]
        assert cliente["tiempo_entrada_sistema"] == paradas[0]["tiempo_inicio_espera"]
        assert cliente["tiempo_salida_sistema"] == paradas[-1]["tiempo_fin_servicio"]
        assert 0 <= cliente["tiempo_entrada_sistema"] <= cliente["tiempo_salida_sistema"] <= duracion
        for anterior, siguiente in zip(paradas, paradas[1:]):
            assert anterior["tiempo_fin_servicio"] <= siguiente["tiempo_inicio_espera"]
        for p in paradas:
            assert p["tiempo_inicio_espera"] <= p["tiempo_inicio_servicio"] <= p["tiempo_fin_servicio"]


@pytest.mark.parametrize("ruta", RESULTADOS, ids=lambda r: r.name)
def test_paradas_respetan_la_config(ruta):
    resultado, config = _par(ruta)
    estaciones = {e["id"]: e for e in config["estaciones"]}
    hay_preferenciales = "clientes_preferenciales" in config["simulacion"]
    entrada = config["simulacion"].get("estacion_entrada", config["estaciones"][0]["id"])

    for cliente in resultado["eventos_clientes"]:
        if cliente["es_preferencial"]:
            assert hay_preferenciales
        paradas = cliente["paradas"]
        assert paradas[0]["estacion_id"] == entrada
        for i, parada in enumerate(paradas):
            estacion = estaciones[parada["estacion_id"]]
            assert 1 <= parada["servidor_asignado"] <= len(estacion["servidores"])
            assert 1 <= parada["cola_asignada"] <= estacion["colas"]["cantidad"]
            if estacion["colas"]["tipo"] == "preferencial":
                cola_esperada = 1 if cliente["es_preferencial"] else 2
                assert parada["cola_asignada"] == cola_esperada
            destinos = [s["hacia"] for s in estacion.get("salidas") or []]
            if i + 1 < len(paradas):
                assert paradas[i + 1]["estacion_id"] in destinos
            else:
                assert destinos == [], "la última parada debe ser una estación de salida"

    assert set(resultado["metricas"]["por_estacion"]) <= set(estaciones)


@pytest.mark.parametrize("ruta", RESULTADOS, ids=lambda r: r.name)
def test_metricas_del_sistema_cuadran_con_los_eventos(ruta):
    """Recalcula W, L (Little) y atendidos a mano, sin usar metrics.py."""
    resultado, _ = _par(ruta)
    eventos = resultado["eventos_clientes"]
    duracion = resultado["duracion_total_minutos"]
    tiempos = [c["tiempo_salida_sistema"] - c["tiempo_entrada_sistema"] for c in eventos]
    w = sum(tiempos) / len(tiempos)
    l = (len(eventos) / duracion) * w

    sistema = resultado["metricas"]["sistema_completo"]
    assert sistema["clientes_totales_atendidos"] == len(eventos)
    assert sistema["tiempo_promedio_en_sistema"] == pytest.approx(w, abs=1e-4)
    assert sistema["clientes_promedio_en_sistema"] == pytest.approx(l, abs=1e-4)
