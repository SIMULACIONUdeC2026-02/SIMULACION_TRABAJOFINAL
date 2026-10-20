"""Pruebas del validador del contrato de entrada. Responsable: Equipo 2."""
import copy
import json
from pathlib import Path

import pytest

from src.config import validar_config

EJEMPLOS = sorted(
    (Path(__file__).resolve().parent.parent / "examples" / "configs_ejemplo")
    .glob("*.json")
)


# --------------------------------------------------------------------------
# Configuraciones de partida (cada test modifica una copia)
# --------------------------------------------------------------------------

def servidor(id_="s1", media=2):
    return {"id": id_, "servicio": {"tipo": "exponencial", "media": media}}


def estacion(id_="cajeros", servidores=3, tipo="unica", cantidad_colas=1,
             reparticion=None, salidas=None):
    cfg = {
        "id": id_,
        "servidores": [servidor(f"s{i + 1}") for i in range(servidores)],
        "colas": {
            "tipo": tipo,
            "cantidad": cantidad_colas,
            "reparticion": reparticion,
        },
    }
    if salidas is not None:
        cfg["salidas"] = salidas
    return cfg


def simulacion(metodo="paralelo", **extra):
    base = {
        "nombre": "prueba",
        "metodo": metodo,
        "duracion_minutos": 480,
        "semilla": 42,
        "llegada": {"distribucion": "poisson", "lambda_por_hora": 40},
    }
    base.update(extra)
    return base


def config_paralela():
    return {"simulacion": simulacion(), "estaciones": [estacion()]}


def config_secuencial():
    return {
        "simulacion": simulacion("secuencial", estacion_entrada="triaje"),
        "estaciones": [
            estacion("triaje", salidas=[{"hacia": "atencion", "probabilidad": 1}]),
            estacion("atencion"),
        ],
    }


def config_ramificada():
    return {
        "simulacion": simulacion("secuencial", estacion_entrada="triaje"),
        "estaciones": [
            estacion("triaje", salidas=[
                {"hacia": "medicina", "probabilidad": 0.6},
                {"hacia": "farmacia", "probabilidad": 0.4},
            ]),
            estacion("medicina"),
            estacion("farmacia"),
        ],
    }


def assert_error(cfg, fragmento):
    errores = validar_config(cfg)
    assert any(fragmento in e for e in errores), (
        f"se esperaba un error con {fragmento!r}, se obtuvo: {errores}"
    )


# --------------------------------------------------------------------------
# Casos válidos
# --------------------------------------------------------------------------

def test_hay_configuraciones_de_ejemplo():
    assert EJEMPLOS, "examples/configs_ejemplo/ no tiene archivos .json"


@pytest.mark.parametrize("ruta", EJEMPLOS, ids=lambda r: r.name)
def test_los_ejemplos_son_validos(ruta):
    cfg = json.loads(ruta.read_text(encoding="utf-8"))
    assert validar_config(cfg) == []


def test_paralela_valida():
    assert validar_config(config_paralela()) == []


def test_paralela_con_estacion_entrada_igual_a_la_unica_estacion():
    cfg = config_paralela()
    cfg["simulacion"]["estacion_entrada"] = "cajeros"
    assert validar_config(cfg) == []


def test_secuencial_lineal_valida():
    assert validar_config(config_secuencial()) == []


def test_secuencial_ramificada_valida():
    assert validar_config(config_ramificada()) == []


def test_secuencial_con_tres_estaciones_en_serie():
    cfg = {
        "simulacion": simulacion("secuencial", estacion_entrada="a"),
        "estaciones": [
            estacion("a", salidas=[{"hacia": "b", "probabilidad": 1}]),
            estacion("b", salidas=[{"hacia": "c", "probabilidad": 1}]),
            estacion("c"),
        ],
    }
    assert validar_config(cfg) == []


def test_secuencial_el_orden_en_la_lista_no_importa():
    cfg = config_secuencial()
    cfg["estaciones"].reverse()
    assert validar_config(cfg) == []


def test_probabilidades_con_error_de_coma_flotante():
    cfg = config_ramificada()
    cfg["estaciones"][0]["salidas"] = [
        {"hacia": "medicina", "probabilidad": 0.1},
        {"hacia": "farmacia", "probabilidad": 0.2},
        {"hacia": "triaje2", "probabilidad": 0.7},
    ]
    cfg["estaciones"].append(estacion("triaje2"))
    assert validar_config(cfg) == []


def test_servidores_con_distintas_distribuciones():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"] = [
        {"id": "s1", "servicio": {"tipo": "exponencial", "media": 2}},
        {"id": "s2", "servicio": {"tipo": "uniforme", "min": 1, "max": 3}},
    ]
    assert validar_config(cfg) == []


