# Simulación de sistemas de colas

Proyecto final de Simulación. Sistema que permite configurar y resolver
problemas de teoría de colas mediante simulación de eventos discretos:
llegadas de Poisson, atención exponencial o uniforme, y distintas
configuraciones de servidores y colas.

## Qué simula

- **Método 1 (paralelo):** el cliente va directo a un objetivo final.
- **Método 2 (secuencial):** el cliente pasa primero por un triaje inicial y
  luego por un objetivo específico.

En cada método hay 4 variantes: cola única con múltiples servidores, colas
múltiples con múltiples servidores, colas múltiples con clientes preferenciales
y múltiples servidores, y colas múltiples con servidor único.

Métricas: tiempo promedio en el sistema, clientes promedio, cola más larga,
rendimiento y tiempo ocioso por servidor, y tiempo promedio de atención.

## Instalación y uso

Requiere Python 3.11 o superior.

```bash
git clone git@github.com:SIMULACIONUdeC2026-02/SIMULACION_TRABAJOFINAL.git
cd SIMULACION_TRABAJOFINAL

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m pytest                    # correr las pruebas
python -m streamlit run src/app.py   # abrir la interfaz desde la raíz del repo
```

En **Configuración**, selecciona un escenario de ejemplo o configura uno
personalizado. Pulsa **Simular** y abre la pestaña **Resultados**.

## Estructura

```
.
├── docs/
│   └── contratos.md          # formato de entrada y de salida (LEER PRIMERO)
├── examples/
│   └── configs_ejemplo/      # configuraciones JSON de prueba
├── src/
│   ├── config.py             # contrato de entrada y validación
│   ├── engine.py             # motor SimPy
│   ├── topologias.py         # las 8 variantes
│   ├── metrics.py            # cálculo de métricas
│   └── app.py                # interfaz Streamlit
├── tests/
│   ├── test_engine.py
│   ├── test_topologias.py
│   └── test_metrics.py
└── .github/                  # plantillas de Issue y PR, CODEOWNERS
```

## Equipos

| Equipo | Responsabilidad | Archivos | Lo revisa |
|---|---|---|---|
| 1 - Engine | Motor de simulación en SimPy | `src/engine.py` | Topologías |
| 2 - Topologías | 8 variantes y contrato de entrada | `src/config.py`, `src/topologias.py` | Engine |
| 3 - Métricas | Cálculo de indicadores | `src/metrics.py` | UI |
| 4 - UI | Interfaz y visualizaciones | `src/app.py` | Métricas |

Cada equipo mantiene los tests de su módulo en `tests/`. La revisión cruzada
se pide sola mediante `.github/CODEOWNERS`.

## Cómo trabajamos

**Nadie hace push directo a `main`.** Todo cambio entra por Pull Request.

1. Toma un Issue del tablero y muévelo a "En progreso".
2. Crea tu rama desde `main` actualizada: `feature/<equipo>-<tarea>`, por
   ejemplo `feature/engine-generador-llegadas`.
3. Haz commits pequeños y frecuentes con prefijo:
   - `feat:` funcionalidad nueva
   - `fix:` corrección de un error
   - `docs:` documentación

   Opcional: alcance entre paréntesis, p. ej. `feat(engine): agrega generador de llegadas`.
   Un workflow avisa en el PR si algún commit no sigue el formato (no bloquea el merge).
4. Abre el Pull Request con la plantilla y escribe `Closes #N` con el número del
   Issue.
5. Necesitas al menos 1 aprobación. Nadie aprueba su propio PR.
6. Cuando se mergea, el Issue pasa a "Hecho".

### Tablero

| Columna | Significado |
|---|---|
| Backlog | Identificada, aún sin priorizar |
| Por hacer | Priorizada para este sprint |
| En progreso | Alguien trabaja en ella |
| En revisión (PR) | Hay un PR esperando aprobación |
| Hecho | Mergeada a `main` |

### Convenciones de código

- Nombres en español, coherentes con el dominio (`cliente`, `estacion`,
  `servidor`).
- `snake_case` para funciones y variables, `PascalCase` para clases.
- Toda función lleva docstring que diga qué recibe y qué devuelve.
- Si un cambio modifica un contrato de datos, se actualiza
  `docs/contratos.md` en el mismo PR y se avisa a los equipos afectados.
