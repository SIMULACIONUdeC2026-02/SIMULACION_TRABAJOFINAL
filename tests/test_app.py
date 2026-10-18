import json

from streamlit.testing.v1 import AppTest

from src.config import validar_config


def enviar_formulario(app):
    app.form_submit_button[0].click().run()


def test_app_muestra_formulario_y_resultados_vacios():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()

    assert not app.exception
    assert app.text_input(key="nombre_simulacion")
    assert app.selectbox(key="metodo")
    assert app.button(key="generar_configuracion")
    assert any(tab.label == "Resultados" for tab in app.tabs)
    assert app.dataframe[0].value.empty
    assert len(app.get("plotly_chart")) == 2
    assert all(not json.loads(chart.proto.spec)["data"] for chart in app.get("plotly_chart"))
    assert [metric.value for metric in app.metric] == ["—", "—", "—"]


def test_formulario_genera_configuracion_paralela_valida():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    enviar_formulario(app)

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
    enviar_formulario(app)

    config = json.loads(app.json[0].value)
    assert config["estaciones"][0]["servidores"][1]["servicio"] == {
        "tipo": "uniforme", "min": 1.0, "max": 3.0
    }
    assert config["estaciones"][0]["colas"] == {
        "tipo": "multiple", "cantidad": 3, "reparticion": "round_robin"
    }
    assert validar_config(config) == []


def test_formulario_genera_configuracion_secuencial_valida():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="metodo").select("Método 2 (secuencial)")
    enviar_formulario(app)

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
    enviar_formulario(app)
    app.number_input(key="cantidad_estaciones").set_value(3)
    enviar_formulario(app)
    app.get("multiselect")[0].select("estacion_3")
    enviar_formulario(app)
    app.number_input(key="probabilidad_0_atencion").set_value(0.6)
    app.number_input(key="probabilidad_0_estacion_3").set_value(0.4)
    enviar_formulario(app)

    config = json.loads(app.json[0].value)
    assert config["estaciones"][0]["salidas"] == [
        {"hacia": "atencion", "probabilidad": 0.6},
        {"hacia": "estacion_3", "probabilidad": 0.4},
    ]
    assert validar_config(config) == []


def test_formulario_ubica_proporcion_preferencial_en_simulacion():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.selectbox(key="estacion_1_tipo_cola").select("Preferencial")
    enviar_formulario(app)

    config = json.loads(app.json[0].value)
    assert config["simulacion"]["clientes_preferenciales"] == {"proporcion": 0.2}
    assert "clientes_preferenciales" not in config["estaciones"][0]
    assert validar_config(config) == []


def test_formulario_muestra_errores_del_validador():
    app = AppTest.from_file("../src/app.py", default_timeout=15).run()
    app.text_input(key="estacion_1_id").set_value("")
    enviar_formulario(app)

    assert any("estaciones[0].id" in error.value for error in app.error)
