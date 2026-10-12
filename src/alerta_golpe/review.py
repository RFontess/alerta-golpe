"""Relatório de revisão das mensagens privadas antes de entrarem no repositório.

Lê `data/private/mensagens_email.csv`, anonimiza e escreve um relatório lado a lado,
original contra anonimizado, mais o que a auditoria achou de suspeito. O relatório
fica em `data/private/`, que está no .gitignore: ele contém o texto original.

Uso: python -m alerta_golpe.review
"""

import re

import pandas as pd

from alerta_golpe.paths import DATA_DIR
from alerta_golpe.preprocessing import anonymize

PRIVATE_DIR = DATA_DIR / "private"

# O que não deveria sobrar depois da anonimização.
_SUSPECTS = {
    "link": r"https?://|www\.|\b[\w-]+\.(?:com|br|net|org|online|site|me|co|ly|is|info)\b",
    "e-mail": r"@[\w-]+\.",
    # Sete dígitos seguidos. Data (26/07/2026) e milhar (25.000) não entram: têm
    # separador no meio e não são identificador de pessoa.
    "número longo": r"\b[A-Za-z]{0,3}\d{7,}[A-Za-z]{0,3}\b",
    "CPF ou CNPJ": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
}

# Legítimas que imitam o formato do golpe: o rótulo é de propósito e precisa de
# conferência explícita, porque é nelas que o modelo tende a errar.
_LOOKS_LIKE_SCAM = r"golpe|fraude|bloquei|suspeit|n[ãa]o reconhec|n[ãa]o autoriz|verifica"


def find_suspects(texto: str) -> list[str]:
    """Trechos que ainda parecem dado pessoal depois da anonimização."""
    found = []
    for name, pattern in _SUSPECTS.items():
        found += [f"{name}: {m.group(0)!r}" for m in re.finditer(pattern, texto, re.IGNORECASE)]
    return found


def build_report(messages: pd.DataFrame) -> str:
    anonymized = messages["texto"].map(anonymize)
    suspects = anonymized.map(find_suspects)
    situations = messages["situacao"].nunique()

    lines = [
        "# Revisão das mensagens do e-mail",
        "",
        f"{len(messages)} mensagens em {situations} situações. "
        f"{int(suspects.map(bool).sum())} com suspeita de dado pessoal remanescente.",
        "",
        "Confira cada par. O que entra no repositório é só a linha `anonimizado`.",
        "",
    ]
    for position, (_, row) in enumerate(messages.iterrows(), start=1):
        texto_anon = anonymized.iloc[position - 1]
        achados = suspects.iloc[position - 1]
        lines += [
            f"## {position}. {row['situacao']}",
            "",
            f"- rótulo: `{row['rotulo']}` | categoria: `{row['categoria']}`",
            f"- original: {row['texto']}",
            f"- anonimizado: {texto_anon}",
        ]
        if achados:
            lines.append(f"- **SUSPEITA:** {'; '.join(achados)}")
        if re.search(_LOOKS_LIKE_SCAM, texto_anon, re.IGNORECASE):
            lines.append("- **CONFERIR:** legítima que parece golpe, rotulada assim de propósito")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    messages = pd.read_csv(PRIVATE_DIR / "mensagens_email.csv")
    report = PRIVATE_DIR / "relatorio_revisao.md"
    report.write_text(build_report(messages), encoding="utf-8")
    print(f"relatório em {report}")


if __name__ == "__main__":
    main()
