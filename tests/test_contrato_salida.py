"""Pruebas de validar_resultado (src/contrato_salida.py). Responsables: Equipo 2 (Topologías).

Para qué existen, en una frase: que cualquier desviación del contrato de salida
se detecte con una prueba y no con una conversación entre equipos.

Qué comprueban
    1. Los resultados de ejemplo (los que usan Métricas y UI mientras el motor
       no está listo) cumplen el contrato.
    2. La salida real del motor (Engine) cumple el mismo contrato, incluido un
       caso de carga alta donde la cola se vacía después del cierre.
    3. El validador de verdad detecta los defectos: cada prueba de "violaciones"
       introduce un error a propósito y exige que sea reportado. Sin ellas no
       sabríamos si el validador es de fiar o si da luz verde a todo.

Qué hacer cuando una de estas pruebas falla
    - Si falla una de la salida del motor: Engine revisa su PR.
    - Si falla una de los ejemplos: quien los editó los corrige.
    - Si el validador pide algo que el contrato no dice: se abre un issue y se
      decide en un solo lugar (docs/contratos.md) antes de tocar el código.
"""
import copy
import json
from pathlib import Path

import pytest

from src.contrato_salida import validar_resultado
from src.engine import ejecutar_simulacion

RAIZ = Path(__file__).resolve().parent.parent
CONFIGS = RAIZ / "examples" / "configs_ejemplo"
RESULTADOS = sorted((RAIZ / "examples" / "resultados_ejemplo").glob("*_resultado.json"))


