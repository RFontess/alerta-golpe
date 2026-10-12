"""Registro das verificações em SQLite, para medir o protótipo em uso.

O texto da mensagem nunca é gravado. A tabela guarda o hash SHA-256 do texto já
anonimizado, que serve para contar mensagem repetida sem permitir ler o conteúdo: é
hash de uma via só, e o que entra nele já saiu sem telefone, nome, valor nem link.

O feedback é "era golpe" ou "não era golpe", e não "acertou" ou "errou": no nível médio
o app não afirma nada, então perguntar se acertou não teria resposta certa. Assim a
resposta serve para os três níveis.

O vocabulário gravado é sem acento, igual ao dos sinais do baseline. Quem mostra na tela
é que acentua.
"""

import hashlib
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

from alerta_golpe.paths import DATA_DIR

DB_PATH = DATA_DIR / "monitoramento.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS verificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TEXT NOT NULL,
    hash_mensagem TEXT NOT NULL,
    nivel TEXT NOT NULL,
    sinais TEXT NOT NULL,
    exemplo INTEGER NOT NULL,
    resposta TEXT
)
"""

FEEDBACK = {"era golpe", "nao era golpe"}


def message_hash(anonymized: str) -> str:
    return hashlib.sha256(anonymized.encode("utf-8")).hexdigest()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Abre o banco, criando o arquivo e a tabela se ainda não existirem.

    Quem chama precisa fechar a conexão: o `with` do sqlite3 encerra a transação, não a
    conexão. Aqui dentro todo uso passa por `contextlib.closing`.
    """
    # Resolvido na chamada, e não no valor padrão, para o teste poder trocar `DB_PATH`.
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(db_path)
    with conexao:
        conexao.execute(SCHEMA)
    return conexao


def record(
    anonymized: str,
    level: str,
    signals: list[str],
    from_example: bool,
    db_path: Path | None = None,
) -> int:
    """Grava uma verificação e devolve o id da linha, para o feedback encontrá-la."""
    with closing(connect(db_path)) as conexao, conexao:
        cursor = conexao.execute(
            "INSERT INTO verificacoes"
            " (data_hora, hash_mensagem, nivel, sinais, exemplo, resposta)"
            " VALUES (?, ?, ?, ?, ?, NULL)",
            (
                datetime.now(UTC).isoformat(timespec="seconds"),
                message_hash(anonymized),
                level,
                ",".join(signals),
                int(from_example),
            ),
        )
        return int(cursor.lastrowid)


def answer(check_id: int, resposta: str, db_path: Path | None = None) -> None:
    if resposta not in FEEDBACK:
        raise ValueError(f"resposta deve ser uma de {sorted(FEEDBACK)}")
    with closing(connect(db_path)) as conexao, conexao:
        conexao.execute("UPDATE verificacoes SET resposta = ? WHERE id = ?", (resposta, check_id))


def history(db_path: Path | None = None) -> pd.DataFrame:
    with closing(connect(db_path)) as conexao:
        return pd.read_sql_query("SELECT * FROM verificacoes ORDER BY id", conexao)


def history_excel(db_path: Path | None = None) -> bytes:
    """Histórico em Excel, para o botão de download do app."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer) as excel:
        history(db_path).to_excel(excel, sheet_name="verificacoes", index=False)
    return buffer.getvalue()


def summary(db_path: Path | None = None) -> dict:
    """Contagens da página de monitoramento, com os exemplos separados."""
    historico = history(db_path)
    sinais: dict[str, int] = {}
    for linha in historico["sinais"]:
        for nome in filter(None, linha.split(",")):
            sinais[nome] = sinais.get(nome, 0) + 1
    com_resposta = historico[historico["resposta"].notna()]
    return {
        "verificacoes": int(len(historico)),
        "mensagens_coladas": int((historico["exemplo"] == 0).sum()),
        "exemplos": int((historico["exemplo"] == 1).sum()),
        "por_nivel": historico["nivel"].value_counts().to_dict(),
        "por_sinal": dict(sorted(sinais.items(), key=lambda par: -par[1])),
        "respostas_por_nivel": {
            nivel: bloco["resposta"].value_counts().to_dict()
            for nivel, bloco in com_resposta.groupby("nivel")
        },
    }
