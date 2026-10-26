"""Ejemplo de punta a punta: ejecutar desde la raíz con python -m examples.ejecutar_engine."""
import json
from pathlib import Path
from src.engine import ejecutar_simulacion


def main():
    """Lee la configuración compartida y escribe el resultado JSON en consola."""
    ruta = Path(__file__).parent / 'configs_ejemplo/01_paralelo_cola_unica.json'
    config = json.loads(ruta.read_text(encoding='utf-8'))
    print(json.dumps({'resultado': ejecutar_simulacion(config)}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
