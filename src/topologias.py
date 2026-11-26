"""
topologias.py - Las 8 variantes de sistema de colas.

Responsables: Equipo 2 (Topologías). Revisa: Equipo 1 (Engine).

Arma configuraciones válidas (contrato de entrada) para cada combinación de
método y variante. No simula nada: eso lo hace engine.py.

Método 1 (paralelo)  x  4 variantes
Método 2 (secuencial, con triaje inicial)  x  4 variantes

Cómo está organizado (tabla de despacho)
----------------------------------------
Cada combinación (metodo, variante) tiene su propia función constructora, y
la tabla _CONSTRUCTORES (al final del archivo) dice cuál usar. Así cada
persona trabaja solo dentro de su función y los PRs no se pisan.

Para implementar una variante:
1. Reemplaza el `raise NotImplementedError` de tu función por la
   construcción de la config. Usa las funciones auxiliares de la sección
   "Funciones auxiliares compartidas" para validar parámetros y estabilidad.
2. Con los valores por defecto, tu función debe devolver exactamente el
   ejemplo indicado en su docstring (examples/configs_ejemplo/...).
3. No hace falta tocar la tabla ni los tests existentes: el test
   test_variante_por_defecto_coincide_con_su_ejemplo empieza a verificar tu
   variante en cuanto deja de lanzar NotImplementedError. Agrega tus propios
   tests de parámetros inválidos y de estabilidad en tests/test_topologias.py.
"""

import math

VARIANTES = (
    "cola_unica_multiples_servidores",
    "colas_multiples_multiples_servidores",
    "colas_multiples_preferencial_multiples_servidores",
    "colas_multiples_servidor_unico",
)


METODOS = ("paralelo", "secuencial")


def _es_numero(valor) -> bool:
    """Verifica si el valor es un número finito (int o float), excluyendo bool."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return False
    return math.isfinite(valor)


def _es_entero(valor) -> bool:
    """Verifica si el valor es int, excluyendo bool."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def construir_config(metodo: str, variante: str, **parametros) -> dict:
    """
    Construye una configuración completa para una variante dada.

    Args:
        metodo: "paralelo" o "secuencial".
        variante: uno de los valores de VARIANTES.
        **parametros: lambda, número de servidores y colas, distribuciones,
            proporción de clientes preferenciales, etc. Cada variante
            documenta los suyos en su función constructora.

    Returns:
        Configuración que cumple el contrato de entrada (config.validar_config).

    Raises:
        ValueError: si *metodo* o *variante* no existen, o si los parámetros son inválidos.
        NotImplementedError: si la combinación aún no se ha implementado.
    """
    if metodo not in METODOS:
        raise ValueError(
            f"Método desconocido: {metodo!r}. "
            f"Los métodos válidos son: {METODOS}"
        )
    if variante not in VARIANTES:
        raise ValueError(
            f"Variante desconocida: {variante!r}. "
            f"Las variantes válidas son: {VARIANTES}"
        )

    constructor = _CONSTRUCTORES[(metodo, variante)]
    return constructor(**parametros)


# ==========================================================================
# Funciones auxiliares compartidas
# Úsalas en tu variante para que todos los mensajes de error sean iguales.
# ==========================================================================

def _validar_numero_positivo(nombre: str, valor) -> None:
    """Lanza ValueError si *valor* no es un número finito mayor que 0."""
    if not _es_numero(valor) or valor <= 0:
        raise ValueError(
            f"{nombre} debe ser un número mayor que 0, recibido: {valor!r}"
        )


def _validar_entero_minimo(nombre: str, valor, minimo: int = 1) -> None:
    """Lanza ValueError si *valor* no es un entero mayor o igual a *minimo*."""
    if not _es_entero(valor) or valor < minimo:
        raise ValueError(
            f"{nombre} debe ser un entero mayor o igual a {minimo}, recibido: {valor!r}"
        )


def _validar_semilla(semilla) -> None:
    """Lanza ValueError si *semilla* no es un entero."""
    if not _es_entero(semilla):
        raise ValueError(
            f"semilla debe ser un número entero, recibido: {semilla!r}"
        )


def _validar_proporcion(nombre: str, valor) -> None:
    """Lanza ValueError si *valor* no está estrictamente entre 0 y 1 (p. ej. proporción de preferenciales)."""
    if not _es_numero(valor) or not 0 < valor < 1:
        raise ValueError(
            f"{nombre} debe ser un número entre 0 y 1 (sin incluirlos), recibido: {valor!r}"
        )


