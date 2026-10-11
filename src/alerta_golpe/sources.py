"""Golpes reais vindos dos datasets FraudTelegram.Br e FraudWhatsApp.Br.

Os datasets são do trabalho de Filho et al. (SBSeg 2023) e o repositório deles não
declara licença, então o texto nunca entra neste repositório: ele é baixado para
`data/external/`, que está no .gitignore, e o mesmo download roda no deploy.

O que fica versionado é a regra de seleção abaixo: só golpe financeiro dirigido a
uma pessoa. A classe de fraude dos datasets também tem propaganda de bot, venda de
documento e spam de investimento em cripto, que são outro gênero e ficam de fora.
As mensagens "não fraude" não servem como legítimas: são conversa de grupo político.
"""

import re
import urllib.request
from pathlib import Path

import pandas as pd

REPOSITORY = "https://github.com/jmmfilho/sec-fraudimabr"
CITATION = (
    "Filho, J. M. M. et al. FraudTelegram.Br e FraudWhatsApp.Br: datasets de fraude "
    "em aplicativos de mensageria instantânea. SBSeg 2023."
)

# Commit fixo: o conteúdo precisa ser o mesmo em qualquer execução.
_COMMIT = "35760f9a83f25676a04f4e0ab9bc4aa5649a7fe4"
_RAW = f"https://raw.githubusercontent.com/jmmfilho/sec-fraudimabr/{_COMMIT}/data"

_FILES = {
    "telegram": "dataset_rotulado_telegram.csv",
    "whatsapp": "df_rotulado_whatsapp.csv",
}

EXTERNAL_DIR = Path("data/external")

# Cada modelo de mensagem é um grupo: as variações só mudam o link ou o valor, então
# a divisão entre treino e teste tem que manter o grupo inteiro de um lado só.
_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    ("auxilio-brasil-pix", "phishing", r"aux[íi]lio brasil.{0,200}saque via pix"),
    ("registrato-valores-a-receber", "phishing", r"registrato.{0,120}valor a receber"),
    ("premio-pix-dia-das-criancas", "phishing", r"ganhe agora.{0,40}no pix"),
    ("nubank-oferece-no-aplicativo", "anuncio falso", r"est[áa] oferecendo at[ée] r\$"),
    (
        "boleto-com-desconto",
        "boleto falso",
        r"pagamentos? dos seguintes boletos|pagamos qualquer tipo de boleto",
    ),
    ("limpa-nome-aumenta-score", "anuncio falso", r"limpar seu nome|aumento score"),
    (
        "emprestimo-para-negativado",
        "anuncio falso",
        r"empr[ée]stimo.{0,80}negativad|negativad.{0,80}empr[ée]stimo",
    ),
    ("esquema-pix-multiplica-valor", "pix", r"esquema pix de \d+"),
    ("pix-online-transferencia", "pix", r"pix on-?line"),
    ("consorcio-contemplado", "anuncio falso", r"contemplad[oa].{0,40}(?:auto|im[óo]vel)"),
    ("antecipacao-de-saldo", "anuncio falso", r"antecipa[çc][ãa]o \d+% do saldo"),
    ("ganhe-por-dia-trabalhando-em-casa", "engenharia social", r"ganhar \d+ reais por dia"),
)


def download(destination: Path = EXTERNAL_DIR) -> None:
    """Baixa os datasets de fraude da fonte original para uma pasta fora do Git."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in _FILES.values():
        target = destination / name
        if not target.exists():
            urllib.request.urlretrieve(f"{_RAW}/{name}", target)


def _read_fraud_rows(destination: Path) -> pd.DataFrame:
    frames = []
    for dataset, name in _FILES.items():
        raw = pd.read_csv(destination / name)
        fraud = raw.loc[raw["Golpe"] == 1, ["text_content"]]
        frames.append(fraud.assign(dataset=dataset))
    rows = pd.concat(frames, ignore_index=True)
    return rows.rename(columns={"text_content": "texto"}).astype({"texto": "string"})


def _match_template(texto: str) -> tuple[str, str] | None:
    plain = re.sub(r"\s+", " ", texto)
    for grupo, categoria, pattern in _TEMPLATES:
        if re.search(pattern, plain, re.IGNORECASE):
            return grupo, categoria
    return None


def load_scam_messages(destination: Path = EXTERNAL_DIR) -> pd.DataFrame:
    """Golpes financeiros selecionados, com a categoria e o grupo de cada um."""
    rows = _read_fraud_rows(destination)
    matches = rows["texto"].map(_match_template)
    selected = rows[matches.notna()].copy()
    selected[["grupo", "categoria"]] = pd.DataFrame(
        matches[matches.notna()].tolist(), index=selected.index
    )
    selected["fonte"] = REPOSITORY
    return selected.reset_index(drop=True)


def main() -> None:
    download()
    scams = load_scam_messages()
    print(f"golpes selecionados: {len(scams)}")
    print(scams.groupby(["grupo", "categoria"]).size().to_string())


if __name__ == "__main__":
    main()
