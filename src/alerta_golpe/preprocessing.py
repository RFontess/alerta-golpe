"""Limpeza e anonimização das mensagens.

A anonimização roda antes da normalização, porque a regra de nomes depende das
letras maiúsculas do texto original.
"""

import re
import unicodedata

import pandas as pd

MARKERS = (
    "<TELEFONE>",
    "<EMAIL>",
    "<NOME>",
    "<CPF>",
    "<CNPJ>",
    "<VALOR>",
    "<LINK>",
    "<CODIGO>",
)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Golpes costumam encurtar o link ou omitir o "http", por isso a lista de domínios.
_LINK = re.compile(
    # O espaço depois do esquema aparece em golpe real ("https:// rebrand.ly/x") e
    # o \S* deixa o esquema sozinho também virar marcador, sem sobrar texto cru.
    r"(?:https?://[ \t]*\S*"
    r"|www\.\S+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|br|net|org|gov|info|xyz|top|link|site|app|io|me|co"
    r"|ly|gl|tk|cc|online|shop|store|digital|vip|click)(?:\.[a-z]{2})?(?:/\S*)?)",
    re.IGNORECASE,
)

# Golpe de Pix costuma mandar pagar para o CNPJ de um microempreendedor que não
# tem nada a ver com a fraude, então o número é dado de uma pessoa lesada.
# Roda antes do telefone e aceita de doze a quatorze dígitos: as mensagens reais
# aparecem com dígito faltando. Doze dígitos ou mais não colidem com telefone.
_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-?\d{2}\b|\b\d{12,14}\b")

# Exige pontuação: onze dígitos seguidos são ambíguos com celular e DDD, e nesse
# caso viram <TELEFONE> (continuam anonimizados, só com o marcador errado).
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-?\d{2}\b|\b\d{9}-\d{2}\b")

_VALOR = re.compile(r"(?:R\$\s*\d[\d.,]*|\b\d[\d.,]*\s*reais\b)", re.IGNORECASE)

# Roda antes do CNPJ e do telefone: rastreio e pedido também têm doze ou treze
# dígitos ("Envio padrão: 3320077642132", "pedido nº2418820753121") e cairiam na
# regra de CNPJ ou de celular. Só aceita "nº" e "n°", porque "no" é preposição
# ("fale no 3333-4444"). O vão de até seis palavras minúsculas cobre o que as
# notificações reais escrevem: "código de uso único é: 893530" e "código de
# verificação temporário para continuar: 274096". Minúsculas só, para não engolir
# um nome próprio no meio. Exige quatro dígitos: código de verificação tem de
# quatro a oito, e com menos o vão largo pegaria número curto de texto comum
# ("válido por 5 minutos").
_CODIGO = re.compile(
    r"((?i:pedidos?(?:\(s\))?|protocolo|c[óo]digo|rastre(?:io|amento)|envio|n\.?[º°]))"
    r"((?:\s+[a-zà-ÿ]{1,12}){0,6}[\s:.-]*)"
    # O prefixo de letras cobre o rastreio dos Correios, do tipo BR123456789BR.
    r"([A-Za-z]{0,3}\d{4}[\w.\-/]*)"
)

# Código de pedido de loja vem com cerquilha: "PAGAMENTO APROVADO #260816G0DEDR81".
_CODIGO_COM_CERQUILHA = re.compile(r"#(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,}\b")

# O mesmo código reaparece sem cerquilha e sem palavra que o anuncie. Oito
# caracteres misturando letra e número: nenhuma palavra comum tem esse formato.
_CODIGO_MISTO = re.compile(r"\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{8,}\b")

# A alternativa de dez ou onze dígitos seguidos existe para não deixar número
# nenhum em claro; o custo é marcar como telefone algum código numérico longo.
_TELEFONE = re.compile(
    r"(?:\b0800[\s.-]?\d{3}[\s.-]?\d{4}\b"
    r"|\+?55[\s.-]?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}\b"
    r"|\b\d{10,11}\b"
    r"|(?:\(\d{2}\)|\b\d{2})[\s.-]\s*9?\d{4}[\s.-]?\d{4}\b"
    r"|\b9?\d{4}[\s.-]\d{4}\b)"
)

# Só as formas com pontuação, DDD entre parênteses, 0800 ou +55: são as que dão
# para reconhecer como telefone sem ambiguidade, mesmo depois de "código".
_TELEFONE_FORMATADO = re.compile(
    r"(?:0800[\s.-]?\d{3}[\s.-]?\d{4}"
    r"|\+?55[\s.-]?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}"
    r"|\(\d{2}\)[\s.-]?\s*9?\d{4}[\s.-]?\d{4}"
    r"|\d{2}[\s.-]\s*9?\d{4}[\s.-]?\d{4}"
    r"|9?\d{4}[\s.-]\d{4})"
)

# Regra deliberadamente estreita: só o nome logo depois de uma saudação ou pronome
# de tratamento. Nome no meio da frase ou sem maiúscula não é detectado.
_NOME = re.compile(
    r"((?i:ol[áa]|oi|bom dia|boa tarde|boa noite|prezad[oa]s?|car[oa]s?"
    r"|sr\.?|sra\.?|senhora?|dona|dr\.?|dra\.?))"
    r"([,:]?\s+)"
    r"([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+)*)"
)

