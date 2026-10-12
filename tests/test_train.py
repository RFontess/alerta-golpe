import pandas as pd
import pytest

from alerta_golpe.train import (
    APP_THRESHOLD,
    THRESHOLDS,
    build_pipeline,
    drop_link_marker,
    evaluate,
    out_of_fold_predictions,
    recall_by_origin,
    threshold_table,
    unseen_types_recognized,
)


@pytest.fixture
def mensagens() -> pd.DataFrame:
    linhas = [
        ("g1", "golpe", "real", "https://www.boatos.org/a", "sua conta sera bloqueada <LINK>"),
        ("g1", "golpe", "real", "https://www.boatos.org/a", "conta bloqueada hoje <LINK>"),
        ("g2", "golpe", "real", "https://github.com/x", "faca o saque via pix <LINK> agora"),
        ("g3", "golpe", "real", "https://github.com/x", "emprestimo para negativado <VALOR>"),
        ("l1", "legitima", "real", "e-mail próprio", "sua fatura fechou e vence dia 21"),
        ("l2", "legitima", "real", "e-mail próprio", "seu pedido foi entregue ontem"),
        ("s1", "legitima", "sintetica", "exemplo sintetico", "oi mae, chego mais tarde"),
    ]
    base = pd.DataFrame(linhas, columns=["grupo", "rotulo", "origem", "fonte", "texto"])
    return base.assign(id=[f"t{i}" for i in range(len(base))], categoria="x", data_coleta="x")


def test_a_dobra_nunca_treina_com_o_grupo_que_testa(mensagens, monkeypatch):
    grupos_de_treino = []
    original = build_pipeline

    def espiao(drop_link=False):
        pipeline = original(drop_link)
        ajustar = pipeline.fit

        def fit(X, y):
            grupos_de_treino.append(set(mensagens.loc[X.index, "grupo"]))
            return ajustar(X, y)

        pipeline.fit = fit
        return pipeline

    monkeypatch.setattr("alerta_golpe.train.build_pipeline", espiao)
    oof = out_of_fold_predictions(mensagens)

    grupos_testados = sorted(mensagens[mensagens["origem"] == "real"]["grupo"].unique())
    assert len(grupos_de_treino) == len(grupos_testados)
    for grupo, treinados in zip(grupos_testados, grupos_de_treino, strict=True):
        assert grupo not in treinados
    assert len(oof) == int((mensagens["origem"] == "real").sum())


def test_sinteticas_entram_no_treino_mas_nao_no_teste(mensagens):
    oof = out_of_fold_predictions(mensagens)
    assert "sintetica" not in set(oof["origem"])


def test_cada_mensagem_real_recebe_uma_probabilidade(mensagens):
    oof = out_of_fold_predictions(mensagens)
    assert oof["proba"].between(0, 1).all()
    assert oof["proba"].notna().all()


def test_drop_link_tira_o_marcador():
    assert "<LINK>" not in drop_link_marker("acesse <LINK> agora")


def test_pipeline_sem_link_nao_cria_atributo_de_link(mensagens):
    pipeline = build_pipeline(drop_link=True).fit(mensagens["texto"], mensagens["rotulo"])
    atributos = set(pipeline.named_steps["tfidf"].get_feature_names_out())
    assert not any("LINK" in a for a in atributos)


def test_pipeline_normal_mantem_o_marcador_separado_da_palavra(mensagens):
    textos = pd.concat([mensagens["texto"], pd.Series(["veja o link no site"])])
    pipeline = build_pipeline().fit(textos, list(mensagens["rotulo"]) + ["legitima"])
    atributos = set(pipeline.named_steps["tfidf"].get_feature_names_out())
    assert "LINK" in atributos
    assert "link" in atributos


def test_contagens_somam_o_total():
    verdadeiro = pd.Series(["golpe", "golpe", "legitima", "legitima"])
    previsto = pd.Series(["golpe", "legitima", "golpe", "legitima"])
    resultado = evaluate(verdadeiro, previsto)
    contagens = resultado["contagens"]
    assert sum(contagens.values()) == resultado["mensagens"] == 4
    assert resultado["precisao"] == 0.5
    assert resultado["recall"] == 0.5


def test_recall_por_origem_separa_sms_de_anuncio_de_grupo(mensagens):
    oof = out_of_fold_predictions(mensagens)
    previsto = pd.Series(["golpe"] * len(oof), index=oof.index)
    por_origem = recall_by_origin(oof, previsto)
    assert por_origem["SMS e alertas"]["golpes"] == 2
    assert por_origem["anuncio de grupo"]["golpes"] == 2
    assert por_origem["SMS e alertas"]["reconhecidos"] == 2


def test_tipos_nao_vistos_conta_por_grupo(mensagens):
    oof = out_of_fold_predictions(mensagens)
    previsto = pd.Series(["golpe"] * len(oof), index=oof.index)
    tipos = unseen_types_recognized(oof, previsto)
    assert tipos["tipos"] == 3
    assert tipos["reconhecidos"] == 3
    assert tipos["nao_reconhecidos"] == []


def test_tabela_de_limiares_cobre_todos_os_limiares(mensagens):
    oof = out_of_fold_predictions(mensagens)
    tabela = threshold_table(oof)
    assert list(tabela["limiar"]) == list(THRESHOLDS)
    # Recall não pode subir quando o limiar sobe.
    assert tabela["recall"].is_monotonic_decreasing
    assert APP_THRESHOLD in set(tabela["limiar"])
