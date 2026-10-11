import pytest

from alerta_golpe.review import find_suspects


@pytest.mark.parametrize(
    "texto",
    [
        "Data: 26/07/2026 20:36 (GMT)",
        "Presente pra você 25.000 pontos em 12 meses!",
        "Seu código de verificação: <CODIGO>",
        "acesse <LINK> para ver a fatura de <VALOR>",
    ],
)
def test_data_e_milhar_nao_sao_suspeita(texto):
    # Data de login e contagem de pontos não identificam ninguém.
    assert find_suspects(texto) == []


@pytest.mark.parametrize(
    "texto",
    [
        "acesse https://banco-falso.com",
        "escreva para pessoa@exemplo.com",
        "rastreio BR123456789BR",
        "Envio padrão: 3320077642132",
        "CPF 123.456.789-01",
        "CNPJ 12.345.678/0001-99",
    ],
)
def test_acusa_dado_pessoal_que_sobrou(texto):
    assert find_suspects(texto) != []
