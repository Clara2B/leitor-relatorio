"""Programa para montar relatórios de LAUDOS e AUDIÊNCIAS a partir das
planilhas de controle, aplicando os filtros e a tabela de valores.

Rodar com:  streamlit run app.py
"""
from __future__ import annotations

import base64
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from core import audiencias, laudos, pendencias
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

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


@st.cache_data(show_spinner=False)
def _logo_base64(nome_arquivo: str) -> str:
    caminho = ASSETS_DIR / nome_arquivo
    if not caminho.exists():
        return ""
    return base64.b64encode(caminho.read_bytes()).decode("ascii")


LOGO_ELITE = _logo_base64("logo_elite_compact.png")
LOGO_EXIMIA = _logo_base64("logo_eximia_compact.png")

# Tema neutro (preto/branco/cinza) no modo geral. As abas de Laudos e de
# Audiências sobrescrevem essas variáveis dentro do próprio painel da aba
# (usando a ordem das abas no DOM — não precisa de JavaScript), assumindo a
# identidade visual da ELITE e da EXIMIA respectivamente. Pendências e
# Gerenciar valores não têm sobrescrita: ficam no neutro.
st.markdown(
    """
    <style>
    :root {
        --brand: #16171A;
        --brand-2: #34363B;
        --accent: #9AA1AC;
        --accent-light: #C7CCD3;
        --accent-wash: rgba(22,23,26,0.05);
    }

    /* 1ª aba (Laudos) = identidade ELITE */
    [data-testid="stTabPanel"]:nth-of-type(1) {
        --brand: #072652;
        --brand-2: #123F6E;
        --accent: #C9A227;
        --accent-light: #E4C765;
        --accent-wash: rgba(201,162,39,0.08);
    }
    /* 2ª aba (Audiências) = identidade EXIMIA */
    [data-testid="stTabPanel"]:nth-of-type(2) {
        --brand: #1A2946;
        --brand-2: #2C3F63;
        --accent: #B08D57;
        --accent-light: #CBB07F;
        --accent-wash: rgba(176,141,87,0.08);
    }

    /* Banner de topo do app (fora das abas — sempre neutro) */
    .app-banner {
        background: linear-gradient(120deg, var(--brand) 0%, var(--brand-2) 100%);
        border-radius: 14px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 6px 18px rgba(0,0,0,0.18);
    }
    .app-banner .selo {
        display: inline-block;
        width: 34px; height: 4px;
        background: var(--accent);
        border-radius: 2px;
        margin-bottom: 0.6rem;
    }
    .app-banner h1 {
        color: #fff;
        font-size: 1.7rem;
        letter-spacing: 0.03em;
        margin: 0 0 0.3rem 0;
        font-weight: 700;
    }
    .app-banner p {
        color: #D6D8DB;
        margin: 0;
        font-size: 0.95rem;
    }

    /* Banner de marca dentro de cada aba (logo real + cor da empresa) */
    .marca-banner {
        display: flex;
        align-items: center;
        gap: 1.1rem;
        background: linear-gradient(120deg, var(--brand) 0%, var(--brand-2) 100%);
        border-radius: 14px;
        padding: 1.1rem 1.4rem;
        margin-bottom: 1.2rem;
    }
    .marca-banner .chip {
        background: #fff;
        border-radius: 10px;
        padding: 0.5rem 0.9rem;
        display: flex;
        align-items: center;
        flex-shrink: 0;
    }
    .marca-banner .chip img {
        height: 34px;
        display: block;
    }
    .marca-banner h2 {
        color: #fff !important;
        border-left: none !important;
        padding-left: 0 !important;
        margin: 0 !important;
        font-size: 1.3rem !important;
        font-weight: 700 !important;
    }
    .marca-banner p {
        color: #D6D8DB;
        margin: 0.15rem 0 0 0;
        font-size: 0.88rem;
    }

    /* Abas — seletores por data-testid (mais estáveis que as classes
    geradas) e !important em tudo, para não deixar nenhuma cor padrão do
    tema do Streamlit (inclusive o vermelho de foco/seleção) vazar por
    cima do visual. */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid rgba(0,0,0,0.12) !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"] {
        height: 3rem;
        font-weight: 600;
        border-bottom: 3px solid transparent !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"] p {
        color: #8a95a3 !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
        border-bottom-color: var(--accent) !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] p {
        color: var(--brand) !important;
        font-weight: 700 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: var(--accent) !important;
    }

    /* Botões primários (inclui os de dentro de formulários: kind
    "primary" para st.button e "primaryFormSubmit" para
    st.form_submit_button) */
    button[kind*="rimary"] {
        background-color: var(--brand) !important;
        border: 1px solid var(--brand) !important;
        font-weight: 600 !important;
    }
    button[kind*="rimary"]:hover {
        background-color: var(--brand-2) !important;
        border-color: var(--accent) !important;
        color: var(--accent-light) !important;
    }

    /* Cartões / containers com borda */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
    }

    /* Métricas */
    div[data-testid="stMetric"] {
        background: var(--accent-wash);
        border-radius: 12px;
        padding: 0.7rem 1rem;
        border-left: 4px solid var(--accent);
    }
    div[data-testid="stMetricLabel"] {
        font-weight: 600;
        opacity: 0.75;
    }

    /* Avisos de tipo sem valor */
    .aviso-tipo-sem-valor {
        border-left: 4px solid #e0a800;
        padding-left: 0.7rem;
    }

    /* Cabeçalhos de seção com traço na cor da aba */
    h2, h3, h4, h5 {
        border-left: 3px solid var(--accent);
        padding-left: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def banner(titulo: str, subtitulo: str):
    """Banner neutro do topo do app (fora das abas)."""
    st.markdown(
        f"""
        <div class="app-banner">
            <span class="selo"></span>
            <h1>{titulo}</h1>
            <p>{subtitulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def marca_banner(logo_base64: str, titulo: str, subtitulo: str):
    """Banner com a identidade da marca (logo real + cor da empresa),
    usado no topo de cada aba de relatório."""
    logo_html = f'<img src="data:image/png;base64,{logo_base64}">' if logo_base64 else ""
    st.markdown(
        f"""
        <div class="marca-banner">
            <div class="chip">{logo_html}</div>
            <div>
                <h2>{titulo}</h2>
                <p>{subtitulo}</p>
            </div>
        </div>
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
    marca_banner(LOGO_ELITE, "Relatório de Laudos", "Emitido pela ELITE MEDIAÇÕES")
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
        tabela.columns = ["Data", "Cliente", "Tipo de laudo", "Status", "Valor"]
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

    periodo_arquivo = f"{periodo_ini.strftime('%d.%m')}_a_{periodo_fim.strftime('%d.%m')}"
    pdf_bytes = gerar_pdf_laudos(resultado)
    botao_pdf(pdf_bytes, f"relatorio_laudos_{empresa}_{periodo_arquivo}.pdf")


def pagina_audiencias():
    marca_banner(LOGO_EXIMIA, "Relatório de Audiências", "Emitido pela EXIMIA CÂMARA DE CONCILIAÇÃO")
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

    periodo_arquivo = f"{periodo_ini.strftime('%d.%m')}_a_{periodo_fim.strftime('%d.%m')}"
    pdf_bytes = gerar_pdf_audiencias(resultado)
    botao_pdf(pdf_bytes, f"relatorio_audiencias_{empresa}_{periodo_arquivo}.pdf")


def pagina_pendencias():
    st.header("💬 Cobrança de Pendências")
    st.caption(
        "Envie a planilha de controle de pagamento (só a ELITE tem) e escolha a "
        "empresa — o programa monta a mensagem de cobrança pronta para o WhatsApp."
    )

    arquivo = st.file_uploader(
        "Planilha de controle de pagamento/pendência (.xlsx)", type=["xlsx"], key="pendencias_upload"
    )
    if not arquivo:
        st.info("⬆️ Envie a planilha para continuar.")
        return

    try:
        path = salvar_temp(arquivo)
        df = pendencias.carregar_planilha(path)
    except Exception as e:
        st.error(f"Não consegui ler a planilha: {e}")
        return

    empresas = pendencias.listar_empresas(df)
    if not empresas:
        st.warning("Não encontrei nenhuma empresa na planilha.")
        return

    with st.container(border=True):
        st.markdown("##### Filtros")
        empresa = st.selectbox("Empresa", empresas, key="empresa_pendencias")
        gerar = st.button("🔎 Gerar mensagem", type="primary", key="gerar_pendencias", use_container_width=True)

    if not gerar:
        return

    try:
        mensagens = pendencias.gerar_mensagens(df, empresa)
    except ValueError as e:
        st.error(str(e))
        return

    if not mensagens:
        st.success(f"✅ **{empresa}** não tem nenhuma pendência em aberto nesta planilha.")
        return

    st.markdown(f"#### Pendências encontradas — {empresa.upper()}")
    if len(mensagens) > 1:
        st.info(
            "Essa empresa tem pendência com **mais de um cobrador** (EXIMIA e ELITE) — "
            "gerei uma mensagem separada para cada uma, já que o PIX de recebimento é diferente."
        )

    for msg in mensagens:
        st.markdown(f"##### {'⚖️ EXIMIA (audiências)' if msg.cobrador == 'EXIMIA' else '📑 ELITE (laudos/mensalidade)'}")
        m1, m2 = st.columns(2)
        m1.metric("Itens pendentes", len(msg.itens))
        m2.metric("Total pendente", format_brl(msg.total))
        texto = pendencias.formatar_texto(msg)
        st.code(texto, language=None)
        st.download_button(
            "⬇️ Baixar como .txt",
            texto,
            file_name=f"cobranca_{empresa}_{msg.cobrador}.txt",
            key=f"download_pendencia_{msg.cobrador}",
        )
        st.divider()


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

    banner(
        "📄 Relatórios — Laudos e Audiências",
        "Monte o relatório, copie o texto pronto ou baixe o PDF já na folha personalizada.",
    )

    aba_laudos, aba_audiencias, aba_pendencias, aba_valores = st.tabs(
        [
            "📑 Relatório de Laudos",
            "⚖️ Relatório de Audiências",
            "💬 Cobrança de Pendências",
            "⚙️ Gerenciar valores",
        ]
    )
    with aba_laudos:
        pagina_laudos()
    with aba_audiencias:
        pagina_audiencias()
    with aba_pendencias:
        pagina_pendencias()
    with aba_valores:
        pagina_gerenciar_valores()


if __name__ == "__main__":
    main()
