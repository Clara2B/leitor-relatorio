"""Tela de login simples (usuário + senha) para proteger o acesso ao
programa quando o código estiver num repositório público no GitHub.

A senha NUNCA fica no código nem no repositório: ela é lida de
`st.secrets` (arquivo `.streamlit/secrets.toml`, que está no .gitignore)
ou de uma variável de ambiente `APP_PASSWORD` / `APP_USUARIOS`.
Veja o README para como configurar.
"""
from __future__ import annotations

import os
from typing import Dict

import streamlit as st


def _carregar_usuarios() -> Dict[str, str]:
    """Retorna {usuario: senha}. Fontes, em ordem de prioridade:

    1. st.secrets["usuarios"] -> {"funcionario": "senha123", ...}
    2. st.secrets["app_password"] -> senha única, usuário fixo "acesso"
    3. variável de ambiente APP_PASSWORD -> senha única, usuário "acesso"
    """
    try:
        if "usuarios" in st.secrets:
            return dict(st.secrets["usuarios"])
        if "app_password" in st.secrets:
            return {"acesso": st.secrets["app_password"]}
    except Exception:
        pass  # sem secrets.toml configurado ainda

    senha_env = os.environ.get("APP_PASSWORD")
    if senha_env:
        return {"acesso": senha_env}

    return {}


def exigir_login() -> bool:
    """Mostra a tela de login se ainda não autenticado. Retorna True quando
    o usuário já pode ver o resto do programa."""
    if st.session_state.get("autenticado"):
        return True

    usuarios = _carregar_usuarios()

    st.markdown(
        """
        <style>
        .login-wrap { max-width: 380px; margin: 4rem auto 0 auto; }
        .login-wrap .selo { display:block; width:40px; height:4px; background:#9AA1AC;
            border-radius:2px; margin: 0 auto 0.8rem auto; }
        .login-wrap h1 { text-align:center !important; font-size:1.5rem; margin-bottom:0.2rem; }
        .login-wrap p.sub { text-align:center; opacity:0.65; margin-bottom:1.6rem; font-size:0.9rem; }
        </style>
        <div class="login-wrap">
            <span class="selo"></span>
            <h1>🔒 Acesso restrito</h1>
            <p class="sub">Entre com seu usuário e senha para continuar</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_meio, _ = st.columns([1, 1.3, 1])
    with col_meio:
        if not usuarios:
            st.warning(
                "Nenhuma senha configurada ainda. Veja no README como configurar "
                "`.streamlit/secrets.toml` (uso local) ou os *Secrets* do Streamlit "
                "Cloud (uso publicado) antes de liberar o acesso."
            )
            return False

        with st.container(border=True):
            with st.form("login"):
                usuario = st.text_input("Usuário")
                senha = st.text_input("Senha", type="password")
                entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if entrar:
            if usuarios.get(usuario) == senha:
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    return False


def botao_sair():
    if st.session_state.get("autenticado"):
        with st.sidebar:
            st.caption(f"Conectado como **{st.session_state.get('usuario', '')}**")
            if st.button("Sair"):
                st.session_state.clear()
                st.rerun()
