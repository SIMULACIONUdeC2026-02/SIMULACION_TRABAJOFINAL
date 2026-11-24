"""Interfaz Streamlit para configurar y consultar simulaciones de colas."""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# `streamlit run src/app.py` solo agrega src/ al path; el motor importa como `src.*`,
# así que se agrega también la raíz del proyecto.
_RAIZ_PROYECTO = str(Path(__file__).resolve().parents[1])
if _RAIZ_PROYECTO not in sys.path:
    sys.path.insert(0, _RAIZ_PROYECTO)

from config import validar_config  # noqa: E402
from src.engine import simular  # noqa: E402


TIPOS_COLA = {"Única": "unica", "Múltiple": "multiple", "Preferencial": "preferencial"}
COLUMNAS_ESTACION = ["Estación", "Espera promedio (min)","Atención promedio (min)","Cola promedio","Cola máxima", "Cola más larga"] 

def _capturar_servicio(prefijo: str, numero: int) -> dict:
    """Captura la distribución de servicio configurada para un servidor."""
    tipo = st.selectbox(
        f"Servicio del servidor {numero}",
        ["Exponencial", "Uniforme"],
        key=f"{prefijo}_servidor_{numero}_tipo",
    )
    if tipo == "Exponencial":
        return {
            "tipo": "exponencial",
            "media": st.number_input(
                f"Media del servidor {numero} (min)",
                min_value=0.1,
                value=2.0,
                step=0.1,
                key=f"{prefijo}_servidor_{numero}_media",
            ),
        }

    minimo, maximo = st.columns(2)
    return {
        "tipo": "uniforme",
        "min": minimo.number_input(
            f"Mínimo del servidor {numero} (min)",
            min_value=0.0,
            value=1.0,
            step=0.1,
            key=f"{prefijo}_servidor_{numero}_min",
        ),
        "max": maximo.number_input(
            f"Máximo del servidor {numero} (min)",
            min_value=0.1,
            value=3.0,
            step=0.1,
            key=f"{prefijo}_servidor_{numero}_max",
        ),
    }


def configurar_estacion(etiqueta: str, prefijo: str, id_por_defecto: str) -> dict:
    """Captura una estación y arma su estructura según el contrato vigente."""
    st.subheader(etiqueta)
    col_id, col_nombre, col_servidores = st.columns(3)
    identificador = col_id.text_input("ID", value=id_por_defecto, key=f"{prefijo}_id")
    nombre = col_nombre.text_input("Nombre", value=etiqueta, key=f"{prefijo}_nombre")
    cantidad_servidores = int(col_servidores.number_input(
        "Servidores", min_value=1, value=3, step=1, key=f"{prefijo}_servidores"
    ))

    servidores = []
    for numero in range(1, cantidad_servidores + 1):
        servicio = _capturar_servicio(prefijo, numero)
        servidores.append({"id": f"s{numero}", "servicio": servicio})

    tipo_cola_ui = st.selectbox(
        "Tipo de cola", list(TIPOS_COLA), key=f"{prefijo}_tipo_cola"
    )
    tipo_cola = TIPOS_COLA[tipo_cola_ui]
    reparticion = None
    if tipo_cola == "multiple":
        if cantidad_servidores > 1:
            cantidad_colas = cantidad_servidores
            st.caption(f"Colas: {cantidad_colas} (una por servidor)")
        else:
            cantidad_colas = int(st.number_input(
                "Número de colas", min_value=2, value=2, step=1,
                key=f"{prefijo}_cantidad_colas",
            ))
        reparticion = st.selectbox(
            "Repartición de clientes",
            ["round_robin", "aleatoria", "mas_corta"],
            key=f"{prefijo}_reparticion",
        )
    else:
        cantidad_colas = 2 if tipo_cola == "preferencial" else 1

    estacion = {
        "id": identificador.strip(),
        "servidores": servidores,
        "colas": {
            "tipo": tipo_cola,
            "cantidad": cantidad_colas,
            "reparticion": reparticion,
        },
        "salidas": [],
    }
    if nombre.strip():
        estacion["nombre"] = nombre.strip()
    return estacion


