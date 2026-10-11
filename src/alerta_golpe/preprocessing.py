"""Limpeza e anonimização das mensagens.

A anonimização roda antes da normalização, porque a regra de nomes depende das
letras maiúsculas do texto original.
"""

import re
import unicodedata

import pandas as pd

MARKERS = ("<TELEFONE>", "<EMAIL>", "<NOME>", "<CPF>", "<VALOR>", "<LINK>")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Golpes costumam encurtar o link ou omitir o "http", por isso a lista de domínios.
_LINK = re.compile(
    r"(?:https?://\S+"
    r"|www\.\S+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|br|net|org|gov|info|xyz|top|link|site|app|io|me|co"
    r"|ly|gl|tk|cc|online|shop|store|digital|vip|click)(?:\.[a-z]{2})?(?:/\S*)?)",
    re.IGNORECASE,
)

# Exige pontuação: onze dígitos seguidos são ambíguos com celular e DDD, e nesse
# caso viram <TELEFONE> (continuam anonimizados, só com o marcador errado).
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-?\d{2}\b|\b\d{9}-\d{2}\b")

_VALOR = re.compile(r"(?:R\$\s*\d[\d.,]*|\b\d[\d.,]*\s*reais\b)", re.IGNORECASE)

# A alternativa de dez ou onze dígitos seguidos existe para não deixar número
# nenhum em claro; o custo é marcar como telefone algum código numérico longo.
_TELEFONE = re.compile(
    r"(?:\b0800[\s.-]?\d{3}[\s.-]?\d{4}\b"
    r"|\+?55[\s.-]?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}\b"
    r"|\b\d{10,11}\b"
    r"|(?:\(\d{2}\)|\b\d{2})[\s.-]\s*9?\d{4}[\s.-]?\d{4}\b"
    r"|\b9?\d{4}[\s.-]\d{4}\b)"
)

# Regra deliberadamente estreita: só o nome logo depois de uma saudação ou pronome
# de tratamento. Nome no meio da frase ou sem maiúscula não é detectado.
_NOME = re.compile(
    r"((?i:ol[áa]|oi|bom dia|boa tarde|boa noite|prezad[oa]s?|car[oa]s?"
    r"|sr\.?|sra\.?|senhora?|dona|dr\.?|dra\.?))"
    r"([,:]?\s+)"
    r"([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ]+)*)"
)

_MARKER = re.compile("|".join(marker.lower() for marker in MARKERS))

_WHITESPACE = re.compile(r"\s+")


def anonymize(text: str) -> str:
    """Troca telefones, e-mails, nomes, CPFs, valores e links pelos marcadores."""
    text = _EMAIL.sub("<EMAIL>", text)
    text = _LINK.sub("<LINK>", text)
    text = _CPF.sub("<CPF>", text)
    text = _VALOR.sub("<VALOR>", text)
    text = _TELEFONE.sub("<TELEFONE>", text)
    return _NOME.sub(r"\1\2<NOME>", text)


def normalize_text(text: str) -> str:
    """Deixa o texto em minúsculas, sem acentos e com um espaço entre palavras."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = without_accents.lower()
    # Os marcadores voltam para maiúsculas para não virarem palavras comuns no TF-IDF.
    with_markers = _MARKER.sub(lambda match: match.group(0).upper(), lowered)
    return _WHITESPACE.sub(" ", with_markers).strip()


def drop_duplicate_messages(messages: pd.DataFrame, text_column: str = "texto") -> pd.DataFrame:
    """Remove mensagens repetidas, comparando o texto já normalizado."""
    normalized = messages[text_column].map(normalize_text)
    return messages[~normalized.duplicated()].copy()
