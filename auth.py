"""
Autenticação leve via st.session_state (gateway interno da guilda).
PIN do admin: configure em .streamlit/secrets.toml → admin_pin = "seu_pin"
"""

from __future__ import annotations

import streamlit as st

ADMIN_CARGOS = ("Líder", "Vice")
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
MAX_PIN_ATTEMPTS = 3
PAGE_ADMIN = "⚙️ Painel Administrativo"


def get_admin_pin() -> str | None:
    """Retorna o PIN configurado em secrets.toml ou None se não estiver definido."""
    try:
        pin = st.secrets.get("admin_pin")
    except (FileNotFoundError, AttributeError, KeyError):
        return None
    if pin is None:
        return None
    pin_str = str(pin).strip()
    return pin_str or None


def is_admin_cargo(cargo: str) -> bool:
    return cargo in ADMIN_CARGOS


def init_session_auth() -> None:
    defaults = {
        "logged_in": False,
        "role": None,
        "member_id": None,
        "nickname": None,
        "cargo": None,
        "pin_attempts": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_logged_in() -> bool:
    return bool(st.session_state.get("logged_in"))


def is_admin() -> bool:
    return is_logged_in() and st.session_state.get("role") == ROLE_ADMIN


def complete_login(member: dict, role: str) -> None:
    st.session_state.logged_in = True
    st.session_state.role = role
    st.session_state.member_id = int(member["id"])
    st.session_state.nickname = member["nickname"]
    st.session_state.cargo = member["cargo"]
    st.session_state.pin_attempts = 0


def logout() -> None:
    for key in (
        "logged_in",
        "role",
        "member_id",
        "nickname",
        "cargo",
        "pin_attempts",
        "nav_pagina",
        "login_pin",
        "login_nickname_existente",
        "login_nickname_novo",
    ):
        st.session_state.pop(key, None)


def require_admin() -> None:
    if not is_admin():
        st.error("Acesso restrito à liderança da guilda.")
        st.stop()
