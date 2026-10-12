import sqlite3

import pytest

from alerta_golpe import monitoring

TEXTO = "Sua conta sera bloqueada hoje. Atualize seus dados em <LINK>"


@pytest.fixture
def db(tmp_path):
    return tmp_path / "monitoramento.db"


def test_cria_o_banco_se_nao_existir(db):
    assert not db.exists()
    monitoring.record(TEXTO, "alto", ["ameaca"], from_example=False, db_path=db)
    assert db.exists()


def test_grava_a_verificacao(db):
    check_id = monitoring.record(
        TEXTO, "alto", ["urgencia", "ameaca"], from_example=True, db_path=db
    )
    linha = monitoring.history(db).iloc[0]
    assert check_id == 1
    assert linha["nivel"] == "alto"
    assert linha["sinais"] == "urgencia,ameaca"
    assert linha["exemplo"] == 1
    assert linha["resposta"] is None
    assert linha["hash_mensagem"] == monitoring.message_hash(TEXTO)


def test_o_texto_nao_aparece_em_nenhuma_coluna(db):
    monitoring.record(TEXTO, "alto", ["ameaca"], from_example=False, db_path=db)
    historico = monitoring.history(db)
    tudo = " ".join(str(valor) for valor in historico.to_numpy().ravel())
    # O banco inteiro, e não só as colunas que o histórico devolve.
    with sqlite3.connect(db) as conexao:
        linhas = conexao.execute("SELECT * FROM verificacoes").fetchall()
    bruto = " ".join(str(valor) for linha in linhas for valor in linha)
    for trecho in ("bloqueada", "Atualize", "conta", "<LINK>"):
        assert trecho not in tudo
        assert trecho not in bruto


def test_a_resposta_atualiza_a_linha(db):
    check_id = monitoring.record(TEXTO, "medio", ["urgencia"], from_example=False, db_path=db)
    monitoring.answer(check_id, "era golpe", db_path=db)
    assert monitoring.history(db).iloc[0]["resposta"] == "era golpe"


def test_resposta_invalida_e_recusada(db):
    check_id = monitoring.record(TEXTO, "baixo", [], from_example=False, db_path=db)
    with pytest.raises(ValueError, match="resposta deve ser"):
        monitoring.answer(check_id, "acertou", db_path=db)


def test_resumo_separa_exemplo_de_mensagem_colada(db):
    monitoring.record(TEXTO, "alto", ["ameaca", "link"], from_example=True, db_path=db)
    segundo = monitoring.record(TEXTO, "medio", ["urgencia"], from_example=False, db_path=db)
    monitoring.record(TEXTO, "baixo", [], from_example=False, db_path=db)
    monitoring.answer(segundo, "nao era golpe", db_path=db)

    resumo = monitoring.summary(db)
    assert resumo["verificacoes"] == 3
    assert resumo["exemplos"] == 1
    assert resumo["mensagens_coladas"] == 2
    assert resumo["por_nivel"] == {"alto": 1, "medio": 1, "baixo": 1}
    assert resumo["por_sinal"] == {"ameaca": 1, "link": 1, "urgencia": 1}
    assert resumo["respostas_por_nivel"] == {"medio": {"nao era golpe": 1}}


def test_resumo_de_banco_vazio(db):
    resumo = monitoring.summary(db)
    assert resumo["verificacoes"] == 0
    assert resumo["por_sinal"] == {}
    assert resumo["respostas_por_nivel"] == {}


def test_exporta_o_historico_em_excel(db):
    monitoring.record(TEXTO, "alto", ["ameaca"], from_example=False, db_path=db)
    conteudo = monitoring.history_excel(db)
    assert conteudo.startswith(b"PK")
