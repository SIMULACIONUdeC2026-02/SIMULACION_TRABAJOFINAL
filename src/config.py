"""
config.py - Contrato de entrada (configuración de la simulación).

Responsables: Equipo 2 (Topologías). Revisa: Equipo 1 (Engine).

Define qué forma tiene una configuración válida y la valida. La referencia
completa del formato y de su significado está en docs/contratos.md. Si cambia
la estructura del JSON, hay que actualizar ese documento y avisar a Engine,
Métricas y UI.
"""

METODOS = ("paralelo", "secuencial")  # Método 1 / Método 2
DISTRIBUCIONES_SERVICIO = ("exponencial", "uniforme")
TIPOS_COLA = ("unica", "multiple", "preferencial")
REPARTICIONES = ("round_robin", "aleatoria", "mas_corta")

TOLERANCIA_PROBABILIDAD = 1e-9

_CLAVES_CONFIG = {"simulacion", "estaciones"}
_CLAVES_SIMULACION = {
    "nombre", "metodo", "duracion_minutos", "semilla", "llegada",
    "clientes_preferenciales", "estacion_entrada",
}
_CLAVES_LLEGADA = {"distribucion", "lambda_por_hora"}
_CLAVES_PREFERENCIALES = {"proporcion"}
_CLAVES_ESTACION = {"id", "nombre", "servidores", "colas", "salidas"}
_CLAVES_SERVIDOR = {"id", "servicio"}
_CLAVES_COLAS = {"tipo", "cantidad", "reparticion"}
_CLAVES_SALIDA = {"hacia", "probabilidad"}
_CLAVES_EXPONENCIAL = {"tipo", "media"}
_CLAVES_UNIFORME = {"tipo", "min", "max"}


def validar_config(config: dict) -> list[str]:
    """
    Valida una configuración contra el contrato de entrada.

    No lanza excepciones por datos mal formados: devuelve todos los errores
    encontrados, cada uno con la ruta del campo (por ejemplo
    "estaciones[0].colas.cantidad: ..."), para poder mostrarlos de una vez.
    También señala claves desconocidas, para detectar errores de escritura
    como "reparticon".

    Args:
        config: diccionario con los bloques "simulacion" y "estaciones".

    Returns:
        Lista de mensajes de error. Lista vacía si la configuración es válida.
    """
    if not isinstance(config, dict):
        return ["config: debe ser un objeto (diccionario)"]

    errores: list[str] = []
    _claves_desconocidas(config, _CLAVES_CONFIG, "config", errores)

    contexto = {"metodo": None, "entrada": None, "preferenciales": False}
    simulacion = _obtener_objeto(config, "simulacion", "simulacion", errores)
    if simulacion is not None:
        contexto = _validar_simulacion(simulacion, errores)

    estaciones = config.get("estaciones")
    if not isinstance(estaciones, list) or not estaciones:
        errores.append("estaciones: debe ser una lista con al menos una estación")
    else:
        _validar_estaciones(estaciones, contexto, errores)

    return errores


# --------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------

