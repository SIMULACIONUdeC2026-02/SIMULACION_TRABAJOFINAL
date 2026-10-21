"""
topologias.py - Las 8 variantes de sistema de colas.

Responsables: Equipo 2 (Topologías). Revisa: Equipo 1 (Engine).

Arma configuraciones válidas (contrato de entrada) para cada combinación de
método y variante. No simula nada: eso lo hace engine.py.

Método 1 (paralelo)  x  4 variantes
Método 2 (secuencial, con triaje inicial)  x  4 variantes
"""

VARIANTES = (
    "cola_unica_multiples_servidores",
    "colas_multiples_multiples_servidores",
    "colas_multiples_preferencial_multiples_servidores",
    "colas_multiples_servidor_unico",
)


METODOS = ("paralelo", "secuencial")


def construir_config(metodo: str, variante: str, **parametros) -> dict:
    """
    Construye una configuración completa para una variante dada.

    Args:
        metodo: "paralelo" o "secuencial".
        variante: uno de los valores de VARIANTES.
        **parametros: lambda, número de servidores y colas, distribuciones,
            proporción de clientes preferenciales, etc.

    Returns:
        Configuración que cumple el contrato de entrada (config.validar_config).

    Raises:
        ValueError: si *metodo* o *variante* no existen.
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

    if metodo == "paralelo" and variante == "cola_unica_multiples_servidores":
        return _paralelo_cola_unica(**parametros)

    raise NotImplementedError(
        f"La combinación metodo={metodo!r}, variante={variante!r} "
        "aún no está implementada."
    )


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

    Antes de construir la configuración, verifica la condición de estabilidad
    del sistema M/M/c:  ρ = (λ/60 · media_servicio) / n_servidores < 1.
    Si ρ ≥ 1 la cola crece sin control y la simulación no tiene sentido.
    """
    # --- Validación de estabilidad -------------------------------------------
    tasa_llegada_por_minuto = lambda_por_hora / 60
    rho = (tasa_llegada_por_minuto * media_servicio) / n_servidores
    if rho >= 1:
        raise ValueError(
            f"El sistema es inestable (ρ = {rho:.4f} ≥ 1). "
            f"Con λ={lambda_por_hora}/h, media_servicio={media_servicio} min "
            f"y n_servidores={n_servidores}, la cola crece sin control. "
            "Reduce λ, reduce media_servicio o aumenta n_servidores."
        )

    # --- Construcción de servidores ------------------------------------------
    servidores = [
        {
            "id": f"s{i + 1}",
            "servicio": {"tipo": "exponencial", "media": media_servicio},
        }
        for i in range(n_servidores)
    ]

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
                "servidores": servidores,
                "colas": {
                    "tipo": "unica",
                    "cantidad": 1,
                    "reparticion": None,
                },
                "salidas": [],
            }
        ],
    }
