import json
from pathlib import Path
from streamlit.testing.v1 import AppTest

from src.app import crear_grafica_comparacion_colas
from src.config import validar_config
from src.app import tabla_por_estacion

def generar_json(app):
    app.button(key="generar_configuracion").click().run()


def test_app_muestra_formulario_y_resultados_vacios():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()

    assert not app.exception
    assert app.text_input(key="nombre_simulacion")
    assert app.selectbox(key="metodo")
    assert app.button(key="generar_configuracion")
    assert any(tab.label == "Resultados" for tab in app.tabs)
    assert app.dataframe[0].value.empty
    assert len(app.get("plotly_chart")) == 1
    assert all(not json.loads(chart.proto.spec)["data"] for chart in app.get("plotly_chart"))
    assert [metric.value for metric in app.metric] == ["—", "—", "—"]
    assert not app.get("progress")
    assert any("no hay datos de utilización" in aviso.value for aviso in app.info)


def test_utilizacion_muestra_porcentajes_y_marca_saturacion():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.session_state["resultado"] = {
        "resultado": {
            "metricas": {
                "por_estacion": {
                    "cajeros": {
                        "por_servidor": {
                            "servidor_1": {"utilizacion": 0.754},
                            "servidor_2": {"utilizacion": 0.90},
                            "servidor_3": {"utilizacion": 0.85},
                        },
                    },
                },
            },
        },
    }
    app.run()

    assert not app.exception
    assert [(metrica.label, metrica.value) for metrica in app.metric[3:]] == [
        ("servidor_1", "75.4%"),
        ("servidor_2 · SATURADO", "90.0%"),
        ("servidor_3", "85.0%"),
    ]
    assert len(app.get("progress")) == 3


def test_utilizacion_del_ejemplo_secuencial_muestra_las_dos_estaciones():
    ruta = (
        Path(__file__).resolve().parents[1] / "examples" / "resultados_ejemplo"
        / "02_secuencial_preferencial_resultado.json"
    )
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.session_state["resultado"] = json.loads(ruta.read_text(encoding="utf-8"))
    app.run()

    assert not app.exception
    assert {"**triaje**", "**atencion**"} <= {elemento.value for elemento in app.markdown}
    assert [(metrica.label, metrica.value) for metrica in app.metric[3:]] == [
        ("servidor_1", "23.3%"),
        ("servidor_1", "33.3%"),
        ("servidor_2", "33.3%"),
    ]


def test_formulario_genera_configuracion_paralela_valida():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    generar_json(app)

    config = json.loads(app.json[0].value)
    assert config["simulacion"]["metodo"] == "paralelo"
    assert "nombre" not in config["simulacion"]
    assert "estacion_entrada" not in config["simulacion"]
    assert "nombre" in config["estaciones"][0]
    assert config["estaciones"][0]["servidores"] == [
        {"id": "s1", "servicio": {"tipo": "exponencial", "media": 2.0}},
        {"id": "s2", "servicio": {"tipo": "exponencial", "media": 2.0}},
        {"id": "s3", "servicio": {"tipo": "exponencial", "media": 2.0}},
    ]
    assert config["estaciones"][0]["colas"] == {
        "tipo": "unica", "cantidad": 1, "reparticion": None
    }
    assert config["estaciones"][0]["salidas"] == []
    assert validar_config(config) == []
    assert not app.error


def test_formulario_genera_servicios_individuales_y_colas_multiples():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="estacion_1_servidor_2_tipo").select("Uniforme")
    app.selectbox(key="estacion_1_tipo_cola").select("Múltiple")
    generar_json(app)

    config = json.loads(app.json[0].value)
    assert config["estaciones"][0]["servidores"][1]["servicio"] == {
        "tipo": "uniforme", "min": 1.0, "max": 3.0
    }
    assert config["estaciones"][0]["colas"] == {
        "tipo": "multiple", "cantidad": 3, "reparticion": "round_robin"
    }
    assert validar_config(config) == []


def test_cantidad_colas_multiples_sigue_a_los_servidores():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="estacion_1_tipo_cola").select("Múltiple").run()
    assert app.selectbox(key="estacion_1_reparticion")
    generar_json(app)

    app.number_input(key="estacion_1_servidores").set_value(2).run()
    assert any(caption.value == "Colas: 2 (una por servidor)" for caption in app.caption)
    generar_json(app)

    config = json.loads(app.json[0].value)
    assert config["estaciones"][0]["colas"]["cantidad"] == 2
    assert validar_config(config) == []
    assert not app.error


def test_campos_dependientes_se_actualizan_sin_generar_json():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="estacion_1_servidor_2_tipo").select("Uniforme").run()

    assert app.number_input(key="estacion_1_servidor_2_min")
    assert app.number_input(key="estacion_1_servidor_2_max")

    app.selectbox(key="estacion_1_tipo_cola").select("Preferencial").run()
    assert app.number_input(key="proporcion_preferencial")