def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_texto(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _obtener_objeto(padre: dict, clave: str, ruta: str, errores: list[str]):
    """Devuelve padre[clave] si es un objeto; si no, registra el error."""
    valor = padre.get(clave)
    if not isinstance(valor, dict):
        errores.append(f"{ruta}: es obligatorio y debe ser un objeto")
        return None
    return valor


def _claves_desconocidas(objeto: dict, permitidas: set, ruta: str,
                         errores: list[str]) -> None:
    for clave in sorted(set(objeto) - permitidas, key=str):
        errores.append(
            f"{ruta}: la clave {clave!r} no existe en el contrato "
            f"(permitidas: {', '.join(sorted(permitidas))})"
        )


# --------------------------------------------------------------------------
# Bloque "simulacion"
# --------------------------------------------------------------------------

def _validar_simulacion(sim: dict, errores: list[str]) -> dict:
    """
    Valida el bloque simulacion.

    Devuelve un contexto con lo que las estaciones necesitan saber:
    el método, la estación de entrada y si hay clientes preferenciales.
    """
    contexto = {"metodo": None, "entrada": None, "preferenciales": False}
    _claves_desconocidas(sim, _CLAVES_SIMULACION, "simulacion", errores)

    metodo = sim.get("metodo")
    if metodo in METODOS:
        contexto["metodo"] = metodo
    else:
        errores.append(
            f"simulacion.metodo: debe ser uno de {METODOS}, recibido {metodo!r}"
        )

    duracion = sim.get("duracion_minutos")
    if not _es_numero(duracion) or duracion <= 0:
        errores.append("simulacion.duracion_minutos: debe ser un número mayor que 0")

    semilla = sim.get("semilla")
    if semilla is not None and not _es_entero(semilla):
        errores.append("simulacion.semilla: debe ser un entero (o no incluirse)")

    llegada = _obtener_objeto(sim, "llegada", "simulacion.llegada", errores)
    if llegada is not None:
        _claves_desconocidas(
            llegada, _CLAVES_LLEGADA, "simulacion.llegada", errores
        )
        if llegada.get("distribucion") != "poisson":
            errores.append(
                "simulacion.llegada.distribucion: debe ser 'poisson', "
                f"recibido {llegada.get('distribucion')!r}"
            )
        tasa = llegada.get("lambda_por_hora")
        if not _es_numero(tasa) or tasa <= 0:
            errores.append(
                "simulacion.llegada.lambda_por_hora: debe ser un número mayor que 0"
            )

    preferenciales = sim.get("clientes_preferenciales")
    if preferenciales is not None:
        ruta = "simulacion.clientes_preferenciales"
        if not isinstance(preferenciales, dict):
            errores.append(f"{ruta}: debe ser un objeto (o no incluirse)")
        else:
            contexto["preferenciales"] = True
            _claves_desconocidas(
                preferenciales, _CLAVES_PREFERENCIALES, ruta, errores
            )
            proporcion = preferenciales.get("proporcion")
            if not _es_numero(proporcion) or not 0 < proporcion < 1:
                errores.append(
                    f"{ruta}.proporcion: debe ser un número mayor que 0 y menor que 1"
                )

    entrada = sim.get("estacion_entrada")
    if entrada is not None:
        if _es_texto(entrada):
            contexto["entrada"] = entrada
        else:
            errores.append(
                "simulacion.estacion_entrada: debe ser el id de una estación"
            )
    elif contexto["metodo"] == "secuencial":
        errores.append(
            "simulacion.estacion_entrada: es obligatoria en el método 'secuencial'"
        )

    return contexto


# --------------------------------------------------------------------------
# Bloque "estaciones"
# --------------------------------------------------------------------------

def _validar_estaciones(estaciones: list, contexto: dict,
                        errores: list[str]) -> None:
    infos = []
    for i, estacion in enumerate(estaciones):
        ruta = f"estaciones[{i}]"
        if not isinstance(estacion, dict):
            errores.append(f"{ruta}: debe ser un objeto")
            infos.append(None)
            continue
        infos.append(_validar_estacion(estacion, ruta, contexto, errores))

    ids = [info["id"] for info in infos if info is not None and info["id"]]
    repetidos = sorted({x for x in ids if ids.count(x) > 1})
    for repetido in repetidos:
        errores.append(f"estaciones: el id {repetido!r} está repetido")

    metodo = contexto["metodo"]
    entrada = contexto["entrada"]

    if metodo == "paralelo":
        if len(estaciones) != 1:
            errores.append(
                "estaciones: el método 'paralelo' requiere exactamente 1 "
                f"estación (hay {len(estaciones)})"
            )
        else:
            info = infos[0]
            if info is not None and info["salidas"]:
                errores.append(
                    "estaciones[0].salidas: debe estar vacía en el método 'paralelo'"
                )
            if (info is not None and entrada is not None and info["id"]
                    and entrada != info["id"]):
                errores.append(
                    f"simulacion.estacion_entrada: {entrada!r} no coincide con "
                    f"la única estación ({info['id']!r})"
                )
    elif metodo == "secuencial":
        if len(estaciones) < 2:
            errores.append(
                "estaciones: el método 'secuencial' requiere al menos 2 "
                f"estaciones (hay {len(estaciones)})"
            )
        elif not repetidos and all(
                info is not None and info["id"] for info in infos):
            _validar_grafo(infos, entrada, errores)


def _validar_estacion(est: dict, ruta: str, contexto: dict,
                      errores: list[str]) -> dict:
    """Valida una estación. Devuelve {'id', 'salidas'} para validar el grafo."""
    _claves_desconocidas(est, _CLAVES_ESTACION, ruta, errores)

    id_estacion = est.get("id")
    if not _es_texto(id_estacion):
        errores.append(f"{ruta}.id: debe ser un texto no vacío")
        id_estacion = None

    cantidad_servidores = _validar_servidores(est, ruta, errores)

    colas = _obtener_objeto(est, "colas", f"{ruta}.colas", errores)
    if colas is not None:
        _validar_colas(colas, cantidad_servidores, contexto,
                       f"{ruta}.colas", errores)

    salidas = _validar_salidas(est, ruta, errores)
    return {"id": id_estacion, "salidas": salidas}


def _validar_servidores(est: dict, ruta: str, errores: list[str]):
    """Valida la lista de servidores. Devuelve cuántos hay, o None si es inválida."""
    servidores = est.get("servidores")
    ruta_lista = f"{ruta}.servidores"
    if not isinstance(servidores, list) or not servidores:
        errores.append(f"{ruta_lista}: debe ser una lista con al menos un servidor")
        return None

    ids = []
    for j, servidor in enumerate(servidores):
        ruta_servidor = f"{ruta_lista}[{j}]"
        if not isinstance(servidor, dict):
            errores.append(f"{ruta_servidor}: debe ser un objeto")
            continue
        _claves_desconocidas(servidor, _CLAVES_SERVIDOR, ruta_servidor, errores)

        id_servidor = servidor.get("id")
        if _es_texto(id_servidor):
            ids.append(id_servidor)
        else:
            errores.append(f"{ruta_servidor}.id: debe ser un texto no vacío")

        servicio = _obtener_objeto(
            servidor, "servicio", f"{ruta_servidor}.servicio", errores
        )
        if servicio is not None:
            _validar_servicio(servicio, f"{ruta_servidor}.servicio", errores)

    for repetido in sorted({x for x in ids if ids.count(x) > 1}):
        errores.append(f"{ruta_lista}: el id {repetido!r} está repetido")

    return len(servidores)


def _validar_servicio(dist: dict, ruta: str, errores: list[str]) -> None:
    tipo = dist.get("tipo")
    if tipo not in DISTRIBUCIONES_SERVICIO:
        errores.append(
            f"{ruta}.tipo: debe ser uno de {DISTRIBUCIONES_SERVICIO}, "
            f"recibido {tipo!r}"
        )
        return

    if tipo == "exponencial":
        _claves_desconocidas(dist, _CLAVES_EXPONENCIAL, ruta, errores)
        media = dist.get("media")
        if not _es_numero(media) or media <= 0:
            errores.append(f"{ruta}.media: debe ser un número mayor que 0")
        return

    _claves_desconocidas(dist, _CLAVES_UNIFORME, ruta, errores)
    minimo, maximo = dist.get("min"), dist.get("max")
    minimo_ok = _es_numero(minimo) and minimo >= 0
    maximo_ok = _es_numero(maximo) and maximo > 0
    if not minimo_ok:
        errores.append(f"{ruta}.min: debe ser un número mayor o igual a 0")
    if not maximo_ok:
        errores.append(f"{ruta}.max: debe ser un número mayor que 0")
    if minimo_ok and maximo_ok and minimo >= maximo:
        errores.append(f"{ruta}: 'min' debe ser menor que 'max'")


def _validar_colas(colas: dict, cantidad_servidores, contexto: dict,
                   ruta: str, errores: list[str]) -> None:
    _claves_desconocidas(colas, _CLAVES_COLAS, ruta, errores)

    cantidad = colas.get("cantidad")
    cantidad_ok = _es_entero(cantidad) and cantidad >= 1
    if not cantidad_ok:
        errores.append(f"{ruta}.cantidad: debe ser un entero mayor o igual a 1")

    tipo = colas.get("tipo")
    tipo_ok = tipo in TIPOS_COLA
    if not tipo_ok:
        errores.append(
            f"{ruta}.tipo: debe ser uno de {TIPOS_COLA}, recibido {tipo!r}"
        )

    reparticion = colas.get("reparticion")
    if reparticion is not None and reparticion not in REPARTICIONES:
        errores.append(
            f"{ruta}.reparticion: debe ser null o una de {REPARTICIONES}, "
            f"recibido {reparticion!r}"
        )

    if not (cantidad_ok and tipo_ok):
        return

    if tipo == "unica":
        if cantidad != 1:
            errores.append(f"{ruta}: el tipo 'unica' requiere cantidad = 1")
        if reparticion is not None:
            errores.append(
                f"{ruta}.reparticion: debe ser null cuando hay una sola cola"
            )

    elif tipo == "multiple":
        if cantidad < 2:
            errores.append(f"{ruta}: el tipo 'multiple' requiere cantidad >= 2")
        if reparticion is None:
            errores.append(
                f"{ruta}.reparticion: es obligatoria con colas 'multiple' "
                f"({REPARTICIONES})"
            )
        if (cantidad_servidores is not None and cantidad_servidores > 1
                and cantidad != cantidad_servidores):
            errores.append(
                f"{ruta}.cantidad: con {cantidad_servidores} servidores, las "
                f"colas 'multiple' requieren una cola por servidor "
                f"(cantidad = {cantidad_servidores}), recibido {cantidad}"
            )

    else:  # preferencial
        if cantidad != 2:
            errores.append(
                f"{ruta}: el tipo 'preferencial' requiere exactamente 2 colas "
                "(la 1 es preferencial y la 2 es normal)"
            )
        if reparticion is not None:
            errores.append(
                f"{ruta}.reparticion: debe ser null con colas 'preferencial' "
                "(la clase del cliente decide su cola)"
            )
        if not contexto["preferenciales"]:
            errores.append(
                f"{ruta}.tipo: 'preferencial' requiere definir "
                "simulacion.clientes_preferenciales"
            )


def _validar_salidas(est: dict, ruta: str, errores: list[str]) -> list:
    """Valida las rutas de salida. Devuelve la lista de (hacia, probabilidad)."""
    salidas = est.get("salidas")
    if salidas is None:
        return []
    ruta_lista = f"{ruta}.salidas"
    if not isinstance(salidas, list):
        errores.append(f"{ruta_lista}: debe ser una lista (vacía si sale del sistema)")
        return []

    rutas = []
    for j, salida in enumerate(salidas):
        ruta_salida = f"{ruta_lista}[{j}]"
        if not isinstance(salida, dict):
            errores.append(f"{ruta_salida}: debe ser un objeto")
            continue
        _claves_desconocidas(salida, _CLAVES_SALIDA, ruta_salida, errores)

        destino = salida.get("hacia")
        probabilidad = salida.get("probabilidad")
        destino_ok = _es_texto(destino)
        probabilidad_ok = _es_numero(probabilidad) and 0 < probabilidad <= 1
        if not destino_ok:
            errores.append(f"{ruta_salida}.hacia: debe ser el id de una estación")
        if not probabilidad_ok:
            errores.append(
                f"{ruta_salida}.probabilidad: debe ser un número mayor que 0 "
                "y menor o igual a 1"
            )
        if destino_ok and probabilidad_ok:
            rutas.append((destino, probabilidad))

    destinos = [destino for destino, _ in rutas]
    for repetido in sorted({x for x in destinos if destinos.count(x) > 1}):
        errores.append(f"{ruta_lista}: el destino {repetido!r} está repetido")

    if rutas and len(rutas) == len(salidas):
        suma = sum(probabilidad for _, probabilidad in rutas)
        if abs(suma - 1) > TOLERANCIA_PROBABILIDAD:
            errores.append(
                f"{ruta_lista}: las probabilidades deben sumar 1 (suman {suma})"
            )
    return rutas


def _validar_grafo(infos: list, entrada, errores: list[str]) -> None:
    """Método secuencial: las rutas deben formar un grafo sin ciclos y conexo."""
    ids = {info["id"] for info in infos}

    if entrada is not None and entrada not in ids:
        errores.append(
            f"simulacion.estacion_entrada: {entrada!r} no es una estación "
            f"existente ({', '.join(sorted(ids))})"
        )

    rutas_validas = True
    for info in infos:
        for destino, _ in info["salidas"]:
            if destino not in ids:
                errores.append(
                    f"estaciones: la estación {info['id']!r} envía clientes a "
                    f"{destino!r}, que no existe"
                )
                rutas_validas = False
    if not rutas_validas or entrada is None or entrada not in ids:
        return

    vecinos = {
        info["id"]: [destino for destino, _ in info["salidas"]] for info in infos
    }

    if _hay_ciclo(vecinos):
        errores.append(
            "estaciones: las salidas forman un ciclo; los clientes solo pueden "
            "avanzar hacia adelante"
        )
        return

    visitadas = set()
    pendientes = [entrada]
    while pendientes:
        actual = pendientes.pop()
        if actual in visitadas:
            continue
        visitadas.add(actual)
        pendientes.extend(vecinos[actual])

    for id_estacion in sorted(ids - visitadas):
        errores.append(
            f"estaciones: la estación {id_estacion!r} no es alcanzable desde "
            f"la estación de entrada {entrada!r}"
        )


def _hay_ciclo(vecinos: dict) -> bool:
    """Detección de ciclos por búsqueda en profundidad (grafos pequeños)."""
    en_curso, terminados = set(), set()

    def visitar(nodo) -> bool:
        if nodo in terminados:
            return False
        if nodo in en_curso:
            return True
        en_curso.add(nodo)
        for vecino in vecinos[nodo]:
            if visitar(vecino):
                return True
        en_curso.discard(nodo)
        terminados.add(nodo)
        return False

    return any(visitar(nodo) for nodo in vecinos)
