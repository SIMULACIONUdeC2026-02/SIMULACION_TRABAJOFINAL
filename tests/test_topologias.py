"""Pruebas de las topologías. Responsables: Equipo 2 (Topologías)."""
import json
import pathlib

import pytest

from src.config import validar_config
from src import topologias
from src.topologias import METODOS, VARIANTES, construir_config

# Ruta al ejemplo de referencia
_EJEMPLO_01 = (
    pathlib.Path(__file__).resolve().parent.parent
    / "examples" / "configs_ejemplo" / "01_paralelo_cola_unica.json"
)


# --------------------------------------------------------------------------
# Tests requeridos
# --------------------------------------------------------------------------

def test_config_por_defecto_es_valida():
    """La configuración generada con valores por defecto pasa validar_config."""
    config = construir_config("paralelo", "cola_unica_multiples_servidores")
    errores = validar_config(config)
    assert errores == [], f"Errores de validación: {errores}"


def test_config_por_defecto_coincide_con_ejemplo_01():
    """El dict generado por defecto es idéntico al contenido de 01_paralelo_cola_unica.json."""
    config = construir_config("paralelo", "cola_unica_multiples_servidores")
    ejemplo = json.loads(_EJEMPLO_01.read_text(encoding="utf-8"))
    assert config == ejemplo


def test_cambiar_n_servidores_a_5():
    """Con n_servidores=5 se generan 5 servidores válidos."""
    config = construir_config(
        "paralelo", "cola_unica_multiples_servidores", n_servidores=5,
    )
    errores = validar_config(config)
    assert errores == [], f"Errores de validación: {errores}"

    servidores = config["estaciones"][0]["servidores"]
    assert len(servidores) == 5
    ids = [s["id"] for s in servidores]
    assert ids == ["s1", "s2", "s3", "s4", "s5"]


def test_variante_inexistente_lanza_value_error():
    """Una variante que no existe lanza ValueError."""
    with pytest.raises(ValueError, match="Variante desconocida"):
        construir_config("paralelo", "variante_que_no_existe")


# --------------------------------------------------------------------------
# Tests adicionales de robustez
# --------------------------------------------------------------------------

def test_metodo_inexistente_lanza_value_error():
    """Un método que no existe lanza ValueError."""
    with pytest.raises(ValueError, match="Método desconocido"):
        construir_config("inexistente", "cola_unica_multiples_servidores")


def test_combinacion_no_implementada_lanza_not_implemented(monkeypatch):
    """Si la función de una combinación aún no está hecha, construir_config
    deja pasar su NotImplementedError. Se usa un constructor falso para que
    este test no se rompa cuando alguien implemente una variante real."""
    def pendiente(**parametros):
        raise NotImplementedError("pendiente")

    monkeypatch.setitem(
        topologias._CONSTRUCTORES,
        ("paralelo", "colas_multiples_multiples_servidores"),
        pendiente,
    )
    with pytest.raises(NotImplementedError):
        construir_config("paralelo", "colas_multiples_multiples_servidores")


def test_sistema_inestable_lanza_value_error():
    """Si ρ ≥ 1 la función rechaza la configuración antes de construirla."""
    with pytest.raises(ValueError, match="inestable"):
        construir_config(
            "paralelo",
            "cola_unica_multiples_servidores",
            lambda_por_hora=200,
            n_servidores=1,
            media_servicio=10,
        )


# --------------------------------------------------------------------------
# Tests de validación de parámetros (PR feedback)
# --------------------------------------------------------------------------

