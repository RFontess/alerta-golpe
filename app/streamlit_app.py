"""Interface do Alerta Golpe.

A pessoa cola a mensagem, clica em "Verificar" e vê o nível, os sinais e a dica.

Três cuidados que o código precisa manter:

- O texto da pessoa nunca é renderizado como Markdown nem como HTML. Tudo que vem da
  mensagem sai por `st.text`, senão o link do golpe viraria link clicável dentro do app.
  `unsafe_allow_html` aparece uma vez só, com o CSS, nunca com conteúdo da pessoa.
- O texto não é guardado em lugar nenhum: nada de `print`, de log ou de `st.cache_data`.
  O rodapé promete isso.
- Os textos que a pessoa lê moram em `explain.py`, que é quem decide. Aqui só entra o
  que é da tela.

O resultado aparece logo abaixo do botão "Verificar", e os exemplos ficam num expander
fechado acima da caixa: no celular, qualquer coisa entre o botão e o resultado empurra o
resultado para fora da tela.

O app não importa nada de treino e não lê a base: chama `explain` e o monitoramento.
"""

import streamlit as st

from alerta_golpe import monitoring
from alerta_golpe.explain import (
    ANONYMIZATION_NOTE,
    RULE_TEXT,
    SIGNAL_PHRASES,
    Explanation,
    explain,
)

# Exemplos inventados para quem chega do portfólio testar rápido. Não saem da base: os
# links usam o domínio reservado `.example` e não há telefone nenhum.
EXAMPLES: tuple[tuple[str, str], ...] = (
    (
        "Exemplo de golpe",
        "Sua conta sera bloqueada hoje. Atualize seus dados em https://banco-seguro.example/acesso",
    ),
    ("Exemplo com um ponto de atenção", "Seu pedido saiu para entrega e chega hoje"),
    ("Exemplo sem sinais", "Oi, cheguei bem em casa. Te ligo mais tarde."),
)

EXAMPLE_TEXTS = frozenset(texto for _, texto in EXAMPLES)

FOOTER = (
    "Protótipo de estudo. Não substitui confirmar com o banco pelos canais oficiais. "
    "O texto da mensagem não é guardado. Guardamos só o resultado e a sua resposta, "
    "para medir o protótipo."
)

FEEDBACK_QUESTION = "Se você já sabe, conte para a gente:"

FEEDBACK_THANKS = "Obrigado. Sua resposta ajuda a medir o protótipo."

# O banco guarda o vocabulário sem acento, igual ao dos sinais do baseline. A tela
# acentua; o que não estiver aqui aparece como está gravado.
ACCENTED_NAMES: dict[str, str] = {
    "medio": "médio",
    "nao era golpe": "não era golpe",
    "urgencia": "urgência",
    "ameaca": "ameaça",
    "pix": "Pix",
    "beneficio ou premio": "benefício ou prêmio",
    "credito para negativado": "crédito para negativado",
}

EMPTY_WARNING = "Cole a mensagem na caixa acima antes de clicar em Verificar."

MAX_CHARS = 2000

# Letra grande e botão grande para quem usa o app no celular, e nenhuma barra lateral.
CSS = """
<style>
    section[data-testid="stSidebar"] { display: none; }
    html, body, .stApp, [data-testid="stAppViewContainer"] { font-size: 20px; }
    .stApp p, .stApp li, .stApp label, .stApp div[data-testid="stText"] { font-size: 20px; }
    .stApp textarea { font-size: 20px; line-height: 1.5; }
    .stApp button { font-size: 20px; padding: 0.7em 1.2em; }
    .stApp [data-testid="stAlert"] p { font-size: 22px; }
    .stApp [data-testid="stCaptionContainer"] p { font-size: 16px; }
</style>
"""

MESSAGE_KEY = "mensagem"
RESULT_KEY = "resultado"
CHECK_ID_KEY = "verificacao"
ANSWERED_KEY = "respondeu"

MONITORING_PAGE = "monitoramento"


def _accented(nome: str) -> str:
    return ACCENTED_NAMES.get(nome, nome)


def _clear_result() -> None:
    """Editar a mensagem apaga o resultado: nunca mostrar a resposta de outro texto."""
    for chave in (RESULT_KEY, CHECK_ID_KEY, ANSWERED_KEY):
        st.session_state.pop(chave, None)


def _check(mensagem: str) -> None:
    resultado = explain(mensagem)
    st.session_state[RESULT_KEY] = resultado
    st.session_state[CHECK_ID_KEY] = monitoring.record(
        resultado.anonymized,
        resultado.level,
        [sinal.name for sinal in resultado.signals],
        from_example=mensagem in EXAMPLE_TEXTS,
    )
    st.session_state.pop(ANSWERED_KEY, None)


def _answer(resposta: str) -> None:
    monitoring.answer(st.session_state[CHECK_ID_KEY], resposta)
    st.session_state[ANSWERED_KEY] = True


def _use_example(texto: str) -> None:
    # Preenche a caixa e já verifica: o resultado fica pronto antes da tela desenhar.
    st.session_state[MESSAGE_KEY] = texto
    _check(texto)