def _verificar_estabilidad(lambda_por_hora, media_servicio, n_servidores,
                           estacion: str | None = None) -> None:
    """
    Lanza ValueError si la estación es inestable: ρ = (λ/60 · media) / c ≥ 1.

    Si ρ ≥ 1 la cola crece sin control y la simulación no tiene sentido.
    En el método secuencial llámala una vez por estación (con la λ que llega
    a esa estación y la media de servicio de sus servidores).

    Args:
        lambda_por_hora: llegadas por hora a la estación.
        media_servicio: tiempo medio de servicio en minutos (para una
            uniforme [a, b], usa (a + b) / 2).
        n_servidores: número de servidores de la estación.
        estacion: nombre de la estación, solo para el mensaje de error.
    """
    rho = (lambda_por_hora / 60 * media_servicio) / n_servidores
    if rho >= 1:
        donde = f" en la estación {estacion!r}" if estacion else ""
        raise ValueError(
            f"El sistema es inestable{donde} (ρ = {rho:.4f} ≥ 1). "
            f"Con λ={lambda_por_hora}/h, media_servicio={media_servicio} min "
            f"y n_servidores={n_servidores}, la cola crece sin control. "
            "Reduce λ, reduce media_servicio o aumenta n_servidores."
        )


def _servidores_exponenciales(n_servidores: int, media_servicio,
                              prefijo: str = "s") -> list[dict]:
    """Lista de *n_servidores* servidores exponenciales con ids prefijo1, prefijo2, ..."""
    return [
        {
            "id": f"{prefijo}{i + 1}",
            "servicio": {"tipo": "exponencial", "media": media_servicio},
        }
        for i in range(n_servidores)
    ]


# ==========================================================================
# Método 1 (paralelo)
# ==========================================================================

def _paralelo_cola_unica(
    *,
    lambda_por_hora: int | float = 40,
    n_servidores: int = 3,
    media_servicio: int | float = 4,
    duracion_minutos: int | float = 480,
    semilla: int = 42,
) -> dict:
    """
    Variante 1: método paralelo, cola única con múltiples servidores.

    Con los valores por defecto reproduce
    examples/configs_ejemplo/01_paralelo_cola_unica.json.

    Antes de construir la configuración, valida los parámetros y verifica
    la condición de estabilidad del sistema M/M/c:
        ρ = (λ/60 · media_servicio) / n_servidores < 1.
    """
    # --- Validación de parámetros --------------------------------------------
    _validar_entero_minimo("n_servidores", n_servidores)
    _validar_numero_positivo("lambda_por_hora", lambda_por_hora)
    _validar_numero_positivo("media_servicio", media_servicio)
    _validar_numero_positivo("duracion_minutos", duracion_minutos)
    _validar_semilla(semilla)

    # --- Validación de estabilidad -------------------------------------------
    _verificar_estabilidad(lambda_por_hora, media_servicio, n_servidores)

    # --- Configuración completa ----------------------------------------------
    return {
        "simulacion": {
            "nombre": "Ejemplo - Método 1, cola única, múltiples servidores",
            "metodo": "paralelo",
            "duracion_minutos": duracion_minutos,
            "semilla": semilla,
            "llegada": {
                "distribucion": "poisson",
                "lambda_por_hora": lambda_por_hora,
            },
        },
        "estaciones": [
            {
                "id": "cajeros",
                "nombre": "Atención de cajeros",
                "servidores": _servidores_exponenciales(n_servidores, media_servicio),
                "colas": {
                    "tipo": "unica",
                    "cantidad": 1,
                    "reparticion": None,
                },
                "salidas": [],
            }
        ],
    }


# --------------------------------------------------------------------------
# Paralelo: colas múltiples con múltiples servidores · Responsable: (asignar)
# --------------------------------------------------------------------------

def _paralelo_colas_multiples(**parametros) -> dict:
    """
    Variante 2: método paralelo, colas múltiples con múltiples servidores.

    Con los valores por defecto debe reproducir
    examples/configs_ejemplo/02_paralelo_colas_multiples.json
    (3 servidores exponenciales de media 4, 3 colas con reparto "round_robin").

    Parámetros sugeridos: lambda_por_hora, n_servidores, n_colas,
    media_servicio, reparticion ("round_robin", "mas_corta" o "aleatoria"),
    duracion_minutos, semilla.
    Valida estabilidad con _verificar_estabilidad.
    """
    raise NotImplementedError(
        "La combinación metodo='paralelo', "
        "variante='colas_multiples_multiples_servidores' aún no está implementada."
    )


