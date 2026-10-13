import pytest

from alerta_golpe.baseline import SIGNALS
from alerta_golpe.baseline import predict as baseline_predict
from alerta_golpe.explain import (
    CATEGORY_KEYWORDS,
    CATEGORY_TIPS,
    FALLBACK_CATEGORY,
    GENERAL_TIP,
    LEVEL_MESSAGES,
    LEVEL_TITLES,
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


def _excerpts(texto: str) -> dict[str, list[str]]:
    return {sinal.name: sinal.excerpts for sinal in explain(texto).signals}


def test_mostra_a_palavra_inteira_e_nao_o_radical_da_regra():
    por_nome = _excerpts(CRU)
    assert por_nome["ameaca"] == ["cancelada"]
    assert por_nome["link"] == ["um link"]
    assert por_nome["valor"] == ["um valor em dinheiro"]


def test_mostra_o_trecho_inteiro_quando_a_regra_casa_varias_palavras():
    # A regra casa "atualize seus dados"; a tela mostra a frase, não palavra por palavra.
    assert _excerpts("Atualize seus dados hoje")["pedido de dados"] == ["Atualize seus dados"]


def test_a_virgula_separa_trechos_diferentes_do_mesmo_sinal():
    por_nome = _excerpts("Urgente: a fatura vence hoje")
    assert por_nome["urgencia"] == ["Urgente", "vence", "hoje"]


def test_o_trecho_sai_como_a_pessoa_escreveu():
    # Acento e maiúscula do original, sem a pontuação das pontas.
    assert _excerpts("Clique aqui, é rápido")["pedido de dados"] == ["Clique aqui"]


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


@pytest.mark.parametrize("nivel", ["alto", "medio", "baixo"])
def test_todo_nivel_tem_titulo_e_mensagem(nivel):
    assert LEVEL_TITLES[nivel].strip()
    assert LEVEL_MESSAGES[nivel].strip()


def test_o_titulo_diz_o_nivel_sem_depender_da_cor():
    assert explain(CRU).title == LEVEL_TITLES["alto"]
    assert "golpe" in explain(CRU).title


def test_nenhum_texto_da_tela_fala_de_endereco():
    # Para muita gente idosa, endereço é o de casa: na tela é sempre "link".
    textos = [
        *SIGNAL_PHRASES.values(),
        *CATEGORY_TIPS.values(),
        *LEVEL_TITLES.values(),
        *LEVEL_MESSAGES.values(),
        GENERAL_TIP,
    ]
    assert all("endereç" not in texto for texto in textos)


def test_devolve_o_texto_anonimizado_que_leu():
    anonimizado = explain(CRU).anonymized
    assert "<LINK>" in anonimizado and "<VALOR>" in anonimizado
    assert "bit.ly" not in anonimizado
