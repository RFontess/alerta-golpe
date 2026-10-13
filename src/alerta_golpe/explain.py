"""Explicação do alerta, feita pelo mesmo sistema que decide.

O app mostra os sinais do baseline que dispararam, porque é o baseline que decide
(`reports/metricas.json`, chave `escolha_do_app`). Os termos do classificador TF-IDF
ficam fora: explicar por um sistema e decidir por outro confundiria quem lê.

A explicação anonimiza o texto antes de contar os sinais. Na avaliação as mensagens já
chegavam anonimizadas, porque o CSV é salvo assim; no app a pessoa cola o texto cru, e
sem anonimizar os sinais "link" e "valor" nunca apareceriam.

As palavras-chave de categoria servem só para escolher a dica. Elas não entram na
decisão, que continua sendo a contagem de sinais do baseline.

O tom dos textos vem do erro medido: a regra deixou passar 6 dos 57 golpes e alertou em
10 das 42 legítimas. Então nenhuma orientação afirma que a mensagem é golpe ou que é
segura, e todas terminam em algo que a pessoa pode fazer: confirmar por outro caminho.

Os textos da tela dizem "link", nunca "endereço": para muita gente idosa, endereço é o
de casa.
"""

import re
from dataclasses import dataclass

from alerta_golpe.baseline import SIGNALS, THRESHOLD
from alerta_golpe.baseline import signals as baseline_signals
from alerta_golpe.preprocessing import anonymize, normalize_text

SIGNAL_PHRASES: dict[str, str] = {
    "urgencia": "A mensagem apressa você.",
    "ameaca": "A mensagem fala de um problema, como bloqueio, dívida ou cancelamento.",
    "link": "A mensagem traz um link para você abrir.",
    "valor": "A mensagem fala de dinheiro.",
    "pix": "A mensagem envolve um Pix.",
    "pedido de dados": "A mensagem pede seus dados ou pede para você clicar.",
    "beneficio ou premio": "A mensagem promete dinheiro ou vantagem.",
    "credito para negativado": "A mensagem fala de empréstimo, crédito ou de limpar o nome.",
}

# Os marcadores da anonimização não são palavras que a pessoa escreveu, então viram
# texto comum na explicação.
MARKER_WORDS: dict[str, str] = {
    "<LINK>": "um link",
    "<VALOR>": "um valor em dinheiro",
}

LEVEL_TITLES: dict[str, str] = {
    "alto": "Cuidado: esta mensagem parece golpe",
    "medio": "Atenção: um ponto para conferir",
    "baixo": "Não encontramos sinais comuns de golpe",
}

LEVEL_MESSAGES: dict[str, str] = {
    "alto": (
        "Não clique em nada, não pague e não responda por ela. Confirme pelo aplicativo "
        "do banco ou pelo número oficial."
    ),
    "medio": (
        "Esse ponto também aparece em mensagens normais. Se a mensagem pedir dinheiro, "
        "dados ou algum código, confirme pelo aplicativo do banco ou pelo número oficial "
        "antes."
    ),
    "baixo": "Isso não garante que a mensagem seja segura.",
}

GENERAL_TIP = (
    "Na dúvida, não clique, não pague e não passe nenhum código. Confirme por outro "
    "caminho: ligue para o banco pelo número oficial ou para a pessoa no número que "
    "você já conhece."
)

RULE_TEXT = (
    "O Alerta Golpe procura oito sinais na mensagem. Quando encontra dois ou mais, "
    "mostra o aviso vermelho; com um só, mostra o aviso amarelo; sem nenhum, diz que "
    "não encontrou sinal. Não há conta de probabilidade: é só a contagem de sinais."
)

ANONYMIZATION_NOTE = (
    "Antes de procurar os sinais, o Alerta Golpe troca por etiquetas os dados que "
    "reconhece: telefone, e-mail, documento, valor, link, código e alguns nomes. É esta "
    "versão da sua mensagem que ele leu:"
)

FALLBACK_CATEGORY = "engenharia social"

# A primeira que bater escolhe a dica. A ordem segue o que caracteriza o golpe, não o
# que ele menciona de passagem: quem se faz passar por alguém conhecido vem primeiro,
# depois o link falso, e só no fim Pix e site, que quase todo golpe cita como meio.
CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("whatsapp", r"troquei de numero|numero novo|novo numero|celular novo|whatsapp|zap"),
    ("boleto falso", r"boleto|codigo de barras|segunda via|linha digitavel"),
    (
        "falsa central",
        r"central de atendimento|central de seguranc|funcionari|atendente|gerente"
        r"|ouvidoria|ligue (?:para|agora|ja)|retorne a ligacao",
    ),
    (
        "phishing",
        r"<LINK>|clique|acesse|atualiz|recadastr|confirme seus dados|senha"
        r"|codigo de seguranca",
    ),
    (
        "anuncio falso",
        r"promoca|oferta|desconto|frete gratis|ganhe|renda extra|trabalhe em casa"
        r"|investimento|lucro|sorteio|premio|vagas limitadas",
    ),
    ("cartao", r"cartao|anuidade|compra nao reconhecida|limite liberado"),
    ("site falso", r"\bsite\b|portal|loja virtual|pagina oficial"),
    ("pix", r"\bpix\b|qr code|chave de transferencia"),
)

