import pandas as pd
import pytest

from alerta_golpe.preprocessing import anonymize, drop_duplicate_messages, normalize_text


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("ligue (11) 98765-4321", "ligue <TELEFONE>"),
        ("ligue 11 98765-4321", "ligue <TELEFONE>"),
        ("ligue 11987654321", "ligue <TELEFONE>"),
        ("ligue 98765-4321", "ligue <TELEFONE>"),
        ("ligue 3333-4444", "ligue <TELEFONE>"),
        ("ligue +55 11 98765-4321", "ligue <TELEFONE>"),
        ("ligue 0800 123 4567", "ligue <TELEFONE>"),
    ],
)
def test_anonimiza_telefone_com_e_sem_ddd(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("escreva para suporte@banco.com.br", "escreva para <EMAIL>"),
        ("escreva para nome.sobrenome+tag@empresa.com", "escreva para <EMAIL>"),
    ],
)
def test_anonimiza_email(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("acesse https://banco-falso.com/entrar", "acesse <LINK>"),
        ("acesse www.banco-falso.com", "acesse <LINK>"),
        ("acesse banco-falso.com.br/atualize", "acesse <LINK>"),
        ("acesse bit.ly/pix-agora", "acesse <LINK>"),
    ],
)
def test_anonimiza_link_com_e_sem_http(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("acesse bit.ly/pix-agora, agora", "acesse <LINK>, agora"),
        ("acesse www.banco-falso.com.", "acesse <LINK>."),
        ("acesse https://banco-falso.com/entrar!", "acesse <LINK>!"),
    ],
)
def test_link_nao_engole_a_pontuacao_da_frase(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("CPF 123.456.789-01", "CPF <CPF>"),
        ("CPF 123456789-01", "CPF <CPF>"),
    ],
)
def test_anonimiza_cpf(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("pague via Pix CNPJ 12.345.678/0001-99", "pague via Pix CNPJ <CNPJ>"),
        ("pague via Pix CNPJ 12345678000199", "pague via Pix CNPJ <CNPJ>"),
        # Mensagem real da Vivo, publicada com um dígito faltando no CNPJ.
        ("pague via Pix CNPJ 3717195000142", "pague via Pix CNPJ <CNPJ>"),
    ],
)
def test_anonimiza_cnpj(texto, esperado):
    assert anonymize(texto) == esperado


def test_cnpj_nao_rouba_o_telefone():
    assert anonymize("ligue 11987654321 agora") == "ligue <TELEFONE> agora"


def test_cpf_sem_pontuacao_vira_telefone_mas_nao_fica_exposto():
    # Onze dígitos seguidos são ambíguos com celular e DDD: o marcador pode sair
    # errado, mas o número nunca fica em claro.
    assert anonymize("CPF 12345678901 bloqueado") == "CPF <TELEFONE> bloqueado"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("pague R$ 1.200,00 hoje", "pague <VALOR> hoje"),
        ("pague R$50 hoje", "pague <VALOR> hoje"),
        ("pague 1500 reais hoje", "pague <VALOR> hoje"),
        ("pague 1.200,00 reais hoje", "pague <VALOR> hoje"),
    ],
)
def test_anonimiza_valor_com_e_sem_real(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Olá Maria, sua fatura venceu", "Olá <NOME>, sua fatura venceu"),
        ("Sr. João da Silva, confirme", "Sr. <NOME>, confirme"),
        ("Sra. Benedita Souza, confirme", "Sra. <NOME>, confirme"),
        ("Prezada Ana Paula, acesse", "Prezada <NOME>, acesse"),
        ("Dona Benedita, seu aviso", "Dona <NOME>, seu aviso"),
        ("boa tarde Carlos", "boa tarde <NOME>"),
    ],
)
def test_anonimiza_nome_depois_de_saudacao(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "Oi Mãe, troquei de número",
        "Oi Pai, troquei de número",
        "Oi Filho, me manda um Pix",
        "Oi Filha, me manda um Pix",
        "Oi Vó, preciso de ajuda",
        "Oi Vô, preciso de ajuda",
        "Oi Tio, preciso de ajuda",
        "Oi Tia, preciso de ajuda",
        "Prezado Cliente, atualize seus dados",
        "Prezado Associado, atualize seus dados",
        "Prezada Associada, atualize seus dados",
        "Prezado Cooperado, confirme o Pix",
        "Prezada Cooperada, confirme o Pix",
        "Olá Usuário, sua conta será bloqueada",
        "Olá Usuária, sua conta será bloqueada",
        "Prezado Senhor, confirme seus dados",
        "Prezada Senhora, confirme seus dados",
        "Oi Amigo, tenho uma proposta",
        "Oi Amiga, tenho uma proposta",
        "Oi Querido, me ajuda",
        "Oi Querida, me ajuda",
        "Oi Tudo bem",
    ],
)
def test_tratamento_generico_nao_e_nome(texto):
    # Tratamento genérico no lugar do nome é sinal de golpe e precisa sobrar no texto.
    assert anonymize(texto) == texto


