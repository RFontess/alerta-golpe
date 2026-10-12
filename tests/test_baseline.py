import pytest

from alerta_golpe.baseline import SIGNALS, predict, score, signals


@pytest.mark.parametrize(
    ("texto", "sinal"),
    [
        ("Sua conta será bloqueada hoje", "urgencia"),
        ("evite o bloqueio imediato", "ameaca"),
        ("acesse <LINK> para confirmar", "link"),
        ("pague <VALOR> hoje", "valor"),
        ("faça o saque via Pix", "pix"),
        ("atualize seus dados agora", "pedido de dados"),
        ("veja se você tem direito ao auxílio", "beneficio ou premio"),
        ("empréstimo na hora para quem está negativado", "credito para negativado"),
    ],
)
def test_reconhece_cada_sinal(texto, sinal):
    assert sinal in signals(texto)


def test_codigo_nao_conta_como_sinal_de_golpe():
    # <CODIGO> aparece em 9% dos golpes e 11% das legítimas: não separa.
    texto = "Este é o seu código de verificação: <CODIGO> Nunca compartilhe com ninguém"
    assert signals(texto) == []
    assert predict(texto) == "legitima"


def test_emoji_nao_conta_como_sinal_de_golpe():
    # Emoji é artefato de uma fonte: 70% nos anúncios de grupo, 0% nos golpes de SMS.
    assert signals("promoção 🎁💵 imperdível") == []


def test_tratamento_generico_nao_e_sinal_de_golpe():
    # Medido e invertido: 2% dos golpes contra 12% das legítimas.
    assert "tratamento generico" not in {nome for nome, _ in SIGNALS}
    assert signals("Prezado Cliente, sua fatura está disponível") == []


@pytest.mark.parametrize(
    "texto",
    [
        "evite o bloqueio imediato",
        "bloqueie seu cartao",
        "sua conta sera bloqueada",
        "seu acesso foi bloqueado",
        "vamos bloquear sua conta",
    ],
)
def test_ameaca_pega_as_formas_de_bloqueio(texto):
    # O radical era "bloquei", que deixava passar "bloqueada" e "bloqueado".
    assert "ameaca" in signals(texto)


def test_sinais_acentuados_sao_reconhecidos():
    # Os padrões rodam sobre o texto normalizado, sem acento.
    assert "ameaca" in signals("conta com restrição e pendência")
    assert "beneficio ou premio" in signals("indenização liberada")


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        # Mensagem inventada que dispara cinco sinais: urgência, valor, pix,
        # benefício e link.
        (
            "Você tem um benefício de <VALOR> liberado, receba agora pelo Pix: <LINK>",
            "golpe",
        ),
        # Legítima: um sinal só não basta.
        ("Sua fatura fechou e vence no dia 21", "legitima"),
        ("Oi, consegue me fazer um Pix dos 40 do almoço?", "legitima"),
    ],
)
def test_preve_com_o_limiar_padrao(texto, esperado):
    assert predict(texto) == esperado


def test_limiar_muda_a_decisao():
    texto = "Sua fatura de <VALOR> vence hoje"
    assert score(texto) == 2
    assert predict(texto, threshold=2) == "golpe"
    assert predict(texto, threshold=3) == "legitima"