def test_colas_multiples_una_por_servidor():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(tipo="multiple", cantidad_colas=3,
                                  reparticion="mas_corta")]
    assert validar_config(cfg) == []


def test_colas_multiples_con_servidor_unico():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(servidores=1, tipo="multiple",
                                  cantidad_colas=4, reparticion="round_robin")]
    assert validar_config(cfg) == []


def test_colas_preferenciales_validas():
    cfg = config_paralela()
    cfg["simulacion"]["clientes_preferenciales"] = {"proporcion": 0.2}
    cfg["estaciones"] = [estacion(tipo="preferencial", cantidad_colas=2)]
    assert validar_config(cfg) == []


def test_clientes_preferenciales_con_colas_que_no_los_priorizan():
    # La clase se conserva aunque esta estación no la use (p. ej. el triaje).
    cfg = config_paralela()
    cfg["simulacion"]["clientes_preferenciales"] = {"proporcion": 0.3}
    assert validar_config(cfg) == []


def test_secuencial_con_preferencial_solo_en_la_segunda_estacion():
    cfg = config_secuencial()
    cfg["simulacion"]["clientes_preferenciales"] = {"proporcion": 0.2}
    cfg["estaciones"][1] = estacion("atencion", tipo="preferencial",
                                    cantidad_colas=2)
    assert validar_config(cfg) == []


# --------------------------------------------------------------------------
# Estructura general
# --------------------------------------------------------------------------

@pytest.mark.parametrize("basura", [None, [], "texto", 42])
def test_config_que_no_es_objeto(basura):
    assert validar_config(basura) == ["config: debe ser un objeto (diccionario)"]


def test_falta_simulacion():
    cfg = config_paralela()
    del cfg["simulacion"]
    assert_error(cfg, "simulacion: es obligatorio")


def test_estaciones_vacia():
    cfg = config_paralela()
    cfg["estaciones"] = []
    assert_error(cfg, "estaciones: debe ser una lista")


def test_estacion_que_no_es_objeto():
    cfg = config_paralela()
    cfg["estaciones"] = ["cajeros"]
    assert_error(cfg, "estaciones[0]: debe ser un objeto")


def test_no_modifica_la_configuracion_recibida():
    cfg = config_ramificada()
    copia = copy.deepcopy(cfg)
    validar_config(cfg)
    assert cfg == copia


def test_reporta_varios_errores_a_la_vez():
    cfg = config_paralela()
    cfg["simulacion"]["metodo"] = "otro"
    cfg["simulacion"]["duracion_minutos"] = 0
    cfg["simulacion"]["llegada"]["lambda_por_hora"] = -5
    assert len(validar_config(cfg)) >= 3


@pytest.mark.parametrize("bloque, clave", [
    ("raiz", "extra"),
    ("simulacion", "replicas"),
    ("llegada", "tasa"),
    ("estacion", "reparticon"),
    ("servidor", "velocidad"),
    ("colas", "reparticon"),
])
def test_claves_desconocidas_se_reportan(bloque, clave):
    cfg = config_paralela()
    objetivo = {
        "raiz": cfg,
        "simulacion": cfg["simulacion"],
        "llegada": cfg["simulacion"]["llegada"],
        "estacion": cfg["estaciones"][0],
        "servidor": cfg["estaciones"][0]["servidores"][0],
        "colas": cfg["estaciones"][0]["colas"],
    }[bloque]
    objetivo[clave] = 1
    assert_error(cfg, f"la clave {clave!r} no existe")


# --------------------------------------------------------------------------
# Bloque simulacion
# --------------------------------------------------------------------------

def test_metodo_invalido():
    cfg = config_paralela()
    cfg["simulacion"]["metodo"] = "mixto"
    assert_error(cfg, "simulacion.metodo")


@pytest.mark.parametrize("valor", [0, -10, "480", None, True])
def test_duracion_invalida(valor):
    cfg = config_paralela()
    cfg["simulacion"]["duracion_minutos"] = valor
    assert_error(cfg, "simulacion.duracion_minutos")


def test_semilla_invalida():
    cfg = config_paralela()
    cfg["simulacion"]["semilla"] = 3.5
    assert_error(cfg, "simulacion.semilla")


def test_semilla_es_opcional():
    cfg = config_paralela()
    del cfg["simulacion"]["semilla"]
    assert validar_config(cfg) == []


def test_llegada_no_poisson():
    cfg = config_paralela()
    cfg["simulacion"]["llegada"]["distribucion"] = "uniforme"
    assert_error(cfg, "simulacion.llegada.distribucion")


@pytest.mark.parametrize("valor", [0, -1, "40", None])
def test_lambda_invalida(valor):
    cfg = config_paralela()
    cfg["simulacion"]["llegada"]["lambda_por_hora"] = valor
    assert_error(cfg, "simulacion.llegada.lambda_por_hora")


