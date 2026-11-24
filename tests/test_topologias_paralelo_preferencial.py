"""Pruebas de la variante 03: método paralelo con clientes preferenciales.

Responsables: Equipo 2 (Topologías).
La comparación con examples/configs_ejemplo/03_paralelo_preferencial.json
ya la cubre test_variante_por_defecto_coincide_con_su_ejemplo en
tests/test_topologias.py; aquí se prueban parámetros, errores y que la
configuración corra en el motor.
"""
import pytest

from config import validar_config
from topologias import construir_config
from src.engine import simular

METODO = "paralelo"
VARIANTE = "colas_multiples_preferencial_multiples_servidores"


def _construir(**parametros) -> dict:
    """Atajo para construir la config de esta variante."""
    return construir_config(METODO, VARIANTE, **parametros)


# --------------------------------------------------------------------------
# Parámetros válidos
# --------------------------------------------------------------------------

def test_parametros_cambiados_generan_config_valida():
    """Con 4 servidores y proporción 0.35 la config es válida y refleja esos valores."""
    config = _construir(n_servidores=4, proporcion_preferenciales=0.35)
    errores = validar_config(config)
    assert errores == [], f"Errores de validación: {errores}"

    estacion = config["estaciones"][0]
    assert [s["id"] for s in estacion["servidores"]] == ["s1", "s2", "s3", "s4"]
    assert config["simulacion"]["clientes_preferenciales"] == {"proporcion": 0.35}
    assert estacion["colas"] == {"tipo": "preferencial", "cantidad": 2, "reparticion": None}


def test_colas_siempre_preferenciales_con_dos_colas():
    """Sin importar los servidores, siempre hay 2 colas preferenciales (1: pref., 2: normales)."""
    for n in (1, 2, 5):
        config = _construir(n_servidores=n, lambda_por_hora=10)
        assert config["estaciones"][0]["colas"] == {
            "tipo": "preferencial", "cantidad": 2, "reparticion": None,
        }


# --------------------------------------------------------------------------
# Parámetros inválidos
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [0, 1, -0.1, 1.5, "0.2", None, float("nan")])
def test_proporcion_invalida_lanza_value_error(valor):
    """La proporción debe ser un número estrictamente entre 0 y 1."""
    with pytest.raises(ValueError, match="proporcion_preferenciales"):
        _construir(proporcion_preferenciales=valor)


@pytest.mark.parametrize("valor", [0, -1, 2.5, True])
def test_n_servidores_invalido_lanza_value_error(valor):
    """n_servidores debe ser un entero ≥ 1 (bool no cuenta como entero)."""
    with pytest.raises(ValueError, match="n_servidores"):
        _construir(n_servidores=valor)


@pytest.mark.parametrize("nombre", ["lambda_por_hora", "media_servicio"])
@pytest.mark.parametrize("valor", [0, -5, float("nan"), float("inf")])
def test_lambda_y_media_invalidas_lanzan_value_error(nombre, valor):
    """lambda_por_hora y media_servicio deben ser números finitos mayores que 0."""
    with pytest.raises(ValueError, match=nombre):
        _construir(**{nombre: valor})


def test_parametro_desconocido_lanza_type_error():
    """Los parámetros son solo por nombre; uno que no existe se rechaza."""
    with pytest.raises(TypeError):
        _construir(n_colas=3)


# --------------------------------------------------------------------------
# Estabilidad
# --------------------------------------------------------------------------

def test_sistema_inestable_lanza_value_error():
    """λ=60/h, media=4 min, c=3 → ρ = 1.33 ≥ 1: el sistema es inestable."""
    with pytest.raises(ValueError, match="inestable"):
        _construir(lambda_por_hora=60, media_servicio=4, n_servidores=3)


def test_rho_exactamente_uno_es_inestable():
    """λ=45/h, media=4 min, c=3 → ρ = 1 exacto, también inestable."""
    with pytest.raises(ValueError, match="inestable"):
        _construir(lambda_por_hora=45, media_servicio=4, n_servidores=3)


# --------------------------------------------------------------------------
# Integración con el motor
# --------------------------------------------------------------------------

def test_config_corre_en_el_motor_con_clientes_preferenciales():
    """La config por defecto corre en simular() y genera clientes preferenciales."""
    salida = simular(_construir())
    assert "resultado" in salida

    clientes = salida["resultado"]["eventos_clientes"]
    assert clientes, "La simulación no generó clientes"
    assert any(c["es_preferencial"] is True for c in clientes)