def configurar_salidas(estaciones: list[dict]) -> None:
    """Permite rutas secuenciales; el validador informa ciclos o probabilidades inválidas."""
    ids = [estacion["id"] for estacion in estaciones]
    st.subheader("Rutas entre estaciones")
    for indice, estacion in enumerate(estaciones):
        destinos = [identificador for identificador in ids if identificador != estacion["id"]]
        siguiente = ids[indice + 1] if indice + 1 < len(ids) else None
        default = [siguiente] if siguiente in destinos else []
        seleccionados = st.multiselect(
            f"Salidas de {estacion['nombre'] or estacion['id']}",
            destinos,
            default=default,
            key=f"salidas_{indice}",
            help="Sin destinos, los clientes salen del sistema al terminar esta estación.",
        )
        rutas = []
        for destino in seleccionados:
            probabilidad = st.number_input(
                f"Probabilidad hacia {destino} desde {estacion['id'] or f'estación {indice + 1}'}",
                min_value=0.0,
                max_value=1.0,
                value=1.0 / len(seleccionados),
                step=0.05,
                key=f"probabilidad_{indice}_{destino}",
            )
            rutas.append({"hacia": destino, "probabilidad": probabilidad})
        estacion["salidas"] = rutas


def construir_config(
    nombre: str,
    metodo: str,
    duracion: int,
    semilla: int,
    llegadas: float,
    estaciones: list[dict],
    estacion_entrada: str | None = None,
    proporcion_preferencial: float | None = None,
) -> dict:
    """Arma el JSON de entrada sin añadir campos fuera del contrato."""
    simulacion = {
        "metodo": metodo,
        "duracion_minutos": int(duracion),
        "semilla": int(semilla),
        "llegada": {"distribucion": "poisson", "lambda_por_hora": llegadas},
    }
    if nombre.strip():
        simulacion["nombre"] = nombre.strip()
    if proporcion_preferencial is not None:
        simulacion["clientes_preferenciales"] = {
            "proporcion": proporcion_preferencial
        }
    if metodo == "secuencial":
        simulacion["estacion_entrada"] = estacion_entrada

    return {"simulacion": simulacion, "estaciones": estaciones}


def crear_grafica_comparacion_colas(
    por_cola: dict[str, dict[str, float | int]] | None = None,
    cola_mas_larga: str | None = None,
) -> go.Figure:
    """
    Crea una gráfica de barras en Plotly para comparar las colas de una estación.

    Compara la longitud máxima y promedio de cada cola, y resalta visualmente
    cuál es la cola más larga detectada por la simulación con un borde en sus
    dos barras y marcando la etiqueta en el eje X.

    Args:
        por_cola: Diccionario con métricas de cada cola
            (ej. {'cola_1': {'longitud_promedio': 1.5, 'longitud_maxima': 4}}).
        cola_mas_larga: Clave de la cola con mayor longitud (ej. 'cola_1').

    Returns:
        go.Figure: Gráfica interactiva de Plotly con las barras comparativas.
    """
    if not por_cola:
        return go.Figure().update_layout(
            xaxis_title="Cola",
            yaxis_title="Clientes",
        )

    nombres_colas = list(por_cola.keys())
    maximos = [float(por_cola[c].get("longitud_maxima", 0)) for c in nombres_colas]
    promedios = [float(por_cola[c].get("longitud_promedio", 0.0)) for c in nombres_colas]

    # Resalta la barra de la cola más larga con un borde distintivo sin alterar
    # el color de la métrica (para que coincida con la leyenda).
    bordes_color = [
        "#1F1F1F" if c == cola_mas_larga else "rgba(0,0,0,0)"
        for c in nombres_colas
    ]
    bordes_ancho = [
        2.5 if c == cola_mas_larga else 0
        for c in nombres_colas
    ]
    etiquetas_x = [
        f"{c} ★" if c == cola_mas_larga else c
        for c in nombres_colas
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Longitud máxima",
        x=nombres_colas,
        y=maximos,
        text=[f"{v:g}" for v in maximos],
        textposition="auto",
        marker_color="#636EFA",
        marker_line_color=bordes_color,
        marker_line_width=bordes_ancho,
        hovertemplate="<b>%{x}</b><br>Longitud máxima: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Longitud promedio",
        x=nombres_colas,
        y=promedios,
        text=[f"{v:.2f}" for v in promedios],
        textposition="auto",
        marker_color="#00CC96",
        marker_line_color=bordes_color,
        marker_line_width=bordes_ancho,
        hovertemplate="<b>%{x}</b><br>Longitud promedio: %{y:.3f}<extra></extra>",
    ))

    titulo = f"Comparación de colas (Mayor: {cola_mas_larga})" if cola_mas_larga else "Comparación de colas"
    fig.update_layout(
        title=titulo,
        barmode="group",
        xaxis=dict(
            title="Cola",
            tickmode="array",
            tickvals=nombres_colas,
            ticktext=etiquetas_x,
        ),
        yaxis_title="Clientes",
        legend_title="Métrica",
    )
    return fig