def test_casos_tabla_pr_29():
    """
    Verifica exactamente los casos de la tabla comparativa del PR #29:
    - n_servidores=0 -> ValueError claro (antes ZeroDivisionError)
    - n_servidores=2.5 -> ValueError claro (antes TypeError)
    - n_servidores=True -> ValueError claro (antes se trataba como 1 servidor)
    - lambda_por_hora="40" -> ValueError claro (antes TypeError)
    - lambda_por_hora=0 -> ValueError claro (antes lo aceptaba y solo validar_config lo rechazaba)
    - media_servicio=-3 -> ValueError claro (antes lo aceptaba y solo validar_config lo rechazaba)
    """
    # 1. n_servidores = 0
    with pytest.raises(ValueError, match="n_servidores"):
        construir_config("paralelo", "cola_unica_multiples_servidores", n_servidores=0)

    # 2. n_servidores = 2.5
    with pytest.raises(ValueError, match="n_servidores"):
        construir_config("paralelo", "cola_unica_multiples_servidores", n_servidores=2.5)

    # 3. n_servidores = True
    with pytest.raises(ValueError, match="n_servidores"):
        construir_config("paralelo", "cola_unica_multiples_servidores", n_servidores=True)

    # 4. lambda_por_hora = "40"
    with pytest.raises(ValueError, match="lambda_por_hora"):
        construir_config("paralelo", "cola_unica_multiples_servidores", lambda_por_hora="40")

    # 5. lambda_por_hora = 0
    with pytest.raises(ValueError, match="lambda_por_hora"):
        construir_config("paralelo", "cola_unica_multiples_servidores", lambda_por_hora=0)

    # 6. media_servicio = -3
    with pytest.raises(ValueError, match="media_servicio"):
        construir_config("paralelo", "cola_unica_multiples_servidores", media_servicio=-3)



@pytest.mark.parametrize(
    "param_kwargs,mensaje_esperado",
    [
        ({"n_servidores": -2}, "n_servidores"),
        ({"n_servidores": False}, "n_servidores"),
        ({"n_servidores": "3"}, "n_servidores"),
        ({"lambda_por_hora": 0}, "lambda_por_hora"),
        ({"lambda_por_hora": -15}, "lambda_por_hora"),
        ({"lambda_por_hora": True}, "lambda_por_hora"),
        ({"media_servicio": 0}, "media_servicio"),
        ({"media_servicio": -5}, "media_servicio"),
        ({"media_servicio": "4"}, "media_servicio"),
        ({"media_servicio": True}, "media_servicio"),
        ({"duracion_minutos": 0}, "duracion_minutos"),
        ({"duracion_minutos": -60}, "duracion_minutos"),
        ({"duracion_minutos": "480"}, "duracion_minutos"),
        ({"duracion_minutos": True}, "duracion_minutos"),
        ({"semilla": 1.5}, "semilla"),
        ({"semilla": "42"}, "semilla"),
        ({"semilla": True}, "semilla"),
    ],
)
def test_otros_parametros_invalidos_lanzan_value_error(param_kwargs, mensaje_esperado):
    """Otros tipos o valores no permitidos deben lanzar ValueError con mensaje claro."""
    with pytest.raises(ValueError, match=mensaje_esperado):
        construir_config(
            "paralelo",
            "cola_unica_multiples_servidores",
            **param_kwargs,
        )


# --------------------------------------------------------------------------
# Tabla de despacho: las 8 variantes (Issue de Topologías)
# --------------------------------------------------------------------------

_CARPETA_EJEMPLOS = _EJEMPLO_01.parent

# (metodo, variante) -> ejemplo que debe reproducir con los valores por defecto
EJEMPLO_POR_VARIANTE = {
    ("paralelo", "cola_unica_multiples_servidores"): "01_paralelo_cola_unica.json",
    ("paralelo", "colas_multiples_multiples_servidores"): "02_paralelo_colas_multiples.json",
    ("paralelo", "colas_multiples_preferencial_multiples_servidores"): "03_paralelo_preferencial.json",
    ("paralelo", "colas_multiples_servidor_unico"): "04_paralelo_servidor_unico.json",
    ("secuencial", "cola_unica_multiples_servidores"): "05_secuencial_cola_unica.json",
    ("secuencial", "colas_multiples_multiples_servidores"): "06_secuencial_colas_multiples.json",
    ("secuencial", "colas_multiples_preferencial_multiples_servidores"): "07_secuencial_preferencial.json",
    ("secuencial", "colas_multiples_servidor_unico"): "08_secuencial_servidor_unico.json",
}