# Tratamento genérico no lugar do nome ("Oi Mãe", "Prezado Cliente") é sinal de
# golpe: quem conhece a pessoa usa o nome dela. Por isso essas palavras ficam.
_NOT_A_NAME = frozenset(
    {
        "mae",
        "pai",
        "filho",
        "filha",
        "vo",
        "tio",
        "tia",
        "cliente",
        "associado",
        "associada",
        "cooperado",
        "cooperada",
        "usuario",
        "usuaria",
        "senhor",
        "senhora",
        "amigo",
        "amiga",
        "querido",
        "querida",
        "tudo",
    }
)

# Marca imitada no lugar do nome é sinal de golpe, então o nome da instituição
# fica no texto. "INSS" e "Detran" em maiúsculas nem chegam aqui: a regra de nome
# exige inicial maiúscula seguida de minúsculas.
_INSTITUTIONS = frozenset(
    {
        "sicredi",
        "itau",
        "bradesco",
        "santander",
        "caixa",
        "banco do brasil",
        "nubank",
        "inter",
        "correios",
        "mercado livre",
        "shopee",
        "amazon",
        "serasa",
        "receita federal",
        "inss",
        "detran",
    }
)

_MAX_INSTITUTION_WORDS = 3

_MARKER = re.compile("|".join(marker.lower() for marker in MARKERS))

_WHITESPACE = re.compile(r"\s+")


def _replace_link(match: re.Match[str]) -> str:
    # A pontuação no fim da frase não faz parte do endereço: "acesse site.com/x," .
    link = match.group(0)
    sem_pontuacao = link.rstrip(".,;:!?)]}")
    return "<LINK>" + link[len(sem_pontuacao) :]


def _replace_value(match: re.Match[str]) -> str:
    # "R$ 450. E o melhor": o ponto encerra a frase, não faz parte da quantia.
    valor = match.group(0)
    sem_pontuacao = valor.rstrip(".,;:!?")
    return "<VALOR>" + valor[len(sem_pontuacao) :]


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _lookup_key(text: str) -> str:
    return _strip_accents(text).lower()


def _count_not_names(words: list[str]) -> int:
    """Quantas palavras do começo são tratamento genérico ou nome de instituição."""
    index = 0
    while index < len(words):
        for size in range(min(_MAX_INSTITUTION_WORDS, len(words) - index), 0, -1):
            if _lookup_key(" ".join(words[index : index + size])) in _INSTITUTIONS:
                index += size
                break
        else:
            if _lookup_key(words[index]) not in _NOT_A_NAME:
                break
            index += 1
    return index


def _replace_name(match: re.Match[str]) -> str:
    greeting, separator, name = match.group(1), match.group(2), match.group(3)
    words = name.split()
    kept = _count_not_names(words)
    if kept == len(words):
        return match.group(0)
    # "Prezado Cliente João" guarda o tratamento genérico e anonimiza o resto.
    prefix = " ".join(words[:kept])
    return f"{greeting}{separator}{prefix} <NOME>" if prefix else f"{greeting}{separator}<NOME>"


def _replace_code(match: re.Match[str]) -> str:
    keyword, gap, number = match.group(1), match.group(2), match.group(3)
    telefone = _TELEFONE_FORMATADO.match(match.string, match.start(3))
    # "código que enviamos para 11 98765-4321": o número começa como código, mas o
    # trecho inteiro é um telefone. Deixa passar para a regra de telefone.
    if telefone and telefone.end() - match.start(3) >= len(number):
        return match.group(0)
    return f"{keyword}{gap}<CODIGO>"


def anonymize(text: str) -> str:
    """Troca telefones, e-mails, nomes, documentos, valores, links e códigos pelos marcadores."""
    text = _EMAIL.sub("<EMAIL>", text)
    text = _LINK.sub(_replace_link, text)
    # Valor antes de código: o "R$" protege a quantia de "envio de R$ 19,90".
    text = _VALOR.sub(_replace_value, text)
    text = _CODIGO_COM_CERQUILHA.sub("<CODIGO>", text)
    text = _CODIGO.sub(_replace_code, text)
    text = _CODIGO_MISTO.sub("<CODIGO>", text)
    text = _CNPJ.sub("<CNPJ>", text)
    text = _CPF.sub("<CPF>", text)
    text = _TELEFONE.sub("<TELEFONE>", text)
    return _NOME.sub(_replace_name, text)


def normalize_text(text: str) -> str:
    """Deixa o texto em minúsculas, sem acentos e com um espaço entre palavras."""
    lowered = _strip_accents(text).lower()
    # Os marcadores voltam para maiúsculas para não virarem palavras comuns no TF-IDF.
    with_markers = _MARKER.sub(lambda match: match.group(0).upper(), lowered)
    return _WHITESPACE.sub(" ", with_markers).strip()


def drop_duplicate_messages(messages: pd.DataFrame, text_column: str = "texto") -> pd.DataFrame:
    """Remove mensagens repetidas, comparando o texto já normalizado."""
    normalized = messages[text_column].map(normalize_text)
    return messages[~normalized.duplicated()].copy()
