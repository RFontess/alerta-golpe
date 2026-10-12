import pytest

from alerta_golpe.baseline import SIGNALS
from alerta_golpe.baseline import predict as baseline_predict
from alerta_golpe.explain import (
    CATEGORY_KEYWORDS,
    CATEGORY_TIPS,
    FALLBACK_CATEGORY,
    GENERAL_TIP,
    SIGNAL_PHRASES,
    explain,
)
from alerta_golpe.preprocessing import anonymize

CRU = "Sua conta será cancelada hoje. Pague R$ 150,00 em http://bit.ly/x1y2z3"


def test_anonimiza_antes_de_contar_os_sinais():
    # Sem anonimizar, "link" e "valor" nunca disparariam no app: quem cria os
    # marcadores é a anonimização, e na avaliação o CSV já vinha anonimizado.
    disparados = {sinal.name for sinal in explain(CRU).signals}
    assert {"link", "valor"} <= disparados


def test_mostra_a_palavra_inteira_e_nao_o_radical_da_regra():
    por_nome = {sinal.name: sinal.words for sinal in explain(CRU).signals}
    assert por_nome["ameaca"] == ["cancelada"]
    assert por_nome["link"] == ["um link"]
    assert por_nome["valor"] == ["um valor em dinheiro"]


@pytest.mark.parametrize(
    "texto",
    [
        CRU,
        "Sua fatura fechou e vence no dia 21",
        "Oi, consegue me fazer um Pix dos 40 do almoço?",
        "Bom dia, cheguei bem em casa",
        "Consulte seu auxílio e faça o saque via Pix: www.gov-auxilio.top",
    ],
)
def test_nivel_alto_se_e_somente_se_o_baseline_marca_golpe(texto):
    alto = explain(texto).level == "alto"
    assert alto == (baseline_predict(anonymize(texto)) == "golpe")


def test_um_sinal_so_da_nivel_medio():
    resultado = explain("Seu pedido chegou hoje")
    assert len(resultado.signals) == 1
    assert resultado.level == "medio"


def test_sem_sinais_o_nivel_e_baixo_com_a_dica_geral():
    resultado = explain("Bom dia, cheguei bem em casa")
    assert resultado.signals == []
    assert resultado.level == "baixo"
    assert resultado.general_tip == GENERAL_TIP


@pytest.mark.parametrize("nome", [nome for nome, _ in SIGNALS])
def test_todo_sinal_tem_frase(nome):
    assert SIGNAL_PHRASES[nome].strip()


@pytest.mark.parametrize("nome", [nome for nome, _ in CATEGORY_KEYWORDS] + [FALLBACK_CATEGORY])
def test_toda_categoria_tem_dica(nome):
    assert CATEGORY_TIPS[nome].strip()


def test_categoria_cai_no_fallback_quando_nenhuma_bate():
    assert explain("Bom dia, cheguei bem em casa").category == FALLBACK_CATEGORY
