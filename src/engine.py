"""Motor SimPy: simulación de eventos discretos para teoría de colas."""
from __future__ import annotations

import math
import random
import re
import unicodedata

import simpy

from src.config import validar_config


def _positivo(valor, nombre: str):
    """Recibe un valor numérico y su nombre; devuelve el valor o lanza ValueError."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nombre} debe ser un número finito mayor que cero")
    return valor


def _finito_no_negativo(valor, nombre: str):
    """Recibe un valor numérico y su nombre; devuelve el valor si es finito y >= 0 o lanza ValueError."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nombre} debe ser un número finito mayor o igual a cero")
    return valor


def ejecutar_simulacion(config: dict) -> dict:
    """Recibe el contrato de entrada y devuelve datos crudos sin envolver en 'resultado'.

    Soporta:
    - Método paralelo (1 estación) y método secuencial (N estaciones en serie o con rutas).
    - Colas únicas FIFO por estación con uno o varios servidores.
    - Servicio exponencial o uniforme por cada servidor.

    Las llegadas se generan hasta duracion_minutos (extremo excluido).
    Después se atiende a los clientes pendientes; duracion_total_minutos
    incluye ese vaciado y nunca es menor que la ventana de llegadas.
    Una semilla fija reproduce los eventos sin alterar el generador global.
    Configuraciones incompletas o inválidas lanzan ValueError; variantes
    aún no implementadas lanzan NotImplementedError.
    """
    errores = validar_config(config)
    if errores:
        raise ValueError("Configuración incompleta o mal formada:\n" + "\n".join(f"- {e}" for e in errores))

    try:
        simulacion = config['simulacion']
        estaciones = config['estaciones']
        metodo = simulacion.get('metodo')
        if metodo not in ('paralelo', 'secuencial'):
            raise NotImplementedError(f"Método '{metodo}' no soportado")

        if simulacion.get('clientes_preferenciales') is not None:
            raise NotImplementedError('Pendiente: Clientes preferenciales (Etapa 3)')

        duracion = _positivo(simulacion['duracion_minutos'], 'duracion_minutos')
        llegada = simulacion['llegada']
        if llegada['distribucion'] != 'poisson':
            raise NotImplementedError('Solo se admiten llegadas Poisson')
        tasa = _positivo(llegada['lambda_por_hora'], 'lambda_por_hora') / 60.0

        semilla = simulacion.get('semilla')
        if semilla is not None and (isinstance(semilla, bool) or not isinstance(semilla, int)):
            raise ValueError('semilla debe ser un entero o null')
        nombre = simulacion.get('nombre', 'simulacion')

        # Procesar y validar cada estación
        estaciones_map = {}
        for est in estaciones:
            est_id = est['id']
            colas = est['colas']
            if colas.get('tipo') != 'unica' or colas.get('cantidad') != 1:
                raise NotImplementedError(
                    f"Estación '{est_id}': tipo de cola '{colas.get('tipo')}' no soportado aún (Etapa 2)"
                )

            servidores = est['servidores']
            cantidad_srv = len(servidores)
            if cantidad_srv < 1:
                raise ValueError(f"Estación '{est_id}': cantidad de servidores debe ser mayor que cero")

            servicios_config = []
            for idx, srv in enumerate(servidores, 1):
                servicio = srv['servicio']
                tipo_srv = servicio['tipo']
                if tipo_srv == 'exponencial':
                    media = _positivo(servicio['media'], f"estacion '{est_id}' servidor {idx} media")
                    servicios_config.append(('exponencial', media))
                elif tipo_srv == 'uniforme':
                    minimo = _finito_no_negativo(servicio['min'], f"estacion '{est_id}' servidor {idx} min")
                    maximo = _positivo(servicio['max'], f"estacion '{est_id}' servidor {idx} max")
                    if minimo >= maximo:
                        raise ValueError(f"estacion '{est_id}' servidor {idx}: min debe ser menor que max")
                    servicios_config.append(('uniforme', minimo, maximo))
                else:
                    raise NotImplementedError(f"Servicio no soportado: '{tipo_srv}'")

            estaciones_map[est_id] = {
                'id': est_id,
                'cantidad_servidores': cantidad_srv,
                'servicios': servicios_config,
                'salidas': est.get('salidas', []),
            }

        estacion_inicial = simulacion.get('estacion_entrada', estaciones[0]['id'])

    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError(f'Configuración incompleta o mal formada: {error}') from error

    azar = random.Random(semilla)
    entorno = simpy.Environment()

    # Cada estación maneja sus servidores disponibles (IDs 1..cantidad) en un Store FIFO
    for est_info in estaciones_map.values():
        cant = est_info['cantidad_servidores']
        almacen = simpy.Store(entorno, capacity=cant)
        almacen.items.extend(range(1, cant + 1))
        est_info['disponibles'] = almacen

    eventos = []

    def atender_en_estacion(est_id: str, cliente: dict):
        """Atiende al cliente en una estación y determina la siguiente parada."""
        est_info = estaciones_map[est_id]
        t_inicio_espera = entorno.now
        servidor = yield est_info['disponibles'].get()
        t_inicio_servicio = entorno.now

        conf_srv = est_info['servicios'][servidor - 1]
        if conf_srv[0] == 'exponencial':
            tiempo = azar.expovariate(1.0 / conf_srv[1])
        else:
            tiempo = azar.uniform(conf_srv[1], conf_srv[2])
        yield entorno.timeout(tiempo)

        t_fin_servicio = entorno.now
        cliente['paradas'].append({
            'estacion_id': est_id,
            'tiempo_inicio_espera': t_inicio_espera,
            'tiempo_inicio_servicio': t_inicio_servicio,
            'tiempo_fin_servicio': t_fin_servicio,
            'servidor_asignado': servidor,
            'cola_asignada': 1,
        })
        yield est_info['disponibles'].put(servidor)

        salidas = est_info['salidas']
        if salidas:
            destinos = [s['hacia'] for s in salidas]
            pesos = [s['probabilidad'] for s in salidas]
            siguiente_id = azar.choices(destinos, weights=pesos, k=1)[0]
            return siguiente_id
        return None

    def proceso_cliente(cliente: dict):
        """Ciclo de vida del cliente desde su entrada hasta su salida del sistema."""
        estacion_actual_id = estacion_inicial
        while estacion_actual_id is not None:
            estacion_actual_id = yield from atender_en_estacion(estacion_actual_id, cliente)
        cliente['tiempo_salida_sistema'] = entorno.now

    def generar_llegadas():
        """Genera el proceso de llegadas externas dentro de la ventana configurada."""
        while True:
            intervalo = azar.expovariate(tasa)
            if entorno.now + intervalo >= duracion:
                return
            yield entorno.timeout(intervalo)
            cliente = {
                'cliente_id': len(eventos) + 1,
                'es_preferencial': False,
                'tiempo_entrada_sistema': entorno.now,
                'tiempo_salida_sistema': None,
                'paradas': [],
            }
            eventos.append(cliente)
            entorno.process(proceso_cliente(cliente))

    entorno.process(generar_llegadas())
    entorno.run()

    nombre_ascii = unicodedata.normalize('NFKD', str(nombre)).encode('ascii', 'ignore').decode()
    identificador = re.sub(r'[^a-z0-9]+', '_', nombre_ascii.lower()).strip('_') or 'simulacion'
    return {
        'simulacion_id': identificador,
        'duracion_total_minutos': max(duracion, entorno.now),
        'eventos_clientes': eventos,
    }