# --------------------------------------------------------------------------
# Paralelo: colas múltiples con servidor único · Responsable: (asignar)
# --------------------------------------------------------------------------

def _paralelo_servidor_unico(**parametros) -> dict:
    """
    Variante 4: método paralelo, varias colas atendidas por un solo servidor.

    Con los valores por defecto debe reproducir
    examples/configs_ejemplo/04_paralelo_servidor_unico.json
    (1 servidor exponencial de media 1, 2 colas con reparto "mas_corta").

    Parámetros sugeridos: lambda_por_hora, n_colas, media_servicio,
    reparticion, duracion_minutos, semilla.
    Valida estabilidad con _verificar_estabilidad(..., n_servidores=1).
    """
    raise NotImplementedError(
        "La combinación metodo='paralelo', "
        "variante='colas_multiples_servidor_unico' aún no está implementada."
    )


# --------------------------------------------------------------------------
# Paralelo: clientes preferenciales · Responsable: Cristy
# --------------------------------------------------------------------------

def _paralelo_preferencial(
    *,
    lambda_por_hora: int | float = 40,
    n_servidores: int = 3,
    media_servicio: int | float = 4,
    proporcion_preferenciales: int | float = 0.2,
    duracion_minutos: int | float = 480,
    semilla: int = 42,
) -> dict:
    """
    Variante 3: método paralelo, colas con clientes preferenciales.

    Una sola estación con *n_servidores* servidores exponenciales y dos
    colas de tipo "preferencial": la cola 1 es para clientes preferenciales
    y la cola 2 para clientes normales. Cuando un servidor queda libre
    atiende primero la cola 1 (prioridad no expropiativa: no interrumpe a
    quien ya está en servicio). Ver docs/contratos.md.

    Con los valores por defecto reproduce
    examples/configs_ejemplo/03_paralelo_preferencial.json.

    Antes de construir la configuración valida los parámetros y verifica la
    estabilidad del sistema M/M/c. La prioridad solo cambia el orden de
    atención, no la carga total, así que la condición sigue siendo:
        ρ = (λ/60 · media_servicio) / n_servidores < 1.

    Args:
        lambda_por_hora: llegadas por hora (proceso de Poisson), mayor que 0.
        n_servidores: número de servidores de la estación, entero ≥ 1.
        media_servicio: tiempo medio de servicio en minutos (exponencial),
            mayor que 0.
        proporcion_preferenciales: fracción de clientes que llegan como
            preferenciales, estrictamente entre 0 y 1.
        duracion_minutos: duración de la simulación en minutos, mayor que 0.
        semilla: semilla del generador aleatorio, entero.

    Returns:
        Configuración que cumple el contrato de entrada (config.validar_config),
        con "clientes_preferenciales": {"proporcion": ...} dentro de
        "simulacion" y colas {"tipo": "preferencial", "cantidad": 2,
        "reparticion": None}.

    Raises:
        ValueError: si algún parámetro no es válido (tipo o rango), si
            proporcion_preferenciales no está entre 0 y 1 (sin incluirlos),
            o si el sistema es inestable (ρ ≥ 1).
    """
    # --- Validación de parámetros --------------------------------------------
    _validar_entero_minimo("n_servidores", n_servidores)
    _validar_numero_positivo("lambda_por_hora", lambda_por_hora)
    _validar_numero_positivo("media_servicio", media_servicio)
    _validar_proporcion("proporcion_preferenciales", proporcion_preferenciales)
    _validar_numero_positivo("duracion_minutos", duracion_minutos)
    _validar_semilla(semilla)

    # --- Validación de estabilidad -------------------------------------------
    _verificar_estabilidad(lambda_por_hora, media_servicio, n_servidores)

    # --- Configuración completa ----------------------------------------------
    return {
        "simulacion": {
            "nombre": "Ejemplo - Método 1, colas múltiples, clientes preferenciales",
            "metodo": "paralelo",
            "duracion_minutos": duracion_minutos,
            "semilla": semilla,
            "llegada": {
                "distribucion": "poisson",
                "lambda_por_hora": lambda_por_hora,
            },
            "clientes_preferenciales": {
                "proporcion": proporcion_preferenciales,
            },
        },
        "estaciones": [
            {
                "id": "cajeros",
                "nombre": "Atención de cajeros",
                "servidores": _servidores_exponenciales(n_servidores, media_servicio),
                # Cola 1: preferenciales · Cola 2: normales.
                "colas": {
                    "tipo": "preferencial",
                    "cantidad": 2,
                    "reparticion": None,
                },
                "salidas": [],
            }
        ],
    }