def test_formulario_genera_configuracion_secuencial_valida():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="metodo").select("Método 2 (secuencial)")
    generar_json(app)

    config = json.loads(app.json[0].value)
    assert config["simulacion"]["metodo"] == "secuencial"
    assert config["simulacion"]["estacion_entrada"] == "cajeros"
    assert len(config["estaciones"]) == 2
    assert config["estaciones"][0]["salidas"] == [
        {"hacia": "atencion", "probabilidad": 1.0}
    ]
    assert config["estaciones"][1]["salidas"] == []
    assert validar_config(config) == []


def test_formulario_genera_rutas_secuenciales_ramificadas():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="metodo").select("Método 2 (secuencial)")
    generar_json(app)
    app.number_input(key="cantidad_estaciones").set_value(3)
    generar_json(app)
    app.get("multiselect")[0].select("estacion_3")
    generar_json(app)
    app.number_input(key="probabilidad_0_atencion").set_value(0.6)
    app.number_input(key="probabilidad_0_estacion_3").set_value(0.4)
    generar_json(app)

    config = json.loads(app.json[0].value)
    assert config["estaciones"][0]["salidas"] == [
        {"hacia": "atencion", "probabilidad": 0.6},
        {"hacia": "estacion_3", "probabilidad": 0.4},
    ]
    assert validar_config(config) == []


def test_formulario_ubica_proporcion_preferencial_en_simulacion():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="estacion_1_tipo_cola").select("Preferencial")
    generar_json(app)

    config = json.loads(app.json[0].value)
    assert config["simulacion"]["clientes_preferenciales"] == {"proporcion": 0.2}
    assert "clientes_preferenciales" not in config["estaciones"][0]
    assert validar_config(config) == []


def test_formulario_muestra_errores_del_validador():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.text_input(key="estacion_1_id").set_value("")
    generar_json(app)

    assert any("estaciones[0].id" in error.value for error in app.error)


def test_tabla_por_estacion_con_ejemplo_02():
    ruta = Path(__file__).parent.parent / "examples/resultados_ejemplo/02_secuencial_preferencial_resultado.json"
    metricas = json.loads(ruta.read_text(encoding="utf-8"))["resultado"]["metricas"]
    tabla = tabla_por_estacion(metricas)
    assert list(tabla["Estación"]) == ["triaje", "atencion"]
    assert tabla.loc[1, "Cola más larga"] == "cola_2"
def test_boton_simular_guarda_resultado_real_en_session_state():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.button(key="ejecutar_simulacion").click().run()

    assert not app.exception
    assert not app.error
    salida = app.session_state["resultado"]
    assert set(salida) == {"resultado"}
    eventos = salida["resultado"]["eventos_clientes"]
    assert eventos
    assert eventos[0]["paradas"][0]["estacion_id"] == "cajeros"


def test_boton_simular_con_config_invalida_muestra_error():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.text_input(key="estacion_1_id").set_value("")
    app.button(key="ejecutar_simulacion").click().run()

    assert "resultado" not in app.session_state
    assert any("estaciones[0].id" in error.value for error in app.error)


def test_crear_grafica_comparacion_colas_vacia():
    fig = crear_grafica_comparacion_colas()
    assert len(fig.data) == 0
    assert fig.layout.xaxis.title.text == "Cola"
    assert fig.layout.yaxis.title.text == "Clientes"


def test_crear_grafica_comparacion_colas_con_datos_resalta_mayor():
    por_cola = {
        "cola_1": {"longitud_promedio": 0.0333, "longitud_maxima": 1},
        "cola_2": {"longitud_promedio": 0.1, "longitud_maxima": 1},
    }
    cola_mas_larga = "cola_2"
    fig = crear_grafica_comparacion_colas(por_cola, cola_mas_larga)

    assert len(fig.data) == 2
    trace_max, trace_prom = fig.data[0], fig.data[1]
    assert trace_max.name == "Longitud máxima"
    assert trace_prom.name == "Longitud promedio"
    assert list(trace_max.x) == ["cola_1", "cola_2"]
    assert list(trace_max.y) == [1.0, 1.0]

    # Los colores por métrica son uniformes y coinciden con la leyenda
    assert trace_max.marker.color == "#636EFA"
    assert trace_prom.marker.color == "#00CC96"

    # La cola más larga ("cola_2") se resalta con un borde en sus dos barras
    assert trace_max.marker.line.width[1] > 0
    assert trace_prom.marker.line.width[1] > 0
    assert trace_max.marker.line.width[0] == 0
    assert trace_prom.marker.line.width[0] == 0

    # No se incluye '(Mayor)' sobre el valor de la barra para evitar confusiones
    assert "Mayor" not in trace_max.text[0]
    assert "Mayor" not in trace_max.text[1]
    assert list(trace_max.text) == ["1", "1"]

    # Se marca la cola mayor en el eje X
    assert fig.layout.xaxis.ticktext[1] == "cola_2 ★"
    assert fig.layout.title.text == "Comparación de colas (Mayor: cola_2)"
    assert fig.layout.yaxis.title.text == "Clientes"
