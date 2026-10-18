"""Interfaz Streamlit para configurar y consultar simulaciones de colas."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import validar_config


TIPOS_COLA = {"Única": "unica", "Múltiple": "multiple", "Preferencial": "preferencial"}


def _capturar_servicio(prefijo: str, numero: int) -> dict:
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
        cantidad_colas = int(st.number_input(
            "Número de colas",
            min_value=2,
            value=max(2, cantidad_servidores),
            step=1,
            disabled=cantidad_servidores > 1,
            help=("Con varios servidores se usa una cola por servidor."
                  if cantidad_servidores > 1 else None),
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


def mostrar_resultados() -> None:
    """Deja la vista lista para mostrar resultados cuando se conecte el motor."""
    metrica_1, metrica_2, metrica_3 = st.columns(3)
    metrica_1.metric("Tiempo promedio en sistema", "—")
    metrica_2.metric("Clientes promedio en sistema", "—")
    metrica_3.metric("Clientes atendidos", "—")

    st.subheader("Resumen por estación")
    st.dataframe(pd.DataFrame(columns=[
        "Estación", "Espera promedio (min)", "Atención promedio (min)",
        "Cola promedio", "Cola máxima", "Cola más larga",
    ]), hide_index=True, width="stretch")

    colas, servidores = st.columns(2)
    with colas:
        st.subheader("Comparación de colas")
        st.plotly_chart(
            go.Figure().update_layout(xaxis_title="Cola", yaxis_title="Longitud máxima"),
            width="stretch",
        )
    with servidores:
        st.subheader("Utilización por servidor")
        st.plotly_chart(
            go.Figure().update_layout(xaxis_title="Servidor", yaxis_title="Utilización (%)"),
            width="stretch",
        )


def main() -> None:
    st.set_page_config(page_title="Simulación de colas", page_icon="📊", layout="wide")
    st.title("Simulación de sistemas de colas")
    st.write("Configura un escenario y revisa cómo se presentan los resultados de la simulación.")
    configuracion_tab, resultados_tab = st.tabs(["Configuración", "Resultados"])

    with configuracion_tab:
        st.caption("Los tiempos se expresan en minutos y la tasa de llegada en clientes por hora.")
        with st.form("formulario_configuracion"):
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

            generar = st.form_submit_button("Generar JSON", key="generar_configuracion")

        if generar:
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