def test_tabla_de_despacho_cubre_las_8_combinaciones():
    """Cada (metodo, variante) tiene una función constructora en la tabla."""
    esperadas = {(m, v) for m in METODOS for v in VARIANTES}
    assert set(topologias._CONSTRUCTORES) == esperadas
    assert set(EJEMPLO_POR_VARIANTE) == esperadas


@pytest.mark.parametrize(
    "metodo, variante", sorted(EJEMPLO_POR_VARIANTE),
    ids=[f"{m}-{v}" for m, v in sorted(EJEMPLO_POR_VARIANTE)],
)
def test_variante_por_defecto_coincide_con_su_ejemplo(metodo, variante):
    """Con los valores por defecto, cada variante genera una config válida e
    idéntica a su ejemplo de examples/configs_ejemplo/.

    Mientras una variante lance NotImplementedError, el test se marca como
    "skipped" (pendiente). En cuanto se implementa, empieza a verificarse solo:
    no hace falta editar este test.
    """
    try:
        config = construir_config(metodo, variante)
    except NotImplementedError:
        pytest.skip("variante pendiente de implementar")
    assert validar_config(config) == []
    ejemplo = json.loads(
        (_CARPETA_EJEMPLOS / EJEMPLO_POR_VARIANTE[(metodo, variante)]).read_text(encoding="utf-8")
    )
    assert config == ejemplo


# --------------------------------------------------------------------------
# Funciones auxiliares compartidas
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [0, -1, "4", None, True, float("nan"), float("inf")])
def test_validar_numero_positivo_rechaza(valor):
    with pytest.raises(ValueError, match="media_servicio"):
        topologias._validar_numero_positivo("media_servicio", valor)


@pytest.mark.parametrize("valor", [0.5, 1, 480])
def test_validar_numero_positivo_acepta(valor):
    topologias._validar_numero_positivo("media_servicio", valor)


@pytest.mark.parametrize("valor", [0, -1, 2.5, "3", True])
def test_validar_entero_minimo_rechaza(valor):
    with pytest.raises(ValueError, match="n_colas"):
        topologias._validar_entero_minimo("n_colas", valor)


def test_validar_entero_minimo_con_minimo_2():
    topologias._validar_entero_minimo("n_colas", 2, minimo=2)
    with pytest.raises(ValueError, match="mayor o igual a 2"):
        topologias._validar_entero_minimo("n_colas", 1, minimo=2)


@pytest.mark.parametrize("valor", [0, 1, -0.1, 1.5, "0.2", None, float("nan")])
def test_validar_proporcion_rechaza(valor):
    with pytest.raises(ValueError, match="proporcion"):
        topologias._validar_proporcion("proporcion_preferenciales", valor)


def test_validar_proporcion_acepta():
    topologias._validar_proporcion("proporcion_preferenciales", 0.2)


def test_verificar_estabilidad_nombra_la_estacion():
    """En el método secuencial, el mensaje dice qué estación es inestable."""
    with pytest.raises(ValueError, match="inestable en la estación 'triaje'"):
        topologias._verificar_estabilidad(60, 2, 1, estacion="triaje")


def test_verificar_estabilidad_acepta_rho_menor_que_1():
    topologias._verificar_estabilidad(40, 4, 3)  # ρ = 0.889


def test_servidores_exponenciales_con_prefijo():
    assert topologias._servidores_exponenciales(2, 5, prefijo="e") == [
        {"id": "e1", "servicio": {"tipo": "exponencial", "media": 5}},
        {"id": "e2", "servicio": {"tipo": "exponencial", "media": 5}},
    ]