@pytest.mark.parametrize("proporcion", [0, 1, 1.5, -0.1, "0.2", None])
def test_proporcion_de_preferenciales_invalida(proporcion):
    cfg = config_paralela()
    cfg["simulacion"]["clientes_preferenciales"] = {"proporcion": proporcion}
    assert_error(cfg, "clientes_preferenciales.proporcion")


def test_clientes_preferenciales_que_no_es_objeto():
    cfg = config_paralela()
    cfg["simulacion"]["clientes_preferenciales"] = 0.2
    assert_error(cfg, "clientes_preferenciales: debe ser un objeto")


def test_estacion_entrada_obligatoria_en_secuencial():
    cfg = config_secuencial()
    del cfg["simulacion"]["estacion_entrada"]
    assert_error(cfg, "estacion_entrada: es obligatoria")


def test_estacion_entrada_inexistente():
    cfg = config_secuencial()
    cfg["simulacion"]["estacion_entrada"] = "no_existe"
    assert_error(cfg, "no es una estación existente")


def test_estacion_entrada_distinta_en_paralelo():
    cfg = config_paralela()
    cfg["simulacion"]["estacion_entrada"] = "otra"
    assert_error(cfg, "no coincide con la única estación")


def test_llegada_dentro_de_estacion_no_existe():
    # La llegada vive solo en "simulacion".
    cfg = config_paralela()
    cfg["estaciones"][0]["llegada"] = {"distribucion": "poisson"}
    assert_error(cfg, "la clave 'llegada' no existe")


# --------------------------------------------------------------------------
# Estaciones y servidores
# --------------------------------------------------------------------------

def test_id_de_estacion_vacio():
    cfg = config_paralela()
    cfg["estaciones"][0]["id"] = "  "
    assert_error(cfg, "estaciones[0].id")


def test_ids_de_estacion_repetidos():
    cfg = config_secuencial()
    cfg["estaciones"][1]["id"] = "triaje"
    assert_error(cfg, "está repetido")


@pytest.mark.parametrize("valor", [None, [], "s1", {}])
def test_servidores_deben_ser_lista_no_vacia(valor):
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"] = valor
    assert_error(cfg, "servidores: debe ser una lista con al menos un servidor")


def test_servidor_que_no_es_objeto():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"] = ["s1"]
    assert_error(cfg, "servidores[0]: debe ser un objeto")


def test_id_de_servidor_vacio():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["id"] = ""
    assert_error(cfg, "servidores[0].id")


def test_ids_de_servidor_repetidos():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][1]["id"] = "s1"
    assert_error(cfg, "servidores: el id 's1' está repetido")


def test_servidor_sin_servicio():
    cfg = config_paralela()
    del cfg["estaciones"][0]["servidores"][0]["servicio"]
    assert_error(cfg, "servidores[0].servicio: es obligatorio")


def test_tipo_de_servicio_invalido():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["servicio"] = {"tipo": "normal"}
    assert_error(cfg, "servicio.tipo")


@pytest.mark.parametrize("media", [0, -1, "2", None])
def test_media_exponencial_invalida(media):
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["servicio"]["media"] = media
    assert_error(cfg, "servicio.media")


def test_exponencial_con_limites_de_uniforme():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["servicio"]["min"] = 1
    assert_error(cfg, "la clave 'min' no existe")


@pytest.mark.parametrize("minimo, maximo", [(1, 1), (2, 1)])
def test_uniforme_con_min_no_menor_que_max(minimo, maximo):
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["servicio"] = {
        "tipo": "uniforme", "min": minimo, "max": maximo,
    }
    assert_error(cfg, "'min' debe ser menor que 'max'")


def test_uniforme_sin_limites():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["servicio"] = {"tipo": "uniforme"}
    errores = validar_config(cfg)
    assert any(".min" in e for e in errores)
    assert any(".max" in e for e in errores)


def test_uniforme_con_min_negativo():
    cfg = config_paralela()
    cfg["estaciones"][0]["servidores"][0]["servicio"] = {
        "tipo": "uniforme", "min": -1, "max": 2,
    }
    assert_error(cfg, "servicio.min")


# --------------------------------------------------------------------------
# Colas
# --------------------------------------------------------------------------

def test_tipo_de_cola_invalido():
    cfg = config_paralela()
    cfg["estaciones"][0]["colas"]["tipo"] = "circular"
    assert_error(cfg, "colas.tipo")


def test_cantidad_de_colas_invalida():
    cfg = config_paralela()
    cfg["estaciones"][0]["colas"]["cantidad"] = 0
    assert_error(cfg, "colas.cantidad")


def test_cola_unica_con_mas_de_una_cola():
    cfg = config_paralela()
    cfg["estaciones"][0]["colas"]["cantidad"] = 2
    assert_error(cfg, "requiere cantidad = 1")


