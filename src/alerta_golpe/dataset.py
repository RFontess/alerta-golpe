"""Carrega a base completa: o CSV do repositório mais os golpes dos datasets externos.

O CSV já vem anonimizado. Os golpes externos são baixados na hora e anonimizados
aqui, porque o texto deles não pode ser versionado.
"""

import pandas as pd

from alerta_golpe.paths import DATA_DIR
from alerta_golpe.preprocessing import anonymize, drop_duplicate_messages
from alerta_golpe.sources import download, load_scam_messages

RAW_PATH = DATA_DIR / "raw/mensagens.csv"

COLUMNS = ["id", "texto", "rotulo", "categoria", "grupo", "origem", "fonte", "data_coleta"]


def load_messages(include_external: bool = True) -> pd.DataFrame:
    """Base de mensagens pronta para análise e treino."""
    messages = pd.read_csv(RAW_PATH)
    if not include_external:
        return messages

    download()
    external = load_scam_messages()
    external = pd.DataFrame(
        {
            "id": [f"e{i:04d}" for i in range(1, len(external) + 1)],
            "texto": external["texto"].map(anonymize),
            "rotulo": "golpe",
            "categoria": external["categoria"],
            "grupo": external["grupo"],
            "origem": "real",
            "fonte": external["fonte"],
            "data_coleta": "2026-10-11",
        }
    )
    todas = pd.concat([messages, external[COLUMNS]], ignore_index=True)
    return drop_duplicate_messages(todas).reset_index(drop=True)