def _show_level(resultado: Explanation) -> None:
    # O título diz o nível por escrito: a cor nunca é a única pista. O "baixo" usa a
    # caixa neutra, nunca verde, porque a regra deixa passar golpe.
    caixa = {"alto": st.error, "medio": st.warning, "baixo": st.info}[resultado.level]
    caixa(f"**{resultado.title}**")


def _show_signals(resultado: Explanation) -> None:
    if not resultado.signals:
        return
    st.markdown("**O que chamou atenção:**")
    for sinal in resultado.signals:
        st.markdown(f"- {sinal.phrase}")
        if sinal.words:
            # st.text não interpreta Markdown: as palavras vêm da mensagem da pessoa.
            st.text("    na mensagem: " + ", ".join(sinal.words))


def _show_details(resultado: Explanation) -> None:
    with st.expander("Como o Alerta Golpe chegou nisso"):
        st.markdown(RULE_TEXT)
        st.markdown("**Os oito sinais:**")
        for frase in SIGNAL_PHRASES.values():
            st.markdown(f"- {frase}")
        st.markdown(ANONYMIZATION_NOTE)
        st.text(resultado.anonymized)


def _show_feedback() -> None:
    if st.session_state.get(ANSWERED_KEY):
        st.markdown(FEEDBACK_THANKS)
        return
    st.markdown(FEEDBACK_QUESTION)
    esquerda, direita = st.columns(2)
    esquerda.button(
        "Era golpe", key="era-golpe", on_click=_answer, args=("era golpe",), width="stretch"
    )
    direita.button(
        "Não era golpe",
        key="nao-era-golpe",
        on_click=_answer,
        args=("nao era golpe",),
        width="stretch",
    )


def _show_result(resultado: Explanation) -> None:
    _show_level(resultado)
    st.markdown(resultado.message)
    _show_signals(resultado)
    st.markdown("**O que fazer:**")
    st.markdown(resultado.category_tip)
    st.markdown(resultado.general_tip)
    _show_details(resultado)
    _show_feedback()


def _show_examples() -> None:
    with st.expander("Quer testar? Use um exemplo"):
        for rotulo, texto in EXAMPLES:
            st.button(rotulo, key=f"exemplo-{rotulo}", on_click=_use_example, args=(texto,))


def check_page() -> None:
    st.title("Alerta Golpe")
    st.markdown("Cole aqui a mensagem que você recebeu e veja se ela tem sinais de golpe.")
    _show_examples()

    st.text_area(
        "Mensagem recebida",
        key=MESSAGE_KEY,
        height=180,
        max_chars=MAX_CHARS,
        on_change=_clear_result,
    )
    verificar = st.button("Verificar", key="verificar", type="primary", width="stretch")

    mensagem = st.session_state.get(MESSAGE_KEY, "")
    if verificar and mensagem.strip():
        _check(mensagem)
    elif verificar:
        _clear_result()
        st.markdown(EMPTY_WARNING)

    if RESULT_KEY in st.session_state:
        _show_result(st.session_state[RESULT_KEY])

    st.divider()
    st.markdown(FOOTER)
    st.caption(f"[Monitoramento do protótipo](?pagina={MONITORING_PAGE})")


def monitoring_page() -> None:
    st.title("Monitoramento")
    st.markdown("Quantas verificações o protótipo já fez e o que as pessoas responderam.")

    resumo = monitoring.summary()
    if not resumo["verificacoes"]:
        st.markdown("Nenhuma verificação registrada ainda.")
        st.markdown("[Voltar](?)")
        return

    uma, duas, tres = st.columns(3)
    uma.metric("Verificações", resumo["verificacoes"])
    duas.metric("Mensagens coladas", resumo["mensagens_coladas"])
    tres.metric("Exemplos", resumo["exemplos"])

    st.markdown("**Por nível:**")
    for nivel, quantas in resumo["por_nivel"].items():
        st.markdown(f"- {_accented(nivel)}: {quantas}")

    st.markdown("**Por sinal:**")
    if resumo["por_sinal"]:
        for nome, quantas in resumo["por_sinal"].items():
            st.markdown(f"- {_accented(nome)}: {quantas}")
    else:
        st.markdown("- nenhum sinal disparado ainda")

    st.markdown("**Respostas por nível:**")
    if resumo["respostas_por_nivel"]:
        for nivel, respostas in resumo["respostas_por_nivel"].items():
            detalhe = ", ".join(f"{_accented(r)}: {q}" for r, q in respostas.items())
            st.markdown(f"- {_accented(nivel)}: {detalhe}")
    else:
        st.markdown("- ninguém respondeu ainda")

    st.download_button(
        "Baixar o histórico em Excel",
        data=monitoring.history_excel(),
        file_name="monitoramento.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.divider()
    st.markdown("[Voltar](?)")


def main() -> None:
    st.set_page_config(
        page_title="Alerta Golpe",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    if st.query_params.get("pagina") == MONITORING_PAGE:
        monitoring_page()
    else:
        check_page()


main()
