"""Interfaz Streamlit para configurar y consultar simulaciones de colas."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import validar_config


TIPOS_COLA = {"Única": "unica", "Múltiple": "multiple", "Preferencial": "preferencial"}


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
    cuál es la cola más larga detectada por la simulación.

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
            yaxis_title="Longitud máxima",
        )

    nombres_colas = list(por_cola.keys())
    maximos = [float(por_cola[c].get("longitud_maxima", 0)) for c in nombres_colas]
    promedios = [float(por_cola[c].get("longitud_promedio", 0.0)) for c in nombres_colas]

    # Resalta la barra de la cola más larga con un color distintivo
    colores_max = [
        "#EF553B" if c == cola_mas_larga else "#636EFA"
        for c in nombres_colas
    ]
    colores_prom = [
        "#FFA15A" if c == cola_mas_larga else "#00CC96"
        for c in nombres_colas
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Longitud máxima",
        x=nombres_colas,
        y=maximos,
        text=[f"{v:g} (Mayor)" if c == cola_mas_larga else f"{v:g}" for c, v in zip(nombres_colas, maximos)],
        textposition="auto",
        marker_color=colores_max,
        hovertemplate="<b>%{x}</b><br>Longitud máxima: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Longitud promedio",
        x=nombres_colas,
        y=promedios,
        text=[f"{v:.2f}" for v in promedios],
        textposition="auto",
        marker_color=colores_prom,
        hovertemplate="<b>%{x}</b><br>Longitud promedio: %{y:.3f}<extra></extra>",
    ))

    titulo = f"Comparación de colas (Mayor: {cola_mas_larga})" if cola_mas_larga else "Comparación de colas"
    fig.update_layout(
        title=titulo,
        barmode="group",
        xaxis_title="Cola",
        yaxis_title="Clientes",
        legend_title="Métrica",
    )
    return fig


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
    st.dataframe(pd.DataFrame(columns=[
        "Estación", "Espera promedio (min)", "Atención promedio (min)",
        "Cola promedio", "Cola máxima", "Cola más larga",
    ]), hide_index=True, width="stretch")

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

        if st.button("Generar JSON", key="generar_configuracion"):
            config = construir_config(
                nombre, metodo, duracion, semilla, llegadas, estaciones,
                estacion_entrada, proporcion_preferencial,
            )
            errores = validar_config(config)
            if errores:
                st.error("Configuración inválida:\n" + "\n".join(f"- {error}" for error in errores))
            else:
                st.success("Configuración válida.")
            st.subheader("JSON de entrada")
            st.json(config)

    with resultados_tab:
        mostrar_resultados()


if __name__ == "__main__":
    main()
