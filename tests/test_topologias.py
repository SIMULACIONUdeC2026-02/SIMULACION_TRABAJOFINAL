"""Pruebas de las topologías. Responsables: Equipo 2 (Topologías)."""
import json
import pathlib

import pytest

from config import validar_config
from topologias import construir_config

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


def test_combinacion_no_implementada_lanza_not_implemented():
    """Una combinación válida pero no implementada lanza NotImplementedError."""
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
