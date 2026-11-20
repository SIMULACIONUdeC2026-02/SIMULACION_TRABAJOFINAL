"""Contrato de salida del motor: validador compartido por los cuatro equipos.

Responsables: Equipo 2 (Topologías), como dueño del contrato. Lo usan todos.

Qué es
    ``validar_resultado`` hace por la salida del motor lo que ``validar_config``
    hace por la configuración de entrada: recibe el resultado y la configuración
    con la que se generó, y devuelve la lista de problemas encontrados.
    Lista vacía = el resultado respeta el contrato (docs/contratos.md).

Para qué sirve
    Para que los equipos no dependan de ponerse de acuerdo a mano. La misma
    función se aplica a los resultados de ejemplo y a lo que produce el motor:
    si algo se desvía del contrato, falla una prueba en el PR y no días después
    en la pantalla.

Cómo la usa cada equipo
    - Engine (Equipo 1): en sus pruebas, ``assert validar_resultado(salida, config) == []``
      para cada variante que implementen.
    - Métricas (Equipo 3): para comprobar que los eventos tienen la forma y las
      garantías que sus cálculos suponen (por ejemplo, que un servidor nunca
      atiende a dos clientes a la vez, de lo que depende el tiempo ocioso).
    - UI (Equipo 4): para mostrar un mensaje claro si el resultado no es válido,
      en lugar de fallar a mitad de la pantalla.
    - Topologías (Equipo 2): para mantener coherentes el contrato y los ejemplos.

Política de cierre que verifica (docs/contratos.md, sección Engine)
    Las llegadas se cortan en ``duracion_minutos``, se atiende a todos los que
    ya entraron, y ``duracion_total_minutos`` es el máximo entre el cierre y la
    última salida.

Si hace falta cambiar una regla de este archivo, se propone con un issue: el
contrato se modifica en un solo lugar para que todos sigan viendo lo mismo.
"""
import math

from src.config import validar_config

CLAVES_RESULTADO = {"simulacion_id", "duracion_total_minutos", "eventos_clientes"}
CLAVES_CLIENTE = {"cliente_id", "es_preferencial", "tiempo_entrada_sistema",
                  "tiempo_salida_sistema", "paradas"}
CLAVES_PARADA = {"estacion_id", "tiempo_inicio_espera", "tiempo_inicio_servicio",
                 "tiempo_fin_servicio", "servidor_asignado", "cola_asignada"}
CLAVES_SISTEMA = {"tiempo_promedio_en_sistema", "clientes_promedio_en_sistema",
                  "clientes_totales_atendidos"}
CLAVES_ESTACION = {"tiempo_promedio_espera_cola", "tiempo_promedio_atencion",
                   "longitud_promedio_cola", "longitud_maxima_cola",
                   "por_servidor", "por_cola", "cola_mas_larga"}

TOLERANCIA = 1e-6
MAX_ERRORES = 50


def _numero(valor) -> bool:
    """True si es int o float finito (bool no cuenta)."""
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and math.isfinite(valor))


