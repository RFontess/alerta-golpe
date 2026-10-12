"""Treina e avalia o classificador, e grava as métricas em `reports/`.

Uso: python -m alerta_golpe.train

A avaliação é validação cruzada **leave-one-group-out**, só com mensagens reais no
teste. Cada grupo é um modelo de mensagem, e variação do mesmo modelo não é exemplo
independente: com divisão aleatória, as 20 variações de um golpe cairiam dos dois
lados e a métrica mediria memorização. As sintéticas do grupo testado também saem do
treino.

Três cuidados que o relatório registra:

- O baseline roda nas **mesmas dobras**, para a comparação ser lado a lado. Ainda
  assim ele é referência otimista: as regras e o limiar dele foram escolhidos olhando
  a base inteira.
- O limiar do app **não** é escolhido olhando o teste. As métricas principais saem com
  0,5, e a tabela de limiares é calculada sobre as previsões fora da dobra.
- Com 17 golpes de SMS, cada mensagem vale uns 6 pontos percentuais, então tudo
  aparece em contagem além da porcentagem.
"""

import json

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.pipeline import Pipeline

from alerta_golpe.baseline import THRESHOLD as BASELINE_THRESHOLD
from alerta_golpe.baseline import predict as baseline_predict
from alerta_golpe.dataset import load_messages
from alerta_golpe.paths import REPORTS_DIR
from alerta_golpe.preprocessing import normalize_text

POSITIVE = "golpe"
DEFAULT_THRESHOLD = 0.5
THRESHOLDS = (0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7)

# Limiar que o app usa, escolhido na tabela de limiares fora da dobra: é onde o F1
# é maior e o recall sobe de 36 para 45 golpes, custando 8 alarmes falsos a mais.
# Ressalva: foi escolhido sobre as mesmas previsões fora da dobra em que é
# reportado, então as métricas nesse limiar são um pouco otimistas.
APP_THRESHOLD = 0.45


def drop_link_marker(texto: str) -> str:
    """Tira o marcador de link, para a avaliação sem o sinal de canal."""
    return texto.replace("<LINK>", " ")


def build_pipeline(drop_link: bool = False) -> Pipeline:
    """TF-IDF de palavras e bigramas com regressão logística.

    `lowercase=False` porque `normalize_text` já entrega minúsculas e deixa os
    marcadores em maiúsculas de propósito: sem isso, `<TELEFONE>` virava o token
    "telefone" e colidia com a palavra comum. O `token_pattern` padrão descarta
    emoji, que nesta base é artefato de uma fonte só.
    """
    preprocessor = (lambda t: drop_link_marker(normalize_text(t))) if drop_link else normalize_text
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=preprocessor,
                    lowercase=False,
                    ngram_range=(1, 2),
                    min_df=1,
                ),
            ),
            (
                "modelo",
                LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
            ),
        ]
    )


def out_of_fold_predictions(messages: pd.DataFrame, drop_link: bool = False) -> pd.DataFrame:
    """Probabilidade de golpe para cada mensagem real, prevista fora da própria dobra."""
    real = messages[messages["origem"] == "real"]
    linhas = []
    for grupo in sorted(real["grupo"].unique()):
        treino = messages[messages["grupo"] != grupo]
        teste = real[real["grupo"] == grupo]
        pipeline = build_pipeline(drop_link).fit(treino["texto"], treino["rotulo"])
        indice_golpe = list(pipeline.classes_).index(POSITIVE)
        proba = pipeline.predict_proba(teste["texto"])[:, indice_golpe]
        linhas.append(teste.assign(proba=proba))
    return pd.concat(linhas, ignore_index=True)


def _counts(verdadeiro: pd.Series, previsto: pd.Series) -> dict[str, int]:
    golpe = verdadeiro == POSITIVE
    marcado = previsto == POSITIVE
    return {
        "vp": int((golpe & marcado).sum()),
        "fp": int((~golpe & marcado).sum()),
        "fn": int((golpe & ~marcado).sum()),
        "vn": int((~golpe & ~marcado).sum()),
    }


