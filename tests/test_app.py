from streamlit.testing.v1 import AppTest

from alerta_golpe.explain import LEVEL_TITLES
from alerta_golpe.paths import PROJECT_ROOT

APP = str(PROJECT_ROOT / "app/streamlit_app.py")

# Rótulo do exemplo, no app, e o nível que ele tem que mostrar.
EXAMPLES = [
    ("Exemplo de golpe", "alto"),
    ("Exemplo com um ponto de atenção", "medio"),
    ("Exemplo sem sinais", "baixo"),
]


def _run():
    return AppTest.from_file(APP, default_timeout=30).run()


def _titles(app) -> list[str]:
    return (
        [bloco.value for bloco in app.error]
        + [bloco.value for bloco in app.warning]
        + [bloco.value for bloco in app.info]
    )


def _texts(app) -> list[str]:
    """Tudo que a tela mostra, por qualquer caminho de renderização."""
    return [bloco.value for bloco in app.text] + [bloco.value for bloco in app.markdown]


def test_abre_sem_resultado():
    app = _run()
    assert not app.exception
    assert _titles(app) == []


def test_clicar_no_exemplo_ja_verifica():
    for rotulo, nivel in EXAMPLES:
        app = _run().button(key=f"exemplo-{rotulo}").click().run()
        assert not app.exception
        assert any(LEVEL_TITLES[nivel] in titulo for titulo in _titles(app)), rotulo


def test_verificar_a_mensagem_colada():
    app = _run()
    app = app.text_area[0].set_value("Sua conta sera cancelada hoje, pague R$ 150,00").run()
    app = app.button(key="verificar").click().run()
    assert any(LEVEL_TITLES["alto"] in titulo for titulo in _titles(app))


def test_o_nivel_baixo_nao_usa_caixa_verde():
    # st.success é a caixa verde do Streamlit, e verde leria como "é seguro".
    app = _run().button(key="exemplo-Exemplo sem sinais").click().run()
    assert [bloco.value for bloco in app.info]
    assert not list(app.success)


def test_nao_mostra_o_link_do_golpe_clicavel():
    # O texto da pessoa sai por st.text, mas um link clicável apareceria em Markdown:
    # o teste confere os dois caminhos.
    app = _run().button(key="exemplo-Exemplo de golpe").click().run()
    assert all("banco-seguro.example" not in texto for texto in _texts(app))


def test_editar_a_mensagem_limpa_o_resultado():
    app = _run().button(key="exemplo-Exemplo de golpe").click().run()
    assert _titles(app)
    app = app.text_area[0].set_value("Oi, tudo bem?").run()
    assert _titles(app) == []


def test_pede_a_mensagem_quando_a_caixa_esta_vazia():
    app = _run()
    app = app.button(key="verificar").click().run()
    assert _titles(app) == []
    assert any("antes de clicar em Verificar" in texto for texto in _texts(app))


def test_a_caixa_tem_limite_de_caracteres():
    assert _run().text_area[0].proto.max_chars == 2000