CATEGORY_TIPS: dict[str, str] = {
    "whatsapp": (
        "Ligue para a pessoa no número antigo, que você já tem. Não envie dinheiro antes "
        "de falar com ela por esse número."
    ),
    "boleto falso": (
        "Não pague o boleto que veio na mensagem. Pegue a segunda via no aplicativo da empresa."
    ),
    "cartao": (
        "Não passe o número do seu cartão por mensagem. Ligue para o número que está "
        "escrito no cartão."
    ),
    "falsa central": (
        "Não ligue para o número da mensagem. Ligue você mesmo para o número oficial do "
        "banco, que está no cartão. Ninguém do banco pede sua senha ou seu código."
    ),
    "pix": (
        "Não faça o Pix agora. Ligue para a pessoa ou para a empresa no número que você "
        "já tem e confirme."
    ),
    "phishing": (
        "Não abra o link da mensagem. Entre no aplicativo do banco ou da loja pelo ícone "
        "do seu celular."
    ),
    "site falso": (
        "Não abra o link da mensagem. Use o aplicativo da empresa que você já tem no celular."
    ),
    "anuncio falso": (
        "Não pague por uma oferta que chegou por mensagem. Procure o produto na loja que "
        "você já conhece."
    ),
    FALLBACK_CATEGORY: (
        "Antes de responder, fale com alguém de confiança. Não passe dados nem dinheiro "
        "por mensagem."
    ),
}

_SIGNAL_PATTERNS = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in SIGNALS}

_COMPILED_CATEGORIES = tuple(
    (name, re.compile(pattern, re.IGNORECASE)) for name, pattern in CATEGORY_KEYWORDS
)

_WORD = re.compile(r"\S+")

_EDGE_PUNCTUATION = ".,;:!?\"'()[]{}*…"


@dataclass(frozen=True)
class Signal:
    """Um sinal que disparou, com a frase para a pessoa e os trechos que o acionaram."""

    name: str
    phrase: str
    excerpts: list[str]


@dataclass(frozen=True)
class Explanation:
    level: str
    title: str
    message: str
    signals: list[Signal]
    category: str
    category_tip: str
    general_tip: str
    anonymized: str


def _normalized_tokens(text: str) -> tuple[str, list[tuple[int, int, int, int]]]:
    """Texto normalizado e, para cada palavra, onde ela está no original e no normalizado.

    Normalizar palavra por palavra dá o mesmo resultado que normalizar o texto inteiro, e
    guarda a posição de cada palavra nos dois: é assim que a explicação mostra "cancelada"
    onde a regra casou só com o radical "cancelad".
    """
    tokens: list[tuple[int, int, int, int]] = []
    pieces: list[str] = []
    position = 0
    for match in _WORD.finditer(text):
        normalized = normalize_text(match.group(0))
        if not normalized:
            continue
        tokens.append((match.start(), match.end(), position, position + len(normalized)))
        pieces.append(normalized)
        position += len(normalized) + 1
    return " ".join(pieces), tokens


def _excerpts_for(
    pattern: re.Pattern[str],
    texto: str,
    normalized: str,
    tokens: list[tuple[int, int, int, int]],
) -> list[str]:
    """Os trechos do texto que a regra casou, inteiros e sem repetir.

    Cada disparo da regra vira um trecho só, recortado do texto como a pessoa escreveu: a
    regra de pedido de dados mostra "Atualize seus dados", e não três palavras soltas. A
    vírgula entre trechos é da tela, não de dentro da frase.
    """
    found: list[str] = []
    for match in pattern.finditer(normalized):
        cobertos = [
            token for token in tokens if token[2] < match.end() and match.start() < token[3]
        ]
        if not cobertos:
            continue
        trecho = texto[cobertos[0][0] : cobertos[-1][1]].strip(_EDGE_PUNCTUATION)
        trecho = MARKER_WORDS.get(trecho, trecho)
        if trecho and trecho not in found:
            found.append(trecho)
    return found


def category(texto: str) -> str:
    """Categoria mais provável, por palavras-chave, só para escolher a dica."""
    normalizado = normalize_text(texto)
    for name, pattern in _COMPILED_CATEGORIES:
        if pattern.search(normalizado):
            return name
    return FALLBACK_CATEGORY


def level(signal_count: int) -> str:
    if signal_count >= THRESHOLD:
        return "alto"
    return "medio" if signal_count else "baixo"


def explain(texto: str) -> Explanation:
    """Nível, sinais que dispararam e dica para o texto como a pessoa colou."""
    anonimizado = anonymize(texto)
    normalizado, tokens = _normalized_tokens(anonimizado)
    disparados = [
        Signal(
            name,
            SIGNAL_PHRASES[name],
            _excerpts_for(_SIGNAL_PATTERNS[name], anonimizado, normalizado, tokens),
        )
        for name in baseline_signals(anonimizado)
    ]
    nivel = level(len(disparados))
    escolhida = category(anonimizado)
    return Explanation(
        level=nivel,
        title=LEVEL_TITLES[nivel],
        message=LEVEL_MESSAGES[nivel],
        signals=disparados,
        category=escolhida,
        category_tip=CATEGORY_TIPS[escolhida],
        general_tip=GENERAL_TIP,
        anonymized=anonimizado,
    )
