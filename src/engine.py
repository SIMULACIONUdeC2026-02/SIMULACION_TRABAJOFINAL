"""Motor SimPy: primera entrega, una estación con cola FIFO compartida."""
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

    Primera entrega: método paralelo, una estación, cola única FIFO y uno
    o varios servidores, sin prioridad. Servicio exponencial o uniforme.
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
        if simulacion['metodo'] != 'paralelo' or len(estaciones) != 1:
            raise NotImplementedError('Primera entrega: paralelo con una estación')
        estacion = estaciones[0]
        colas = estacion['colas']
        if colas['tipo'] != 'unica' or colas['cantidad'] != 1 or simulacion.get('clientes_preferenciales') is not None:
            raise NotImplementedError('Primera entrega: cola única FIFO sin prioridad')

        duracion = _positivo(simulacion['duracion_minutos'], 'duracion_minutos')
        llegada = simulacion['llegada']
        if llegada['distribucion'] != 'poisson':
            raise NotImplementedError('Solo se admiten llegadas Poisson')
        tasa = _positivo(llegada['lambda_por_hora'], 'lambda_por_hora') / 60

        servidores = estacion['servidores']
        cantidad = len(servidores)
        if cantidad < 1:
            raise ValueError('cantidad de servidores debe ser un entero positivo')

        servicios_config = []
        for idx, srv in enumerate(servidores, 1):
            servicio = srv['servicio']
            tipo_srv = servicio['tipo']
            if tipo_srv == 'exponencial':
                media = _positivo(servicio['media'], f'servidor {idx} media')
                servicios_config.append(('exponencial', media))
            elif tipo_srv == 'uniforme':
                minimo = _finito_no_negativo(servicio['min'], f'servidor {idx} min')
                maximo = _positivo(servicio['max'], f'servidor {idx} max')
                if minimo >= maximo:
                    raise ValueError(f'servidor {idx}: min no puede ser mayor o igual que max')
                servicios_config.append(('uniforme', minimo, maximo))
            else:
                raise NotImplementedError('Servicio: exponencial o uniforme')

        estacion_id = estacion['id']
        nombre = simulacion.get('nombre', 'simulacion')
        semilla = simulacion.get('semilla')
        if semilla is not None and (isinstance(semilla, bool) or not isinstance(semilla, int)):
            raise ValueError('semilla debe ser un entero o null')
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError(f'Configuración incompleta o mal formada: {error}') from error

    azar = random.Random(semilla)
    entorno = simpy.Environment()
    # Store mantiene en FIFO a los clientes que esperan un servidor libre.
    disponibles = simpy.Store(entorno, capacity=cantidad)
    disponibles.items.extend(range(1, cantidad + 1))
    eventos = []

    def atender(cliente):
        """Recibe un evento de cliente; registra su servicio y devuelve un proceso."""
        servidor = yield disponibles.get()
        inicio = entorno.now
        conf_srv = servicios_config[servidor - 1]
        if conf_srv[0] == 'exponencial':
            tiempo = azar.expovariate(1.0 / conf_srv[1])
        else:
            tiempo = azar.uniform(conf_srv[1], conf_srv[2])
        yield entorno.timeout(tiempo)
        cliente['paradas'].append({
            'estacion_id': estacion_id,
            'tiempo_inicio_espera': cliente['tiempo_entrada_sistema'],
            'tiempo_inicio_servicio': inicio,
            'tiempo_fin_servicio': entorno.now,
            'servidor_asignado': servidor,
            'cola_asignada': 1,
        })
        cliente['tiempo_salida_sistema'] = entorno.now
        yield disponibles.put(servidor)

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
            entorno.process(atender(cliente))

    entorno.process(generar_llegadas())
    entorno.run()
    nombre_ascii = unicodedata.normalize('NFKD', str(nombre)).encode('ascii', 'ignore').decode()
    identificador = re.sub(r'[^a-z0-9]+', '_', nombre_ascii.lower()).strip('_') or 'simulacion'
    return {
        'simulacion_id': identificador,
        'duracion_total_minutos': max(duracion, entorno.now),
        'eventos_clientes': eventos,
    }