@pytest.mark.parametrize(
    "texto",
    [
        "Prezado Cliente Sicredi, confirme",
        "Olá Cliente Nubank",
        "Prezado Cliente Itaú",
        "Prezado Cliente Bradesco",
        "Prezado Cliente Santander",
        "Prezado Cliente Caixa",
        "Prezado Cliente Banco do Brasil",
        "Prezado Cliente Inter",
        "Olá Correios",
        "Olá Mercado Livre",
        "Olá Shopee",
        "Olá Amazon",
        "Olá Serasa",
        "Olá Receita Federal",
        "Prezado Cliente INSS",
        "Prezado Cliente Detran",
    ],
)
def test_nome_de_instituicao_nao_e_nome_de_pessoa(texto):
    # Marca imitada também é sinal de golpe: o nome da instituição fica no texto.
    assert anonymize(texto) == texto


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Prezado Cliente João, confirme", "Prezado Cliente <NOME>, confirme"),
        ("Prezado Cliente Sicredi João", "Prezado Cliente Sicredi <NOME>"),
        ("Prezada Associada Maria Souza", "Prezada Associada <NOME>"),
    ],
)
def test_nome_depois_de_tratamento_ou_instituicao_ainda_e_anonimizado(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.xfail(
    strict=True,
    reason="limitação conhecida: a regra de nome só olha depois de saudação ou "
    "pronome de tratamento, então nome no meio da frase não é detectado",
)
@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("a conta de Maria foi bloqueada", "a conta de <NOME> foi bloqueada"),
        ("fale com Carlos Souza sobre o Pix", "fale com <NOME> sobre o Pix"),
    ],
)
def test_nome_no_meio_da_frase(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("pedido 1234567890 entregue", "pedido <CODIGO> entregue"),
        ("Pedido 12345 saiu para entrega", "Pedido <CODIGO> saiu para entrega"),
        ("protocolo 2026-00123 aberto", "protocolo <CODIGO> aberto"),
        ("Codigo: 987654", "Codigo: <CODIGO>"),
        ("nº 445566 confirmado", "nº <CODIGO> confirmado"),
        ("n.º 445566 confirmado", "n.º <CODIGO> confirmado"),
        ("seu código é 123456", "seu código é <CODIGO>"),
        (
            "codigo de seguranca 123456 nao compartilhe",
            "codigo de seguranca <CODIGO> nao compartilhe",
        ),
    ],
)
def test_anonimiza_codigo(texto, esperado):
    assert anonymize(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        (
            "Digite o código que enviamos para (11) 98765-4321",
            "Digite o código que enviamos para <TELEFONE>",
        ),
        (
            "Digite o código que enviamos para 11 98765-4321",
            "Digite o código que enviamos para <TELEFONE>",
        ),
        ("codigo enviado para 98765-4321", "codigo enviado para <TELEFONE>"),
        # "no" é preposição, não o ordinal "nº": o número aqui é telefone.
        ("Fale no 3333-4444", "Fale no <TELEFONE>"),
    ],
)
def test_codigo_nao_quebra_telefone(texto, esperado):
    assert anonymize(texto) == esperado


def test_anonimiza_varios_marcadores_na_mesma_mensagem():
    texto = (
        "Olá Maria, sua fatura de R$ 1.200,00 do pedido 12345 venceu. "
        "Confirme o CPF 123.456.789-01 em bit.ly/pix-agora, "
        "escreva para golpe@falso.com ou ligue (11) 98765-4321"
    )
    assert anonymize(texto) == (
        "Olá <NOME>, sua fatura de <VALOR> do pedido <CODIGO> venceu. "
        "Confirme o CPF <CPF> em <LINK>, "
        "escreva para <EMAIL> ou ligue <TELEFONE>"
    )


@pytest.mark.parametrize(
    "texto",
    [
        "promoção válida até 10/10/2026",
        "sua encomenda chega amanhã",
        "Oi, tudo bem? Chegou sua encomenda.",
    ],
)
def test_texto_sem_dado_pessoal_fica_igual(texto):
    assert anonymize(texto) == texto


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("  Seu   ÚLTIMO  aviso  ", "seu ultimo aviso"),
        ("SUA CONTA SERÁ BLOQUEADA", "sua conta sera bloqueada"),
        ("ola mundo", "ola mundo"),
    ],
)
def test_normaliza_caixa_acento_e_espaco(texto, esperado):
    assert normalize_text(texto) == esperado


def test_normalizacao_preserva_marcadores_em_maiusculas():
    # Em minúsculas, <TELEFONE> viraria a palavra comum "telefone" no TF-IDF.
    normalizado = normalize_text(anonymize("Olá Maria, ligue (11) 98765-4321"))
    assert normalizado == "ola <NOME>, ligue <TELEFONE>"


def test_normalizacao_e_idempotente():
    assert normalize_text(normalize_text("  Olá   MUNDO ")) == "ola mundo"


def test_remove_duplicadas_comparando_texto_normalizado():
    mensagens = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "texto": [
                "Seu Pix foi bloqueado",
                "seu  pix foi   bloqueado",
                "Outra mensagem",
                "Seu Pix foi bloqueado",
            ],
        }
    )
    resultado = drop_duplicate_messages(mensagens)
    assert resultado["id"].tolist() == [1, 3]


def test_remove_duplicadas_nao_altera_o_dataframe_original():
    mensagens = pd.DataFrame({"texto": ["mesma", "mesma"]})
    drop_duplicate_messages(mensagens)
    assert len(mensagens) == 2
