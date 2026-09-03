"""Programa para montar relatórios de LAUDOS e AUDIÊNCIAS a partir das
planilhas de controle, aplicando os filtros e a tabela de valores.

Rodar com:  streamlit run app.py
"""
from __future__ import annotations

import tempfile
from datetime import date

import streamlit as st

from core import audiencias, laudos
from core.auth import botao_sair, exigir_login
from core.config_store import (
    get_cnpj_empresa,
    load_config,
    remove_cnpj_empresa,
    remove_config_audiencia,
    remove_valor_laudo,
    set_cnpj_empresa,
    set_config_audiencia,
    set_valor_laudo,
)
from core.pdf_export import gerar_pdf_audiencias, gerar_pdf_laudos
from core.utils import format_brl

st.set_page_config(page_title="Relatórios - Laudos e Audiências", layout="wide", page_icon="📄")

st.markdown(
    """
    <style>
    .bloco-metrica {
        background: var(--background-color);
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 10px;
        padding: 0.9rem 1rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(120,120,120,0.07);
        border-radius: 10px;
        padding: 0.6rem 0.8rem;
        border: 1px solid rgba(128,128,128,0.15);
    }
    .aviso-tipo-sem-valor {
        border-left: 4px solid #e0a800;
        padding-left: 0.7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def salvar_temp(upload) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(upload.getbuffer())
        return tmp.name


def caixa_texto_copiavel(texto: str, nome_arquivo: str):
    """Mostra o texto final pronto para copiar: bloco monoespaçado com botão
    de copiar embutido (passa o mouse no canto superior direito do bloco),
    mais um botão para baixar como .txt."""
    st.markdown("##### 📋 Texto pronto para copiar")
    st.code(texto, language=None)
    st.download_button("⬇️ Baixar como .txt", texto, file_name=nome_arquivo, use_container_width=False)


def botao_pdf(pdf_bytes: bytes, nome_arquivo: str):
    st.markdown("##### 📄 Relatório em PDF (folha personalizada)")
    st.download_button(
        "⬇️ Baixar PDF",
        pdf_bytes,
        file_name=nome_arquivo,
        mime="application/pdf",
        use_container_width=False,
    )


def pagina_laudos():
    st.header("📑 Relatório de Laudos")
    config = load_config()

    arquivo = st.file_uploader("Planilha de laudos (.xlsx)", type=["xlsx"], key="laudos_upload")
    if not arquivo:
        st.info("⬆️ Envie a planilha de laudos para continuar.")
        return

    try:
        path = salvar_temp(arquivo)
        df = laudos.carregar_planilha(path)
    except Exception as e:
        st.error(f"Não consegui ler a planilha: {e}")
        return

    empresas = laudos.listar_empresas(df)
    if not empresas:
        st.warning("Não encontrei nenhuma empresa na planilha.")
        return

    with st.container(border=True):
        st.markdown("##### Filtros")
        col1, col2, col3 = st.columns(3)
        with col1:
            empresa = st.selectbox("Empresa", empresas)
            cnpj = st.text_input(
                "CNPJ (preenchido automaticamente, pode editar)",
                value=get_cnpj_empresa(config, empresa),
                key=f"cnpj_laudo_{empresa}",
            )
        with col2:
            hoje = date.today()
            mes = st.selectbox("Mês de início do período (dia 21)", MESES, index=hoje.month - 1)
            ano = st.number_input("Ano", min_value=2020, max_value=2100, value=hoje.year, step=1)
        with col3:
            status_opcao = st.radio("Status", laudos.OPCOES_STATUS)
            st.caption("Por padrão, laudos de solicitação e de correção entram juntos no total (é assim que a cobrança é feita).")

        mes_num = MESES.index(mes) + 1
        periodo_ini, periodo_fim = laudos.periodo_20_a_20(int(ano), mes_num)
        st.caption(f"🗓️ Período aplicado: **{periodo_ini.strftime('%d/%m/%Y')}** a **{periodo_fim.strftime('%d/%m/%Y')}**")

        gerar = st.button("🔎 Gerar relatório", type="primary", key="gerar_laudos", use_container_width=True)

    if not gerar:
        return

    try:
        resultado = laudos.gerar_relatorio(
            df, config, empresa, periodo_ini, periodo_fim, status_opcao, cnpj or None
        )
    except ValueError as e:
        st.error(str(e))
        return

    if resultado.linhas.empty:
        st.warning(
            f"Nenhum laudo encontrado para **{empresa}** no período "
            f"{periodo_ini.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')} "
            f"com status **{resultado.status}**."
        )
        return

    if resultado.tipos_sem_valor:
        st.markdown('<div class="aviso-tipo-sem-valor">', unsafe_allow_html=True)
        st.warning(
            "⚠️ Estes tipos de laudo apareceram na planilha mas não estão cadastrados "
            "na tabela de valores (entraram como R$ 0,00): "
            + ", ".join(f"**{t}**" for t in resultado.tipos_sem_valor)
            + ". Cadastre o valor na aba **⚙️ Gerenciar valores** e gere de novo."
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"#### Resultado — {resultado.empresa.upper()} · {resultado.status}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Laudos encontrados", len(resultado.linhas))
    m2.metric("Total geral", format_brl(resultado.total))
    m3.metric("Tipos diferentes", resultado.linhas["TIPO"].nunique())

    with st.expander("Ver tabela detalhada", expanded=True):
        tabela = resultado.linhas.copy()
        tabela["DATA"] = tabela["DATA"].apply(lambda d: d.strftime("%d/%m/%Y"))
        tabela["VALOR"] = tabela["VALOR"].apply(format_brl)
        tabela.columns = ["Data", "Cliente", "Tipo de laudo", "Valor"]
        st.dataframe(tabela, use_container_width=True, hide_index=True)

    resumo_por_tipo = (
        resultado.linhas.groupby("TIPO")["VALOR"]
        .agg(Quantidade="count", Subtotal="sum")
        .reset_index()
        .rename(columns={"TIPO": "Tipo de laudo"})
    )
    resumo_por_tipo["Subtotal"] = resumo_por_tipo["Subtotal"].apply(format_brl)
    with st.expander("Ver resumo por tipo de laudo"):
        st.dataframe(resumo_por_tipo, use_container_width=True, hide_index=True)

    texto = laudos.formatar_texto(resultado)
    caixa_texto_copiavel(texto, f"relatorio_laudos_{empresa}.txt")

    pdf_bytes = gerar_pdf_laudos(resultado)
    botao_pdf(pdf_bytes, f"relatorio_laudos_{empresa}.pdf")


def pagina_audiencias():
    st.header("⚖️ Relatório de Audiências")
    config = load_config()

    arquivo = st.file_uploader("Planilha de audiências (.xlsx)", type=["xlsx"], key="audiencias_upload")
    if not arquivo:
        st.info("⬆️ Envie a planilha de audiências para continuar.")
        return

    try:
        path = salvar_temp(arquivo)
        df = audiencias.carregar_planilha(path)
    except Exception as e:
        st.error(f"Não consegui ler a planilha: {e}")
        return

    empresas = audiencias.listar_empresas(df)
    if not empresas:
        st.warning("Não encontrei nenhuma empresa na planilha.")
        return

    with st.container(border=True):
        st.markdown("##### Filtros")
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.selectbox("Empresa", empresas, key="empresa_aud")
            cnpj = st.text_input(
                "CNPJ (preenchido automaticamente, pode editar)",
                value=get_cnpj_empresa(config, empresa),
                key=f"cnpj_aud_{empresa}",
            )
        with col2:
            hoje = date.today()
            mes = st.selectbox("Mês", MESES, index=hoje.month - 1, key="mes_aud")
            ano = st.number_input("Ano", min_value=2020, max_value=2100, value=hoje.year, step=1, key="ano_aud")
            quinzena = st.radio("Quinzena", ["1 a 15", "16 ao fim do mês"], key="quinzena_aud")

        mes_num = MESES.index(mes) + 1
        quinzena_num = 1 if quinzena == "1 a 15" else 2
        periodo_ini, periodo_fim = audiencias.periodo_quinzenal(int(ano), mes_num, quinzena_num)
        st.caption(f"🗓️ Período aplicado: **{periodo_ini.strftime('%d/%m/%Y')}** a **{periodo_fim.strftime('%d/%m/%Y')}**")

        gerar = st.button("🔎 Gerar relatório", type="primary", key="gerar_audiencias", use_container_width=True)

    if not gerar:
        return

    try:
        resultado = audiencias.gerar_relatorio(df, config, empresa, periodo_ini, periodo_fim, cnpj or None)
    except ValueError as e:
        st.error(str(e))
        return

    if not resultado.clientes:
        st.warning(
            f"Nenhuma audiência encontrada para **{empresa}** no período "
            f"{periodo_ini.strftime('%d/%m/%Y')} a {periodo_fim.strftime('%d/%m/%Y')}."
        )
        return

    if not resultado.valor_cadastrado:
        st.warning(
            f"⚠️ A empresa **{empresa}** ainda não tem valor cadastrado. "
            "Cadastre abaixo ou na aba **⚙️ Gerenciar valores**."
        )
        with st.form("cadastro_rapido_audiencia"):
            st.write(f"Cadastrar valor agora para {empresa}:")
            valor_novo = st.number_input("Valor por audiência (R$)", min_value=0.0, step=10.0)
            if st.form_submit_button("Cadastrar e gerar novamente", type="primary"):
                set_config_audiencia(config, empresa, valor_novo)
                st.success("Cadastrado! Clique em '🔎 Gerar relatório' novamente.")
        return

    st.markdown(f"#### Resultado — {resultado.empresa.upper()}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Audiências no período", len(resultado.clientes))
    m2.metric("Valor por audiência", format_brl(resultado.valor_unitario) if resultado.valor_unitario else "—")
    m3.metric("Total", format_brl(resultado.total) if resultado.total is not None else "—")

    with st.expander("Ver lista de clientes", expanded=True):
        st.dataframe(
            {"#": range(1, len(resultado.clientes) + 1), "Cliente": resultado.clientes},
            use_container_width=True,
            hide_index=True,
        )

    texto = audiencias.formatar_texto(resultado)
    caixa_texto_copiavel(texto, f"relatorio_audiencias_{empresa}.txt")

    pdf_bytes = gerar_pdf_audiencias(resultado)
    botao_pdf(pdf_bytes, f"relatorio_audiencias_{empresa}.pdf")


def pagina_gerenciar_valores():
    st.header("⚙️ Gerenciar valores")
    config = load_config()

    st.subheader("🧾 Tipos de laudo")
    st.caption("Valor fixo (R$) usado para calcular o relatório de laudos, por tipo.")

    laudos_cfg = config.get("laudos", {})
    if not laudos_cfg:
        st.info("Nenhum tipo de laudo cadastrado ainda.")
    for tipo, valor in list(laudos_cfg.items()):
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.markdown(f"**{tipo}**")
            novo_valor = c2.number_input(
                "Valor (R$)", min_value=0.0, step=5.0, value=float(valor), key=f"laudo_{tipo}"
            )
            c3.write("")
            c3.write("")
            if c3.button("🗑️ Remover", key=f"rm_laudo_{tipo}", use_container_width=True):
                remove_valor_laudo(config, tipo)
                st.rerun()
            if novo_valor != valor:
                set_valor_laudo(config, tipo, novo_valor)
                st.rerun()

    with st.form("novo_tipo_laudo", border=True):
        st.markdown("**➕ Adicionar novo tipo de laudo**")
        c1, c2 = st.columns([3, 1])
        novo_tipo = c1.text_input("Nome do tipo (ex: LAUDO VEÍCULO)")
        novo_valor = c2.number_input("Valor (R$)", min_value=0.0, step=5.0)
        if st.form_submit_button("Adicionar", type="primary"):
            if novo_tipo.strip():
                set_valor_laudo(config, novo_tipo.strip(), novo_valor)
                st.rerun()
            else:
                st.error("Informe o nome do tipo de laudo.")

    st.divider()
    st.subheader("⚖️ Empresas de audiência")
    st.caption("Valor por audiência, por empresa.")

    aud_cfg = config.get("audiencias", {})
    if not aud_cfg:
        st.info("Nenhuma empresa de audiência cadastrada ainda.")
    for empresa, dados in list(aud_cfg.items()):
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.markdown(f"**{empresa}**")
            novo_valor = c2.number_input(
                "Valor por audiência (R$)",
                min_value=0.0,
                step=10.0,
                value=float(dados.get("valor", 0.0)),
                key=f"val_{empresa}",
            )
            c3.write("")
            c3.write("")
            if c3.button("🗑️ Remover", key=f"rm_aud_{empresa}", use_container_width=True):
                remove_config_audiencia(config, empresa)
                st.rerun()
            if novo_valor != dados.get("valor"):
                set_config_audiencia(config, empresa, novo_valor)
                st.rerun()

    with st.form("nova_empresa_audiencia", border=True):
        st.markdown("**➕ Adicionar nova empresa**")
        c1, c2 = st.columns(2)
        nova_empresa = c1.text_input("Nome da empresa")
        novo_valor = c2.number_input("Valor por audiência (R$)", min_value=0.0, step=10.0)
        if st.form_submit_button("Adicionar", type="primary"):
            if nova_empresa.strip():
                set_config_audiencia(config, nova_empresa.strip(), novo_valor)
                st.rerun()
            else:
                st.error("Informe o nome da empresa.")

    st.divider()
    st.subheader("🏢 CNPJ das empresas")
    st.caption(
        "Preenche automaticamente o campo CNPJ ao gerar relatório de laudos ou "
        "audiências para essa empresa (continua editável na hora de gerar)."
    )

    cnpjs_cfg = config.get("cnpjs", {})
    if not cnpjs_cfg:
        st.info("Nenhum CNPJ cadastrado ainda.")
    for empresa_nome, cnpj_atual in list(cnpjs_cfg.items()):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 3, 1])
            c1.markdown(f"**{empresa_nome}**")
            novo_cnpj = c2.text_input(
                "CNPJ", value=cnpj_atual, key=f"cnpj_cfg_{empresa_nome}", label_visibility="collapsed"
            )
            c3.write("")
            if c3.button("🗑️ Remover", key=f"rm_cnpj_{empresa_nome}", use_container_width=True):
                remove_cnpj_empresa(config, empresa_nome)
                st.rerun()
            if novo_cnpj != cnpj_atual:
                set_cnpj_empresa(config, empresa_nome, novo_cnpj)
                st.rerun()

    with st.form("novo_cnpj_empresa", border=True):
        st.markdown("**➕ Adicionar CNPJ de uma empresa**")
        c1, c2 = st.columns(2)
        nome_para_cnpj = c1.text_input("Nome da empresa (como aparece na planilha)")
        cnpj_novo = c2.text_input("CNPJ")
        if st.form_submit_button("Adicionar", type="primary"):
            if nome_para_cnpj.strip():
                set_cnpj_empresa(config, nome_para_cnpj.strip(), cnpj_novo.strip())
                st.rerun()
            else:
                st.error("Informe o nome da empresa.")


def main():
    if not exigir_login():
        return
    botao_sair()

    st.title("📄 Relatórios — Laudos e Audiências")
    st.caption("Monte o relatório, copie o texto pronto e cole direto no seu documento final.")

    aba_laudos, aba_audiencias, aba_valores = st.tabs(
        ["📑 Relatório de Laudos", "⚖️ Relatório de Audiências", "⚙️ Gerenciar valores"]
    )
    with aba_laudos:
        pagina_laudos()
    with aba_audiencias:
        pagina_audiencias()
    with aba_valores:
        pagina_gerenciar_valores()


if __name__ == "__main__":
    main()