def tabla_por_estacion(metricas: dict) -> pd.DataFrame:    
        """Arma la tabla resumen a partir de metricas["por_estacion"] (contrato de salida)."""
        por_estacion = metricas.get("por_estacion",{})
        filas=[]
        for nombre_estacion, info in por_estacion.items():
            filas.append([nombre_estacion,
                    info.get("tiempo_promedio_espera_cola"),
                    info.get("tiempo_promedio_atencion"),
                    info.get("longitud_promedio_cola"),
                    info.get("longitud_maxima_cola"),
                    info.get("cola_mas_larga")
                    ])
        tabla_resultante=pd.DataFrame(filas,columns=COLUMNAS_ESTACION)
        return tabla_resultante


def mostrar_resultados(resultado: dict | None = None) -> None:
    """Muestra los resultados de la simulación o vistas vacías si no hay datos."""
    if resultado is None and "resultado" in st.session_state:
        resultado = st.session_state["resultado"]

    metricas = {}
    if resultado and isinstance(resultado, dict):
        metricas = resultado.get("resultado", resultado).get("metricas", {})

    sistema = metricas.get("sistema_completo", {})
    t_sistema = sistema.get("tiempo_promedio_en_sistema")
    c_sistema = sistema.get("clientes_promedio_en_sistema")
    atendidos = sistema.get("clientes_totales_atendidos")

    metrica_1, metrica_2, metrica_3 = st.columns(3)
    metrica_1.metric("Tiempo promedio en sistema", f"{t_sistema:.2f} min" if t_sistema is not None else "—")
    metrica_2.metric("Clientes promedio en sistema", f"{c_sistema:.2f}" if c_sistema is not None else "—")
    metrica_3.metric("Clientes atendidos", str(atendidos) if atendidos is not None else "—")

    st.subheader("Resumen por estación")
    st.dataframe(tabla_por_estacion(metricas) if metricas else pd.DataFrame(columns=COLUMNAS_ESTACION), hide_index=True, width="stretch")

    colas, servidores = st.columns(2)
    with colas:
        st.subheader("Comparación de colas")
        por_estacion = metricas.get("por_estacion", {})
        if por_estacion:
            estaciones_disponibles = list(por_estacion.keys())
            if len(estaciones_disponibles) > 1:
                estacion_sel = st.selectbox(
                    "Estación para comparar colas",
                    estaciones_disponibles,
                    key="selector_estacion_colas",
                )
            else:
                estacion_sel = estaciones_disponibles[0]
            datos_estacion = por_estacion.get(estacion_sel, {})
            por_cola = datos_estacion.get("por_cola", {})
            cola_mas_larga = datos_estacion.get("cola_mas_larga")
            fig_colas = crear_grafica_comparacion_colas(por_cola, cola_mas_larga)
            st.plotly_chart(fig_colas)
            if cola_mas_larga:
                st.caption(f"Cola más larga en {estacion_sel}: **{cola_mas_larga}**")
        else:
            fig_vacia = crear_grafica_comparacion_colas()
            st.plotly_chart(fig_vacia)

    with servidores:
        st.subheader("Utilización por servidor")
        st.plotly_chart(
            go.Figure().update_layout(xaxis_title="Servidor", yaxis_title="Utilización (%)"),
        )