# ==========================================================================
# Método 2 (secuencial, con triaje inicial)
# Todas las variantes tienen 2 estaciones en serie: la primera es la de
# entrada ("estacion_entrada") y envía a la segunda con probabilidad 1.0.
# Verifica la estabilidad de CADA estación.
# ==========================================================================

# --------------------------------------------------------------------------
# Secuencial: cola única · Responsable: (asignar)
# --------------------------------------------------------------------------

def _secuencial_cola_unica(**parametros) -> dict:
    """
    Variante 1: método secuencial, cola única en cada estación.

    Con los valores por defecto debe reproducir
    examples/configs_ejemplo/05_secuencial_cola_unica.json
    (triaje: 2 servidores exponenciales de media 2 → atención: 2 servidores
    exponenciales de media 4; λ = 20/h).
    """
    raise NotImplementedError(
        "La combinación metodo='secuencial', "
        "variante='cola_unica_multiples_servidores' aún no está implementada."
    )


# --------------------------------------------------------------------------
# Secuencial: colas múltiples · Responsable: (asignar)
# --------------------------------------------------------------------------

def _secuencial_colas_multiples(**parametros) -> dict:
    """
    Variante 2: método secuencial, colas múltiples en la segunda estación.

    Con los valores por defecto debe reproducir
    examples/configs_ejemplo/06_secuencial_colas_multiples.json
    (recepción: 1 servidor uniforme [1, 3] → cajas: 2 servidores
    exponenciales de medias 5 y 6, 2 colas "mas_corta"; λ = 15/h, semilla 123).
    Ojo: en este ejemplo las estaciones no tienen "nombre".
    """
    raise NotImplementedError(
        "La combinación metodo='secuencial', "
        "variante='colas_multiples_multiples_servidores' aún no está implementada."
    )


# --------------------------------------------------------------------------
# Secuencial: clientes preferenciales · Responsable: (asignar)
# --------------------------------------------------------------------------

def _secuencial_preferencial(**parametros) -> dict:
    """
    Variante 3: método secuencial, clientes preferenciales en la segunda estación.

    Con los valores por defecto debe reproducir
    examples/configs_ejemplo/07_secuencial_preferencial.json
    (triaje: 1 servidor exponencial de media 2 → especialistas: 2 servidores
    exponenciales de media 5, colas "preferencial" con cantidad 2;
    λ = 18/h, proporción 0.3, semilla 77).
    """
    raise NotImplementedError(
        "La combinación metodo='secuencial', "
        "variante='colas_multiples_preferencial_multiples_servidores' "
        "aún no está implementada."
    )


# --------------------------------------------------------------------------
# Secuencial: colas múltiples con servidor único · Responsable: (asignar)
# --------------------------------------------------------------------------

def _secuencial_servidor_unico(**parametros) -> dict:
    """
    Variante 4: método secuencial, varias colas y un solo servidor en la segunda estación.

    Con los valores por defecto debe reproducir
    examples/configs_ejemplo/08_secuencial_servidor_unico.json
    (filtro: 1 servidor exponencial de media 1 → taquilla: 1 servidor
    uniforme [2, 4] con id "s_unico", 3 colas "aleatoria"; λ = 15/h, semilla 88).
    """
    raise NotImplementedError(
        "La combinación metodo='secuencial', "
        "variante='colas_multiples_servidor_unico' aún no está implementada."
    )


# ==========================================================================
# Tabla de despacho: (metodo, variante) -> función constructora.
# Cubre las 8 combinaciones; no hace falta editarla para implementar una.
# ==========================================================================

_CONSTRUCTORES = {
    ("paralelo", "cola_unica_multiples_servidores"): _paralelo_cola_unica,
    ("paralelo", "colas_multiples_multiples_servidores"): _paralelo_colas_multiples,
    ("paralelo", "colas_multiples_preferencial_multiples_servidores"): _paralelo_preferencial,
    ("paralelo", "colas_multiples_servidor_unico"): _paralelo_servidor_unico,
    ("secuencial", "cola_unica_multiples_servidores"): _secuencial_cola_unica,
    ("secuencial", "colas_multiples_multiples_servidores"): _secuencial_colas_multiples,
    ("secuencial", "colas_multiples_preferencial_multiples_servidores"): _secuencial_preferencial,
    ("secuencial", "colas_multiples_servidor_unico"): _secuencial_servidor_unico,
}
