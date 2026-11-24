"""Ejemplo de punta a punta: corre simular() sobre un ejemplo y escribe el resultado JSON.

Desde la raíz del proyecto:
    python -m examples.ejecutar_engine                 # ejemplo 01 (por defecto)
    python -m examples.ejecutar_engine 05              # por número
    python -m examples.ejecutar_engine 07_secuencial_preferencial
    python -m examples.ejecutar_engine ruta/a/mi_config.json
    python -m examples.ejecutar_engine --lista         # muestra los 8 ejemplos
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.engine import simular

CARPETA_EJEMPLOS = Path(__file__).parent / 'configs_ejemplo'
EJEMPLO_POR_DEFECTO = '01_paralelo_cola_unica.json'


def listar_ejemplos() -> list[str]:
    """Devuelve los nombres de los archivos JSON de examples/configs_ejemplo, ordenados."""
    return sorted(ruta.name for ruta in CARPETA_EJEMPLOS.glob('*.json'))


def resolver_ejemplo(nombre: str) -> Path:
    """Convierte '05', '05_secuencial_cola_unica', el nombre del archivo o una ruta en un Path.

    Raises:
        FileNotFoundError: si no hay ningún ejemplo que coincida o hay más de uno.
    """
    ruta = Path(nombre)
    if ruta.is_file():
        return ruta

    base = nombre[:-5] if nombre.endswith('.json') else nombre
    coincidencias = [
        archivo for archivo in listar_ejemplos()
        if archivo[:-5] == base or archivo.startswith(f'{base}_')
    ]
    if len(coincidencias) != 1:
        disponibles = ', '.join(listar_ejemplos())
        motivo = 'ambiguo' if coincidencias else 'no encontrado'
        raise FileNotFoundError(f"Ejemplo '{nombre}' {motivo}. Disponibles: {disponibles}")
    return CARPETA_EJEMPLOS / coincidencias[0]


def main(argumentos: list[str] | None = None) -> int:
    """Lee la configuración elegida, ejecuta simular() y escribe el resultado JSON en consola."""
    parser = argparse.ArgumentParser(description='Ejecuta el motor sobre un ejemplo de configuración.')
    parser.add_argument(
        'ejemplo', nargs='?', default=EJEMPLO_POR_DEFECTO,
        help="número ('03'), nombre del ejemplo o ruta a un JSON (por defecto: 01)",
    )
    parser.add_argument('--lista', action='store_true', help='muestra los ejemplos disponibles y termina')
    args = parser.parse_args(argumentos)

    if args.lista:
        print('\n'.join(listar_ejemplos()))
        return 0

    try:
        ruta = resolver_ejemplo(args.ejemplo)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1

    config = json.loads(ruta.read_text(encoding='utf-8'))
    print(json.dumps(simular(config), indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
