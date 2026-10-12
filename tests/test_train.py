import pandas as pd
import pytest

from alerta_golpe.baseline import SIGNALS
from alerta_golpe.train import (
    APP_THRESHOLD,
    MAX_FALSE_POSITIVES,
    THRESHOLDS,
    build_hybrid_pipeline,
    build_pipeline,
    choose_for_app,
    drop_link_marker,
    evaluate,
    out_of_fold_predictions,
    recall_by_origin,
    signal_features,
    threshold_table,
    unseen_types_recognized,
)


def _candidato(nome, alarmes_falsos, golpes_de_sms, recall=0.5, f1=0.5):
    return {
        "configuracao": nome,
        "alarmes_falsos": alarmes_falsos,
        "golpes_de_sms": golpes_de_sms,
        "golpes_de_sms_total": 17,
        "recall": recall,
        "f1": f1,
    }


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


def test_sinais_do_baseline_viram_colunas_binarias():
    matriz = signal_features(["sua conta sera bloqueada hoje <LINK>", "oi, tudo bem?"])
    assert matriz.shape == (2, len(SIGNALS))
    assert set(matriz.flatten()) <= {0.0, 1.0}
    assert matriz[0].sum() > matriz[1].sum()


def test_hibrido_usa_tfidf_mais_os_sinais(mensagens):
    pipeline = build_hybrid_pipeline().fit(mensagens["texto"], mensagens["rotulo"])
    atributos = pipeline.named_steps["atributos"]
    n_tfidf = len(atributos.transformer_list[0][1].get_feature_names_out())
    assert atributos.transform(mensagens["texto"]).shape[1] == n_tfidf + len(SIGNALS)


def test_criterio_descarta_quem_passa_do_limite_de_alarme_falso():
    candidatos = [
        _candidato("pega tudo mas alarma", MAX_FALSE_POSITIVES + 1, 17),
        _candidato("comportada", 5, 10),
    ]
    escolha = choose_for_app(candidatos)
    assert escolha["escolhida"] == "comportada"
    assert escolha["fora_do_limite"] == ["pega tudo mas alarma"]


def test_criterio_prefere_mais_golpes_de_sms():
    candidatos = [_candidato("a", 9, 14), _candidato("b", 2, 5)]
    assert choose_for_app(candidatos)["escolhida"] == "a"


def test_criterio_desempata_por_recall_e_depois_f1():
    candidatos = [
        _candidato("recall menor", 3, 11, recall=0.70, f1=0.90),
        _candidato("recall maior", 3, 11, recall=0.80, f1=0.60),
    ]
    assert choose_for_app(candidatos)["escolhida"] == "recall maior"

    empatados = [
        _candidato("f1 menor", 3, 11, recall=0.80, f1=0.60),
        _candidato("f1 maior", 3, 11, recall=0.80, f1=0.70),
    ]
    assert choose_for_app(empatados)["escolhida"] == "f1 maior"


def test_sem_nenhuma_configuracao_elegivel_fica_o_baseline():
    candidatos = [_candidato("alarmista", MAX_FALSE_POSITIVES + 5, 17)]
    assert choose_for_app(candidatos)["escolhida"] == "baseline"


def test_tabela_de_limiares_cobre_todos_os_limiares(mensagens):
    oof = out_of_fold_predictions(mensagens)
    tabela = threshold_table(oof)
    assert list(tabela["limiar"]) == list(THRESHOLDS)
    # Recall não pode subir quando o limiar sobe.
    assert tabela["recall"].is_monotonic_decreasing
    assert APP_THRESHOLD in set(tabela["limiar"])