def _scores(contagens: dict[str, int]) -> dict[str, float]:
    vp, fp, fn = contagens["vp"], contagens["fp"], contagens["fn"]
    precisao = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
    return {"precisao": round(precisao, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def evaluate(verdadeiro: pd.Series, previsto: pd.Series) -> dict:
    contagens = _counts(verdadeiro, previsto)
    return {**_scores(contagens), "contagens": contagens, "mensagens": int(len(verdadeiro))}


def _as_prediction(oof: pd.DataFrame, threshold: float) -> pd.Series:
    return pd.Series(
        [POSITIVE if p >= threshold else "legitima" for p in oof["proba"]], index=oof.index
    )


def per_group_variation(oof: pd.DataFrame, previsto: pd.Series) -> dict:
    """Acerto por grupo: média e variação entre as dobras, separadas por rótulo."""
    acertou = previsto.to_numpy() == oof["rotulo"].to_numpy()
    por_grupo = (
        oof.assign(acertou=acertou).groupby(["rotulo", "grupo"])["acertou"].mean().reset_index()
    )
    resultado = {}
    for rotulo, bloco in por_grupo.groupby("rotulo"):
        resultado[rotulo] = {
            "grupos": int(len(bloco)),
            "acerto_medio": round(float(bloco["acertou"].mean()), 3),
            "desvio": round(float(bloco["acertou"].std(ddof=0)), 3),
            "grupos_sem_nenhum_acerto": int((bloco["acertou"] == 0).sum()),
        }
    return resultado


def unseen_types_recognized(oof: pd.DataFrame, previsto: pd.Series) -> dict:
    """De N tipos de golpe que o modelo não viu no treino, quantos ele reconheceu.

    Um tipo conta como reconhecido quando a maioria das mensagens dele é marcada.
    """
    golpes = oof["rotulo"] == POSITIVE
    marcado = pd.Series(previsto.to_numpy() == POSITIVE, index=oof.index)
    por_tipo = marcado[golpes].groupby(oof.loc[golpes, "grupo"]).mean()
    return {
        "tipos": int(len(por_tipo)),
        "reconhecidos": int((por_tipo >= 0.5).sum()),
        "reconhecidos_por_inteiro": int((por_tipo == 1).sum()),
        "nao_reconhecidos": sorted(por_tipo[por_tipo < 0.5].index),
    }


def _origin(oof: pd.DataFrame) -> pd.Series:
    # Quem vem do GitHub é anúncio de grupo; de URL de checagem, SMS ou alerta.
    return pd.Series(
        ["anuncio de grupo" if "github" in f else "SMS e alertas" for f in oof["fonte"]],
        index=oof.index,
    )


def recall_by_origin(oof: pd.DataFrame, previsto: pd.Series) -> dict:
    """Recall do golpe por origem, em contagem: SMS e alertas é o caso de uso do app."""
    golpes = oof[oof["rotulo"] == POSITIVE]
    marcado = pd.Series(previsto.to_numpy() == POSITIVE, index=oof.index).loc[golpes.index]
    resultado = {}
    for origem, bloco in marcado.groupby(_origin(golpes)):
        resultado[origem] = {
            "reconhecidos": int(bloco.sum()),
            "golpes": int(len(bloco)),
            "recall": round(float(bloco.mean()), 3),
        }
    return resultado


def threshold_table(oof: pd.DataFrame) -> pd.DataFrame:
    """Limiares avaliados sobre as previsões fora da dobra, não sobre o teste final."""
    linhas = []
    for threshold in THRESHOLDS:
        previsto = _as_prediction(oof, threshold)
        resultado = evaluate(oof["rotulo"], previsto)
        linhas.append(
            {
                "limiar": threshold,
                **{k: resultado[k] for k in ("precisao", "recall", "f1")},
                **resultado["contagens"],
            }
        )
    return pd.DataFrame(linhas)


def baseline_on_same_rows(oof: pd.DataFrame) -> dict:
    """Baseline nas mesmas mensagens, para a comparação ser lado a lado."""
    previsto = oof["texto"].map(baseline_predict)
    return {
        "limiar_de_sinais": BASELINE_THRESHOLD,
        **evaluate(oof["rotulo"], previsto),
        "por_grupo": per_group_variation(oof, previsto),
        "recall_por_origem": recall_by_origin(oof, previsto),
        "tipos_nao_vistos": unseen_types_recognized(oof, previsto),
    }


def save_confusion_matrix(oof: pd.DataFrame, previsto: pd.Series, destino, titulo: str) -> None:
    matriz = confusion_matrix(oof["rotulo"], previsto, labels=[POSITIVE, "legitima"])
    figura, eixo = plt.subplots(figsize=(4.5, 4))
    eixo.imshow(matriz, cmap="Blues")
    eixo.set_xticks([0, 1], ["golpe", "legitima"])
    eixo.set_yticks([0, 1], ["golpe", "legitima"])
    eixo.set_xlabel("previsto")
    eixo.set_ylabel("verdadeiro")
    eixo.set_title(titulo)
    limite = matriz.max() / 2
    for i in range(2):
        for j in range(2):
            eixo.text(
                j,
                i,
                str(matriz[i, j]),
                ha="center",
                va="center",
                color="white" if matriz[i, j] > limite else "black",
                fontsize=14,
            )
    eixo.grid(False)
    figura.tight_layout()
    figura.savefig(destino, dpi=150)
    plt.close(figura)


def _full_report(oof: pd.DataFrame, previsto: pd.Series) -> dict:
    return {
        **evaluate(oof["rotulo"], previsto),
        "por_grupo": per_group_variation(oof, previsto),
        "recall_por_origem": recall_by_origin(oof, previsto),
        "tipos_nao_vistos": unseen_types_recognized(oof, previsto),
    }


def run() -> tuple[dict, pd.DataFrame]:
    mensagens = load_messages()
    oof = out_of_fold_predictions(mensagens)
    previsto = _as_prediction(oof, DEFAULT_THRESHOLD)

    oof_sem_link = out_of_fold_predictions(mensagens, drop_link=True)
    previsto_sem_link = _as_prediction(oof_sem_link, DEFAULT_THRESHOLD)

    limiares = threshold_table(oof)

    metricas = {
        "base": {
            "mensagens": int(len(mensagens)),
            "grupos": int(mensagens["grupo"].nunique()),
            "no_teste": int(len(oof)),
            "grupos_no_teste": int(oof["grupo"].nunique()),
            "golpes_no_teste": int((oof["rotulo"] == POSITIVE).sum()),
            "legitimas_no_teste": int((oof["rotulo"] != POSITIVE).sum()),
        },
        "validacao": "leave-one-group-out, só mensagens reais no teste",
        "limiar": DEFAULT_THRESHOLD,
        "modelo": _full_report(oof, previsto),
        "modelo_sem_link": _full_report(oof_sem_link, previsto_sem_link),
        "baseline": baseline_on_same_rows(oof),
        "limiares_fora_da_dobra": limiares.to_dict(orient="records"),
        "limiar_do_app": {
            "limiar": APP_THRESHOLD,
            "escolhido_em": "tabela de limiares fora da dobra, não no teste",
            "ressalva": (
                "escolhido sobre as mesmas previsões fora da dobra em que é "
                "reportado, então estas métricas são um pouco otimistas"
            ),
            **_full_report(oof, _as_prediction(oof, APP_THRESHOLD)),
        },
    }
    return metricas, oof


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    metricas, oof = run()

    (REPORTS_DIR / "metricas.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    save_confusion_matrix(
        oof,
        _as_prediction(oof, DEFAULT_THRESHOLD),
        REPORTS_DIR / "matriz_confusao.png",
        f"Matriz de confusão, limiar {DEFAULT_THRESHOLD}",
    )
    save_confusion_matrix(
        oof,
        _as_prediction(oof, APP_THRESHOLD),
        REPORTS_DIR / "matriz_confusao_limiar_do_app.png",
        f"Matriz de confusão, limiar {APP_THRESHOLD}",
    )

    with pd.ExcelWriter(REPORTS_DIR / "metricas.xlsx") as excel:
        pd.DataFrame(
            [
                {"metrica": "precisao", **_por_abordagem(metricas, "precisao")},
                {"metrica": "recall", **_por_abordagem(metricas, "recall")},
                {"metrica": "f1", **_por_abordagem(metricas, "f1")},
            ]
        ).to_excel(excel, sheet_name="resumo", index=False)
        pd.DataFrame(metricas["limiares_fora_da_dobra"]).to_excel(
            excel, sheet_name="limiares", index=False
        )
        pd.DataFrame(
            [
                {"origem": origem, **valores}
                for origem, valores in metricas["modelo"]["recall_por_origem"].items()
            ]
        ).to_excel(excel, sheet_name="recall por origem", index=False)

    resumo = pd.DataFrame(
        [
            {"abordagem": nome, **{k: metricas[chave][k] for k in ("precisao", "recall", "f1")}}
            for nome, chave in (
                ("baseline", "baseline"),
                ("modelo", "modelo"),
                ("modelo sem LINK", "modelo_sem_link"),
                ("modelo no limiar do app", "limiar_do_app"),
            )
        ]
    )
    print(resumo.to_string(index=False))
    print(f"\nmétricas em {REPORTS_DIR}")


def _por_abordagem(metricas: dict, chave: str) -> dict:
    return {
        "baseline": metricas["baseline"][chave],
        "modelo": metricas["modelo"][chave],
        "modelo sem LINK": metricas["modelo_sem_link"][chave],
    }


if __name__ == "__main__":
    main()
