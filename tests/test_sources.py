"""Testes do filtro de seleção dos datasets externos.

As mensagens aqui são inventadas para o teste, escritas só com as palavras-chave que
cada modelo precisa. Nenhuma frase vem dos datasets, que não têm licença aberta: o texto
deles fica em `data/external/`, fora do Git. Os links usam domínio reservado e não há
nome de pessoa nenhum.
"""

import pytest

from alerta_golpe.sources import _TEMPLATES, _match_template

GOLPES: tuple[tuple[str, str], ...] = (
    (
        "O Auxilio Brasil liberou uma parcela extra. Confira e faca o saque via Pix "
        "em https://parcela-extra.example/consulta",
        "auxilio-brasil-pix",
    ),
    (
        "Consulta do Registrato liberada: veja se existe valor a receber no seu nome.",
        "registrato-valores-a-receber",
    ),
    (
        "Ganhe agora cinquenta reais no Pix para comemorar a data com a familia.",
        "premio-pix-dia-das-criancas",
    ),
    (
        "O banco esta oferecendo ate R$ 3.000 de limite novo dentro do aplicativo.",
        "nubank-oferece-no-aplicativo",
    ),
    (
        "Pagamento dos seguintes boletos, me chame para combinar.",
        "boleto-com-desconto",
    ),
    (
        "Quer limpar seu nome e voltar a ter credito na praca? Falo no particular.",
        "limpa-nome-aumenta-score",
    ),
    (
        "Emprestimo liberado na hora mesmo para quem esta negativado, sem consulta.",
        "emprestimo-para-negativado",
    ),
    (
        "Entrei no esquema Pix de 50 e recebi muito mais de volta. Quer entrar?",
        "esquema-pix-multiplica-valor",
    ),
    (
        "Fazemos Pix online para quem precisa transferir acima do limite diario.",
        "pix-online-transferencia",
    ),
    (
        "Tenho uma carta de consorcio contemplado de automovel pronta para usar.",
        "consorcio-contemplado",
    ),
    ("Antecipacao 90% do saldo direto na sua conta, hoje mesmo.", "antecipacao-de-saldo"),
    (
        "Voce pode ganhar 137 reais por dia sem sair de casa.",
        "ganhe-por-dia-trabalhando-em-casa",
    ),
)

OUTRO_GENERO: tuple[str, ...] = (
    # Propaganda de bot e spam de investimento em cripto.
    "Ative o bot no grupo e receba os sinais automaticos todo dia de graca",
    "Compre bitcoin com a gente e veja seu dinheiro render todo mes",
    # Venda de documento e de gabarito.
    "Entrego diploma de qualquer faculdade, sem voce precisar estudar",
    "Tenho o gabarito da prova em maos, falo no particular",
    # Pirataria de TV e propaganda comercial.
    "Assine nossos canais de TV por um valor baixo, sem consulta ao SPC",
    # Política e doação de campanha.
    "Peca a sua camiseta de campanha e ajude a divulgar nosso candidato",
    # Passaporte sanitário.
    "Registro das doses da vacina feito direto no aplicativo do governo",
)


@pytest.mark.parametrize(("texto", "grupo"), GOLPES)
def test_reconhece_golpe_financeiro_contra_uma_pessoa(texto, grupo):
    resultado = _match_template(texto)
    assert resultado is not None
    assert resultado[0] == grupo


def test_todo_modelo_tem_um_caso_de_teste():
    # Modelo novo sem caso de teste quebra aqui, e não passa em silêncio.
    assert {grupo for _, grupo in GOLPES} == {grupo for grupo, _, _ in _TEMPLATES}


@pytest.mark.parametrize("texto", OUTRO_GENERO)
def test_descarta_o_que_nao_e_golpe_financeiro(texto):
    assert _match_template(texto) is None


def test_a_quebra_de_linha_nao_impede_o_reconhecimento():
    # Os anúncios vêm com título em linha separada, e o padrão roda sobre uma linha só.
    texto = (
        "*AUXILIO BRASIL*\n\nConfira se voce tem direito a parcela\n"
        "e faca o saque via Pix ainda hoje!"
    )
    assert _match_template(texto) is not None