def _entero(valor) -> bool:
    """True si es int (bool no cuenta)."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def validar_resultado(resultado: dict, config: dict,
                      exigir_metricas: bool = False) -> list[str]:
    """Comprueba que ``resultado`` respeta el contrato de salida.

    Args:
        resultado: lo que devuelve ``ejecutar_simulacion`` (o el contenido de
            "resultado" en los archivos de examples/resultados_ejemplo).
        config: la configuración con la que se generó.
        exigir_metricas: si es True, el bloque "metricas" es obligatorio.
            El motor solo entrega eventos; las métricas las agrega Métricas.

    Returns:
        Lista de mensajes de error (vacía si todo está bien). Nunca lanza
        excepciones por datos mal formados.
    """
    if not isinstance(config, dict):
        return ["config: debe ser un diccionario"]
    errores_config = validar_config(config)
    if errores_config:
        return [f"config inválida: {e}" for e in errores_config[:5]]
    if not isinstance(resultado, dict):
        return ["resultado: debe ser un diccionario"]

    errores: list[str] = []

    def error(mensaje: str) -> None:
        if len(errores) < MAX_ERRORES:
            errores.append(mensaje)

    _validar_forma_general(resultado, exigir_metricas, error)
    eventos = resultado.get("eventos_clientes")
    if not isinstance(eventos, list):
        return errores

    estaciones = {e["id"]: e for e in config["estaciones"]}
    simulacion = config["simulacion"]
    cierre = simulacion["duracion_minutos"]
    duracion_total = resultado.get("duracion_total_minutos")
    estacion_entrada = simulacion.get("estacion_entrada", config["estaciones"][0]["id"])
    hay_preferenciales = "clientes_preferenciales" in simulacion

    ids_vistos = set()
    ocupacion: dict[tuple, list] = {}
    ultima_salida = None

    for posicion, cliente in enumerate(eventos):
        etiqueta = f"eventos_clientes[{posicion}]"
        if not isinstance(cliente, dict):
            error(f"{etiqueta}: debe ser un diccionario")
            continue
        if set(cliente) != CLAVES_CLIENTE:
            error(f"{etiqueta}: claves esperadas {sorted(CLAVES_CLIENTE)}, "
                  f"recibidas {sorted(cliente)}")
            continue
        if not _entero(cliente["cliente_id"]):
            error(f"{etiqueta}.cliente_id: debe ser entero")
        elif cliente["cliente_id"] in ids_vistos:
            error(f"{etiqueta}.cliente_id: repetido ({cliente['cliente_id']})")
        else:
            ids_vistos.add(cliente["cliente_id"])
        if not isinstance(cliente["es_preferencial"], bool):
            error(f"{etiqueta}.es_preferencial: debe ser booleano")
        elif cliente["es_preferencial"] and not hay_preferenciales:
            error(f"{etiqueta}: cliente preferencial pero la config no define "
                  f"clientes_preferenciales")

        entrada = cliente["tiempo_entrada_sistema"]
        salida = cliente["tiempo_salida_sistema"]
        if not (_numero(entrada) and _numero(salida)):
            error(f"{etiqueta}: tiempo_entrada_sistema y tiempo_salida_sistema "
                  f"deben ser números finitos (sin null)")
            continue
        if not 0 <= entrada < cierre:
            error(f"{etiqueta}: entró en {entrada}, fuera de [0, {cierre}) "
                  f"(no hay llegadas en el cierre ni después)")
        if salida < entrada:
            error(f"{etiqueta}: sale ({salida}) antes de entrar ({entrada})")
        if _numero(duracion_total) and salida > duracion_total + TOLERANCIA:
            error(f"{etiqueta}: sale en {salida}, después de duracion_total_minutos "
                  f"({duracion_total})")
        ultima_salida = salida if ultima_salida is None else max(ultima_salida, salida)

        paradas = cliente["paradas"]
        if not isinstance(paradas, list) or not paradas:
            error(f"{etiqueta}.paradas: debe ser una lista con al menos una parada")
            continue
        if _paradas_bien_formadas(paradas, etiqueta, error):
            _validar_recorrido(cliente, paradas, estaciones, estacion_entrada,
                               etiqueta, ocupacion, error)

    _validar_ocupacion_exclusiva(ocupacion, error)
    _validar_duracion_total(duracion_total, cierre, ultima_salida, error)
    _validar_metricas(resultado, estaciones, exigir_metricas, error)
    return errores


def _validar_forma_general(resultado: dict, exigir_metricas: bool, error) -> None:
    """Claves de primer nivel, simulacion_id y tipo de duracion_total_minutos."""
    permitidas = CLAVES_RESULTADO | {"metricas"}
    for clave in sorted(CLAVES_RESULTADO - set(resultado)):
        error(f"resultado: falta la clave '{clave}'")
    for clave in sorted(set(resultado) - permitidas):
        error(f"resultado: clave desconocida '{clave}'")
    if exigir_metricas and "metricas" not in resultado:
        error("resultado: falta el bloque 'metricas'")
    simulacion_id = resultado.get("simulacion_id")
    if "simulacion_id" in resultado and not (isinstance(simulacion_id, str) and simulacion_id):
        error("simulacion_id: debe ser un texto no vacío")
    duracion = resultado.get("duracion_total_minutos")
    if "duracion_total_minutos" in resultado and not (_numero(duracion) and duracion > 0):
        error("duracion_total_minutos: debe ser un número finito mayor que 0")
    if "eventos_clientes" in resultado and not isinstance(resultado["eventos_clientes"], list):
        error("eventos_clientes: debe ser una lista")


def _paradas_bien_formadas(paradas: list, etiqueta: str, error) -> bool:
    """True si todas las paradas son diccionarios con las claves y tipos del contrato."""
    bien = True
    for j, parada in enumerate(paradas):
        ruta = f"{etiqueta}.paradas[{j}]"
        if not isinstance(parada, dict) or set(parada) != CLAVES_PARADA:
            error(f"{ruta}: claves esperadas {sorted(CLAVES_PARADA)}")
            bien = False
            continue
        for clave in ("tiempo_inicio_espera", "tiempo_inicio_servicio",
                      "tiempo_fin_servicio"):
            if not _numero(parada[clave]):
                error(f"{ruta}.{clave}: debe ser un número finito (sin null)")
                bien = False
        for clave in ("servidor_asignado", "cola_asignada"):
            if not _entero(parada[clave]):
                error(f"{ruta}.{clave}: debe ser un entero (posición desde 1)")
                bien = False
    return bien


def _validar_recorrido(cliente, paradas, estaciones, estacion_entrada,
                       etiqueta, ocupacion, error) -> None:
    """Orden de los tiempos, coherencia con la config y ruta entre estaciones."""
    if cliente["tiempo_entrada_sistema"] != paradas[0]["tiempo_inicio_espera"]:
        error(f"{etiqueta}: tiempo_entrada_sistema debe ser el inicio de espera "
              f"de la primera parada")
    if cliente["tiempo_salida_sistema"] != paradas[-1]["tiempo_fin_servicio"]:
        error(f"{etiqueta}: tiempo_salida_sistema debe ser el fin de servicio "
              f"de la última parada")
    if paradas[0]["estacion_id"] != estacion_entrada:
        error(f"{etiqueta}: la primera parada debe estar en la estación de "
              f"entrada '{estacion_entrada}'")

    for j, parada in enumerate(paradas):
        ruta = f"{etiqueta}.paradas[{j}]"
        if not (parada["tiempo_inicio_espera"] <= parada["tiempo_inicio_servicio"]
                <= parada["tiempo_fin_servicio"]):
            error(f"{ruta}: se exige inicio_espera <= inicio_servicio <= fin_servicio")
        if j > 0 and paradas[j - 1]["tiempo_fin_servicio"] > parada["tiempo_inicio_espera"]:
            error(f"{ruta}: empieza a esperar antes de terminar la parada anterior")

        estacion = estaciones.get(parada["estacion_id"])
        if estacion is None:
            error(f"{ruta}.estacion_id: '{parada['estacion_id']}' no existe en la config")
            continue
        if not 1 <= parada["servidor_asignado"] <= len(estacion["servidores"]):
            error(f"{ruta}.servidor_asignado: {parada['servidor_asignado']} fuera de "
                  f"1..{len(estacion['servidores'])}")
        else:
            ocupacion.setdefault((parada["estacion_id"], parada["servidor_asignado"]),
                                 []).append((parada["tiempo_inicio_servicio"],
                                             parada["tiempo_fin_servicio"],
                                             cliente["cliente_id"]))
        if not 1 <= parada["cola_asignada"] <= estacion["colas"]["cantidad"]:
            error(f"{ruta}.cola_asignada: {parada['cola_asignada']} fuera de "
                  f"1..{estacion['colas']['cantidad']}")
        elif estacion["colas"]["tipo"] == "preferencial" and isinstance(
                cliente["es_preferencial"], bool):
            esperada = 1 if cliente["es_preferencial"] else 2
            if parada["cola_asignada"] != esperada:
                error(f"{ruta}.cola_asignada: en una cola preferencial se espera "
                      f"{esperada}, recibido {parada['cola_asignada']}")

        destinos = [s["hacia"] for s in estacion.get("salidas") or []]
        if j + 1 < len(paradas):
            if paradas[j + 1]["estacion_id"] not in destinos:
                error(f"{ruta}: de '{parada['estacion_id']}' no se puede pasar a "
                      f"'{paradas[j + 1]['estacion_id']}' (salidas: {destinos})")
        elif destinos:
            error(f"{ruta}: la última parada debe estar en una estación sin salidas")


def _validar_ocupacion_exclusiva(ocupacion: dict, error) -> None:
    """Un servidor atiende a un cliente a la vez: sus servicios no se solapan."""
    for (estacion_id, servidor), servicios in ocupacion.items():
        servicios.sort()
        for (_, fin, previo), (inicio, _, siguiente) in zip(servicios, servicios[1:]):
            if inicio < fin - TOLERANCIA:
                error(f"servidor {servidor} de '{estacion_id}': el cliente {siguiente} "
                      f"empieza a ser atendido en {inicio}, antes de que termine el "
                      f"cliente {previo} ({fin})")


def _validar_duracion_total(duracion_total, cierre, ultima_salida, error) -> None:
    """duracion_total_minutos = max(cierre, última salida) (política de cierre)."""
    if not _numero(duracion_total):
        return
    esperada = cierre if ultima_salida is None else max(cierre, ultima_salida)
    if abs(duracion_total - esperada) > TOLERANCIA:
        error(f"duracion_total_minutos: es {duracion_total} pero debe ser el máximo "
              f"entre el cierre ({cierre}) y la última salida "
              f"({ultima_salida}) = {esperada}")


def _validar_metricas(resultado: dict, estaciones: dict, exigir: bool, error) -> None:
    """Forma del bloque 'metricas' (solo claves; los valores los prueba Métricas)."""
    if "metricas" not in resultado:
        return
    metricas = resultado["metricas"]
    if not isinstance(metricas, dict) or set(metricas) != {"sistema_completo", "por_estacion"}:
        error("metricas: debe tener exactamente 'sistema_completo' y 'por_estacion'")
        return
    sistema = metricas["sistema_completo"]
    if not isinstance(sistema, dict) or set(sistema) != CLAVES_SISTEMA:
        error(f"metricas.sistema_completo: claves esperadas {sorted(CLAVES_SISTEMA)}")
    por_estacion = metricas["por_estacion"]
    if not isinstance(por_estacion, dict):
        error("metricas.por_estacion: debe ser un diccionario")
        return
    for estacion_id, datos in por_estacion.items():
        if estacion_id not in estaciones:
            error(f"metricas.por_estacion: '{estacion_id}' no existe en la config")
        elif not isinstance(datos, dict) or set(datos) != CLAVES_ESTACION:
            error(f"metricas.por_estacion.{estacion_id}: claves esperadas "
                  f"{sorted(CLAVES_ESTACION)}")