def main() -> None:
    st.set_page_config(page_title="Simulación de colas", page_icon="📊", layout="wide")
    st.title("Simulación de sistemas de colas")
    st.write("Configura un escenario y revisa cómo se presentan los resultados de la simulación.")
    configuracion_tab, resultados_tab = st.tabs(["Configuración", "Resultados"])

    with configuracion_tab:
        st.caption("Los tiempos se expresan en minutos y la tasa de llegada en clientes por hora.")
        st.subheader("Datos de la simulación")
        nombre = st.text_input("Nombre de la simulación", value="", key="nombre_simulacion")
        metodo_ui = st.selectbox(
            "Método", ["Método 1 (paralelo)", "Método 2 (secuencial)"], key="metodo"
        )
        col_duracion, col_semilla, col_llegadas = st.columns(3)
        duracion = col_duracion.number_input("Duración (min)", min_value=1, value=480, step=1)
        semilla = col_semilla.number_input("Semilla", min_value=0, value=42, step=1)
        llegadas = col_llegadas.number_input(
            "Llegadas por hora", min_value=0.1, value=40.0, step=1.0
        )

        metodo = "paralelo" if metodo_ui == "Método 1 (paralelo)" else "secuencial"
        cantidad_estaciones = 1
        if metodo == "secuencial":
            cantidad_estaciones = int(st.number_input(
                "Número de estaciones", min_value=2, value=2, step=1,
                key="cantidad_estaciones",
            ))

        estaciones = []
        for indice in range(cantidad_estaciones):
            if indice == 0:
                id_default = "cajeros"
            elif indice == 1:
                id_default = "atencion"
            else:
                id_default = f"estacion_{indice + 1}"
            nombre_estacion = f"Estación {indice + 1}"
            estaciones.append(configurar_estacion(
                nombre_estacion, f"estacion_{indice + 1}", id_default
            ))

        estacion_entrada = None
        if metodo == "secuencial":
            configurar_salidas(estaciones)
            ids = [estacion["id"] for estacion in estaciones]
            estacion_entrada = st.selectbox(
                "Estación de entrada", ids, key="estacion_entrada"
            )

        proporcion_preferencial = None
        if any(estacion["colas"]["tipo"] == "preferencial" for estacion in estaciones):
            proporcion_preferencial = st.number_input(
                "Proporción de clientes preferenciales",
                min_value=0.01,
                max_value=0.99,
                value=0.2,
                step=0.05,
                key="proporcion_preferencial",
            )

        config = construir_config(
            nombre, metodo, duracion, semilla, llegadas, estaciones,
            estacion_entrada, proporcion_preferencial,
        )

        col_generar, col_simular = st.columns(2)
        if col_generar.button("Generar JSON", key="generar_configuracion"):
            errores = validar_config(config)
            if errores:
                st.error("Configuración inválida:\n" + "\n".join(f"- {error}" for error in errores))
            else:
                st.success("Configuración válida.")
            st.subheader("JSON de entrada")
            st.json(config)

        if col_simular.button("Simular", key="ejecutar_simulacion", type="primary"):
            ejecutar_y_guardar(config)

    with resultados_tab:
        mostrar_resultados()


def ejecutar_y_guardar(config: dict) -> None:
    """Corre la simulación completa y guarda {"resultado": ...} en st.session_state["resultado"]."""
    try:
        salida = simular(config)
    except (ValueError, NotImplementedError, RuntimeError) as error:
        st.session_state.pop("resultado", None)
        st.error(f"No se pudo simular:\n{error}")
        return

    st.session_state["resultado"] = salida
    resultado = salida["resultado"]
    st.success(
        f"Simulación lista: {len(resultado['eventos_clientes'])} clientes atendidos en "
        f"{resultado['duracion_total_minutos']:.2f} min. Revisa la pestaña Resultados."
    )
    if "metricas" not in resultado:
        st.info("Las métricas aún no están disponibles (pendiente Issue #17 de Métricas).")


if __name__ == "__main__":
    main()
