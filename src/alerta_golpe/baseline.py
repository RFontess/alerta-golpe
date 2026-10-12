"""Baseline por palavras-chave, para ter com o que comparar o classificador.

Conta quantos sinais diferentes a mensagem dispara e chama de golpe a partir de dois.
Os sinais vieram da análise exploratória, que mediu a presença de cada um nas duas
classes (`notebooks/01_analise_exploratoria.ipynb`).

Ficaram **fora** de propósito:

- `<CODIGO>`: aparece em 9% dos golpes e 11% das legítimas. Código de verificação
  legítimo é comum, e é justamente o que o golpista pede para a vítima repassar.
- emoji: separa as classes na base (49% contra 5%), mas é artefato de uma fonte. Está
  em 70% dos anúncios de grupo de Telegram e em 0% dos golpes que chegam por SMS,
  que é o caso de uso do app.
- tamanho do texto: diferença pequena entre as mensagens reais e contaminada pelas
  sintéticas, que são conversas curtas.
- tratamento genérico ("Prezado Cliente"): medido e **invertido**. Dispara em 2% dos
  golpes e 12% das legítimas, porque e-mail corporativo legítimo trata o cliente
  assim e os golpes de SMS nem saúdam. Como sinal de golpe, empurraria para o lado
  errado. A anonimização continua preservando essas palavras, que é outra questão.
"""

import re

from alerta_golpe.preprocessing import normalize_text

# Os padrões rodam sobre o texto normalizado: sem acento e com os marcadores em
# maiúsculas, então nada aqui leva acento.
SIGNALS: tuple[tuple[str, str], ...] = (
    (
        "urgencia",
        r"urgente|imediat|agora|hoje|ultimo aviso|prazo|vence|nao perca|limitad"
        r"|24 horas|ainda hoje|em breve",
    ),
    # "bloque" e não "bloquei": o radical com i só pegava "bloqueio" e "bloqueie", e
    # deixava passar "bloqueada", que é como o SMS de golpe costuma escrever.
    ("ameaca", r"bloque|suspens|cancelad|irregular|pendencia|divida|judicial|restricao|evite"),
    ("link", r"<LINK>"),
    ("valor", r"<VALOR>"),
    ("pix", r"\bpix\b"),
    (
        "pedido de dados",
        r"atualiz\w* (?:seus|os) dados|confirm\w* (?:seus|os) dados|recadastr"
        r"|valid\w* (?:seus|os) dados|informe (?:seu|o) cpf|clique (?:no|aqui)|acesse o link",
    ),
    (
        "beneficio ou premio",
        r"auxilio|beneficio|premio|sorteio|indenizacao|valores? a receber|saque|contemplad"
        r"|restitui|ganhe",
    ),
    ("credito para negativado", r"negativad|limpa nome|aumentar? score|emprestimo|consignado"),
)

_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in SIGNALS)

THRESHOLD = 2


def signals(texto: str) -> list[str]:
    """Nomes dos sinais que a mensagem dispara."""
    normalizado = normalize_text(texto)
    return [name for name, pattern in _COMPILED if pattern.search(normalizado)]


def score(texto: str) -> int:
    """Quantos sinais diferentes a mensagem dispara."""
    return len(signals(texto))


def predict(texto: str, threshold: int = THRESHOLD) -> str:
    return "golpe" if score(texto) >= threshold else "legitima"