def _json(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def _config(nombre: str) -> dict:
    return _json(CONFIGS / nombre)


def _cliente(cid, entrada, inicio, fin, servidor=1, estacion="cajeros", cola=1):
    """Cliente de una sola parada (cola única de 01_paralelo_cola_unica)."""
    return {
        "cliente_id": cid, "es_preferencial": False,
        "tiempo_entrada_sistema": entrada, "tiempo_salida_sistema": fin,
        "paradas": [{"estacion_id": estacion, "tiempo_inicio_espera": entrada,
                     "tiempo_inicio_servicio": inicio, "tiempo_fin_servicio": fin,
                     "servidor_asignado": servidor, "cola_asignada": cola}],
    }


def _resultado_valido() -> dict:
    """Resultado mínimo y correcto para 01_paralelo_cola_unica (cierre = 480)."""
    return {"simulacion_id": "prueba", "duracion_total_minutos": 480,
            "eventos_clientes": [_cliente(1, 1.0, 1.0, 5.0, servidor=1),
                                 _cliente(2, 2.0, 2.0, 6.0, servidor=2)]}


# ---------------------------------------------------------------- casos válidos

def test_resultado_minimo_valido():
    assert validar_resultado(_resultado_valido(), _config("01_paralelo_cola_unica.json")) == []


def test_sin_clientes_devuelve_la_duracion_configurada():
    resultado = {"simulacion_id": "x", "duracion_total_minutos": 480, "eventos_clientes": []}
    assert validar_resultado(resultado, _config("01_paralelo_cola_unica.json")) == []


@pytest.mark.parametrize("ruta", RESULTADOS, ids=lambda r: r.name)
def test_resultados_de_ejemplo_cumplen_el_contrato(ruta):
    config = _json(ruta.with_name(ruta.name.replace("_resultado", "_config")))
    resultado = _json(ruta)["resultado"]
    assert validar_resultado(resultado, config, exigir_metricas=True) == []


def test_serie_de_dos_estaciones_valida():
    """El motor aún no corre la serie, pero el contrato ya se puede probar a mano."""
    config = _config("05_secuencial_cola_unica.json")
    cliente = {
        "cliente_id": 1, "es_preferencial": False,
        "tiempo_entrada_sistema": 1.0, "tiempo_salida_sistema": 9.0,
        "paradas": [
            {"estacion_id": "triaje", "tiempo_inicio_espera": 1.0,
             "tiempo_inicio_servicio": 1.0, "tiempo_fin_servicio": 3.0,
             "servidor_asignado": 1, "cola_asignada": 1},
            {"estacion_id": "atencion", "tiempo_inicio_espera": 3.0,
             "tiempo_inicio_servicio": 5.0, "tiempo_fin_servicio": 9.0,
             "servidor_asignado": 2, "cola_asignada": 1},
        ],
    }
    resultado = {"simulacion_id": "serie", "duracion_total_minutos": 480,
                 "eventos_clientes": [cliente]}
    assert validar_resultado(resultado, config) == []

    # saltarse una estación o terminar en una que tiene salidas es un error
    solo_triaje = copy.deepcopy(resultado)
    solo_triaje["eventos_clientes"][0]["paradas"].pop()
    solo_triaje["eventos_clientes"][0]["tiempo_salida_sistema"] = 3.0
    assert any("sin salidas" in e for e in validar_resultado(solo_triaje, config))

    al_reves = copy.deepcopy(resultado)
    al_reves["eventos_clientes"][0]["paradas"][1]["estacion_id"] = "triaje"
    assert any("no se puede pasar" in e for e in validar_resultado(al_reves, config))


# ------------------------------------------------------------ salida del motor

@pytest.mark.parametrize("semilla", [1, 7, 42, 2026])
def test_salida_real_del_motor_cumple_el_contrato(semilla):
    config = _config("01_paralelo_cola_unica.json")
    config["simulacion"]["semilla"] = semilla
    assert validar_resultado(ejecutar_simulacion(config), config) == []


def test_motor_con_carga_alta_alarga_la_duracion_y_sigue_siendo_valido():
    """Utilización ~0,97: la cola se vacía después del cierre (T > duración)."""
    config = _config("01_paralelo_cola_unica.json")
    config["simulacion"]["llegada"]["lambda_por_hora"] = 60 * (3 / 4) * 0.97  # 3 servidores, media 4
    config["simulacion"]["semilla"] = 3
    resultado = ejecutar_simulacion(config)
    assert resultado["duracion_total_minutos"] > config["simulacion"]["duracion_minutos"], \
        "la prueba no ejercita la política de cierre: súbase la carga"
    assert validar_resultado(resultado, config) == []


# --------------------------------------------------------- violaciones del contrato

def _mutar(funcion):
    resultado = _resultado_valido()
    funcion(resultado)
    return resultado


CASOS_INVALIDOS = [
    ("falta clave", lambda r: r.pop("eventos_clientes"), "falta la clave 'eventos_clientes'"),
    ("clave desconocida", lambda r: r.update(extra=1), "clave desconocida 'extra'"),
    ("duracion no es el máximo", lambda r: r.update(duracion_total_minutos=500),
     "debe ser el máximo"),
    ("duracion menor que el cierre", lambda r: r.update(duracion_total_minutos=100),
     "debe ser el máximo"),
    ("cliente repetido", lambda r: r["eventos_clientes"][1].update(cliente_id=1), "repetido"),
    ("salida null", lambda r: r["eventos_clientes"][0].update(tiempo_salida_sistema=None),
     "sin null"),
    ("salida antes de entrar", lambda r: r["eventos_clientes"][0].update(tiempo_salida_sistema=0.5),
     "antes de entrar"),
    ("entra después del cierre", lambda r: r["eventos_clientes"][0].update(tiempo_entrada_sistema=480),
     "no hay llegadas en el cierre"),
    ("servidor fuera de rango",
     lambda r: r["eventos_clientes"][0]["paradas"][0].update(servidor_asignado=9),
     "servidor_asignado"),
    ("cola fuera de rango",
     lambda r: r["eventos_clientes"][0]["paradas"][0].update(cola_asignada=2),
     "cola_asignada"),
    ("estación inexistente",
     lambda r: r["eventos_clientes"][0]["paradas"][0].update(estacion_id="fantasma"),
     "no existe en la config"),
    ("preferencial sin config",
     lambda r: r["eventos_clientes"][0].update(es_preferencial=True),
     "clientes_preferenciales"),
    ("espera después del servicio",
     lambda r: r["eventos_clientes"][0]["paradas"][0].update(tiempo_inicio_servicio=0.1),
     "inicio_espera <= inicio_servicio"),
    ("NaN en un tiempo",
     lambda r: r["eventos_clientes"][0]["paradas"][0].update(tiempo_fin_servicio=float("nan")),
     "número finito"),
    ("cliente sin paradas", lambda r: r["eventos_clientes"][0].update(paradas=[]),
     "al menos una parada"),
]


@pytest.mark.parametrize("nombre, cambio, fragmento", CASOS_INVALIDOS,
                         ids=[c[0] for c in CASOS_INVALIDOS])
def test_detecta_violaciones(nombre, cambio, fragmento):
    errores = validar_resultado(_mutar(cambio), _config("01_paralelo_cola_unica.json"))
    assert any(fragmento in e for e in errores), errores


def test_detecta_servidor_atendiendo_a_dos_clientes_a_la_vez():
    """Es la comprobación de la que depende el cálculo del tiempo ocioso."""
    resultado = {"simulacion_id": "x", "duracion_total_minutos": 480,
                 "eventos_clientes": [_cliente(1, 1.0, 1.0, 5.0, servidor=1),
                                      _cliente(2, 2.0, 2.0, 6.0, servidor=1)]}
    errores = validar_resultado(resultado, _config("01_paralelo_cola_unica.json"))
    assert any("antes de que termine" in e for e in errores), errores


def test_servicios_pegados_en_el_mismo_servidor_son_validos():
    resultado = {"simulacion_id": "x", "duracion_total_minutos": 480,
                 "eventos_clientes": [_cliente(1, 1.0, 1.0, 5.0, servidor=1),
                                      _cliente(2, 2.0, 5.0, 9.0, servidor=1)]}
    assert validar_resultado(resultado, _config("01_paralelo_cola_unica.json")) == []


def test_metricas_con_forma_incorrecta():
    config = _config("01_paralelo_cola_unica.json")
    resultado = _resultado_valido()
    resultado["metricas"] = {"sistema_completo": {}, "por_estacion": {}}
    assert any("sistema_completo" in e for e in validar_resultado(resultado, config))
    assert any("falta el bloque 'metricas'" in e
               for e in validar_resultado(_resultado_valido(), config, exigir_metricas=True))


# ----------------------------------------------------------------- robustez

@pytest.mark.parametrize("basura", [None, [], "texto", 5, {}, {"eventos_clientes": 3},
                                    {"simulacion_id": "x", "duracion_total_minutos": 480,
                                     "eventos_clientes": [None, 3, {}, {"paradas": 1}]}])
def test_no_lanza_excepciones_con_datos_mal_formados(basura):
    errores = validar_resultado(basura, _config("01_paralelo_cola_unica.json"))
    assert isinstance(errores, list) and errores


def test_config_invalida_se_reporta_sin_lanzar():
    assert validar_resultado(_resultado_valido(), {})[0].startswith("config inválida")
    assert validar_resultado(_resultado_valido(), None) == ["config: debe ser un diccionario"]