def test_cola_unica_con_reparticion():
    cfg = config_paralela()
    cfg["estaciones"][0]["colas"]["reparticion"] = "round_robin"
    assert_error(cfg, "debe ser null cuando hay una sola cola")


def test_colas_multiples_con_una_sola_cola():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(servidores=1, tipo="multiple",
                                  cantidad_colas=1, reparticion="aleatoria")]
    assert_error(cfg, "requiere cantidad >= 2")


def test_colas_multiples_sin_reparticion():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(tipo="multiple", cantidad_colas=3)]
    assert_error(cfg, "reparticion: es obligatoria")


def test_reparticion_invalida():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(tipo="multiple", cantidad_colas=3,
                                  reparticion="al_azar")]
    assert_error(cfg, "colas.reparticion")


def test_colas_multiples_distinto_numero_que_servidores():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(servidores=3, tipo="multiple",
                                  cantidad_colas=5, reparticion="mas_corta")]
    assert_error(cfg, "una cola por servidor")


def test_colas_preferenciales_sin_definir_clientes_preferenciales():
    cfg = config_paralela()
    cfg["estaciones"] = [estacion(tipo="preferencial", cantidad_colas=2)]
    assert_error(cfg, "requiere definir simulacion.clientes_preferenciales")


@pytest.mark.parametrize("cantidad", [1, 3])
def test_colas_preferenciales_requieren_exactamente_dos(cantidad):
    cfg = config_paralela()
    cfg["simulacion"]["clientes_preferenciales"] = {"proporcion": 0.2}
    cfg["estaciones"] = [estacion(tipo="preferencial", cantidad_colas=cantidad)]
    assert_error(cfg, "requiere exactamente 2 colas")


def test_colas_preferenciales_con_reparticion():
    cfg = config_paralela()
    cfg["simulacion"]["clientes_preferenciales"] = {"proporcion": 0.2}
    cfg["estaciones"] = [estacion(tipo="preferencial", cantidad_colas=2,
                                  reparticion="round_robin")]
    assert_error(cfg, "debe ser null con colas 'preferencial'")


# --------------------------------------------------------------------------
# Método paralelo y secuencial, rutas
# --------------------------------------------------------------------------

def test_paralelo_con_dos_estaciones():
    cfg = config_paralela()
    cfg["estaciones"].append(estacion("otra"))
    assert_error(cfg, "requiere exactamente 1 estación")


def test_paralelo_con_salidas():
    cfg = config_paralela()
    cfg["estaciones"][0]["salidas"] = [{"hacia": "otra", "probabilidad": 1}]
    assert_error(cfg, "debe estar vacía en el método 'paralelo'")


def test_secuencial_con_una_sola_estacion():
    cfg = config_secuencial()
    cfg["estaciones"] = [estacion("triaje")]
    assert_error(cfg, "requiere al menos 2 estaciones")


def test_salidas_que_no_son_lista():
    cfg = config_secuencial()
    cfg["estaciones"][0]["salidas"] = {"hacia": "atencion"}
    assert_error(cfg, "salidas: debe ser una lista")


def test_salida_con_destino_inexistente():
    cfg = config_secuencial()
    cfg["estaciones"][0]["salidas"][0]["hacia"] = "no_existe"
    assert_error(cfg, "que no existe")


@pytest.mark.parametrize("probabilidad", [0, -0.5, 1.5, "1", None])
def test_probabilidad_de_salida_invalida(probabilidad):
    cfg = config_secuencial()
    cfg["estaciones"][0]["salidas"][0]["probabilidad"] = probabilidad
    assert_error(cfg, "salidas[0].probabilidad")


def test_probabilidades_que_no_suman_uno():
    cfg = config_ramificada()
    cfg["estaciones"][0]["salidas"][1]["probabilidad"] = 0.3
    assert_error(cfg, "las probabilidades deben sumar 1")


def test_destino_repetido_en_salidas():
    cfg = config_ramificada()
    cfg["estaciones"][0]["salidas"][1]["hacia"] = "medicina"
    assert_error(cfg, "el destino 'medicina' está repetido")


def test_ciclo_entre_estaciones():
    cfg = config_secuencial()
    cfg["estaciones"][1]["salidas"] = [{"hacia": "triaje", "probabilidad": 1}]
    assert_error(cfg, "forman un ciclo")


def test_estacion_que_se_envia_a_si_misma():
    cfg = config_secuencial()
    cfg["estaciones"][1]["salidas"] = [{"hacia": "atencion", "probabilidad": 1}]
    assert_error(cfg, "forman un ciclo")


def test_estacion_no_alcanzable_desde_la_entrada():
    cfg = config_secuencial()
    cfg["estaciones"][0]["salidas"] = []  # el triaje no envía a nadie
    assert_error(cfg, "no es alcanzable desde la estación de entrada")
