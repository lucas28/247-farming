"""
Plataforma Web de Gerenciamento — Guilda Summoners War

Como rodar o projeto:
    1. Crie um ambiente virtual (opcional, recomendado):
       python -m venv venv
       venv\\Scripts\\activate        # Windows
       source venv/bin/activate      # Linux/macOS

    2. Instale as dependências:
       pip install -r requirements.txt

    3. Inicie o aplicativo:
       streamlit run app.py

    4. O banco SQLite é criado automaticamente em data/guilda.db
       na primeira execução, com dados de exemplo.

    5. Acesse http://localhost:8501 no navegador.

    6. Na primeira visita, identifique-se pelo nickname (IGN).
       Líder/Vice precisam do PIN configurado em .streamlit/secrets.toml
       (veja .streamlit/secrets.toml.example).
"""

import base64
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).parent
# Miniatura para UI (rápida); PNG completo como fallback e favicon
CREST_UI_CANDIDATES = (
    BASE_DIR / "data" / "crest_thumb.png",
    BASE_DIR / "247farming.png",
    BASE_DIR / "data" / "guild_crest.png",
)
CREST_FAVICON_CANDIDATES = (
    BASE_DIR / "data" / "crest_thumb.png",
    BASE_DIR / "247farming.png",
)

import guides
from database import (
    CARGOS,
    ESTRELAS,
    STATUS_OPCOES,
    TIPOS_DEFESA,
    DatabaseConnectionError,
    connection_setup_hints,
    create_defesa,
    create_membro,
    delete_defesa,
    delete_membro,
    get_membro_by_nickname,
    init_db,
    load_defesas,
    load_guild_config,
    load_membros,
    load_nicknames_ativos,
    register_membro_onboarding,
    update_defesa,
    update_guild_config,
    update_membro,
)
from auth import (
    MAX_PIN_ATTEMPTS,
    PAGE_ADMIN,
    ROLE_ADMIN,
    ROLE_MEMBER,
    complete_login,
    get_admin_pin,
    init_session_auth,
    is_admin,
    is_admin_cargo,
    is_logged_in,
    logout,
    require_admin,
)
from monsters import PLACEHOLDER_IMG, resolve_many, unique_monsters_from_defesas
from speed_calculator import render_speed_calculator

# Versão local do cache de imagens (incrementar ao mudar regras de elemento/imagem)
_IMAGE_CACHE_VERSION = 3

# ---------------------------------------------------------------------------
# Configuração global da página
# ---------------------------------------------------------------------------

PAGINAS = [
    "🏠 Dashboard",
    "📜 Guias e Regras",
    "🛡️ Banco de Defesas",
    "⚡ Calculadora de Speed Tuning",
    "👥 Membros da Guilda",
    PAGE_ADMIN,
]


def paginas_para_usuario() -> list[str]:
    if is_admin():
        return PAGINAS
    return [p for p in PAGINAS if p != PAGE_ADMIN]


def resolve_crest_path(for_favicon: bool = False) -> Path | None:
    candidates = CREST_FAVICON_CANDIDATES if for_favicon else CREST_UI_CANDIDATES
    for path in candidates:
        if path.exists():
            return path
    return None


@st.cache_data(show_spinner=False)
def crest_data_uri() -> str:
    path = resolve_crest_path(for_favicon=False)
    if not path:
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def crest_img_html(css_class: str = "guild-crest", size: int | None = None) -> str:
    uri = crest_data_uri()
    if not uri:
        return "⚔️"
    style = f' style="width:{size}px;height:{size}px;"' if size else ""
    return f'<img src="{uri}" class="{css_class}" alt="Brasão da guilda"{style} />'


def configure_page() -> None:
    crest = resolve_crest_path(for_favicon=True)
    st.set_page_config(
        page_title="24/7 Farming — Guild Hub",
        page_icon=str(crest) if crest else "⚔️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_dark_theme() -> None:
    """CSS customizado para tema escuro moderno e cards com destaque."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background: linear-gradient(160deg, #0d1117 0%, #161b22 45%, #0d1117 100%);
            color: #e6edf3;
        }

        [data-testid="stSidebar"] {
            background: transparent;
        }

        [data-testid="stSidebar"] > div:first-child {
            background: linear-gradient(
                165deg,
                rgba(18, 23, 31, 0.97) 0%,
                rgba(11, 15, 22, 0.99) 55%,
                rgba(8, 11, 18, 1) 100%
            );
            border-right: 1px solid rgba(88, 166, 255, 0.08);
            box-shadow: 8px 0 32px rgba(0, 0, 0, 0.35);
        }

        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding: 1.35rem 1rem 1.75rem;
        }

        [data-testid="stSidebar"] hr {
            display: none;
        }

        /* ---- Brand header ---- */
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            padding: 1rem 1.05rem;
            margin-bottom: 1.75rem;
            border-radius: 20px;
            background: linear-gradient(
                135deg,
                rgba(88, 166, 255, 0.14) 0%,
                rgba(163, 113, 247, 0.09) 50%,
                rgba(247, 120, 186, 0.06) 100%
            );
            border: 1px solid rgba(88, 166, 255, 0.18);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.22);
        }

        .sidebar-brand-icon {
            flex-shrink: 0;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 16px;
            background: rgba(8, 11, 18, 0.65);
            border: 1px solid rgba(88, 166, 255, 0.22);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
            padding: 3px;
            overflow: hidden;
        }

        .sidebar-brand-icon img,
        .sidebar-brand-icon .guild-crest {
            width: 100%;
            height: 100%;
            object-fit: contain;
            border-radius: 12px;
            display: block;
        }

        .sidebar-brand-title {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(90deg, #e6edf3, #a8c7fa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.2;
        }

        .sidebar-brand-sub {
            font-size: 0.72rem;
            color: #8b949e;
            margin-top: 0.15rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        /* ---- Nav section label ---- */
        .sidebar-nav-label {
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #6e7681;
            margin: 0 0 0.65rem 0.35rem;
        }

        /* ---- Radio → pill navigation ---- */
        [data-testid="stSidebar"] .stRadio > label {
            display: none !important;
        }

        [data-testid="stSidebar"] .stRadio > div {
            gap: 0.35rem;
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label {
            display: flex !important;
            align-items: center !important;
            margin: 0 !important;
            padding: 0.72rem 1rem 0.72rem 0.85rem !important;
            border-radius: 14px !important;
            border: 1px solid transparent !important;
            background: transparent !important;
            color: #9ca3af !important;
            font-weight: 500 !important;
            font-size: 0.9rem !important;
            cursor: pointer !important;
            transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
            width: 100% !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:hover {
            background: rgba(88, 166, 255, 0.07) !important;
            border-color: rgba(88, 166, 255, 0.14) !important;
            color: #e6edf3 !important;
            transform: translateX(3px);
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label[data-checked="true"],
        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:has(input:checked) {
            background: linear-gradient(
                135deg,
                rgba(88, 166, 255, 0.2) 0%,
                rgba(163, 113, 247, 0.12) 100%
            ) !important;
            border-color: rgba(88, 166, 255, 0.32) !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 18px rgba(88, 166, 255, 0.14),
                        inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
            transform: translateX(4px);
        }

        /* Esconde o círculo do radio — visual de menu, não formulário */
        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label > div:first-child {
            display: none !important;
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label > div:last-child {
            margin-left: 0 !important;
            padding-left: 0 !important;
        }

        [data-testid="stSidebar"] .stRadio [role="radiogroup"] > label p {
            margin: 0 !important;
            font-size: 0.9rem !important;
        }

        /* ---- Footer guild card ---- */
        .sidebar-footer {
            margin-top: 2rem;
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: rgba(22, 27, 34, 0.75);
            border: 1px solid rgba(48, 54, 61, 0.7);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }

        .sidebar-footer-label {
            display: block;
            font-size: 0.65rem;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #6e7681;
            margin-bottom: 0.35rem;
        }

        .sidebar-footer-name {
            display: block;
            font-size: 0.95rem;
            font-weight: 600;
            color: #e6edf3;
            margin-bottom: 0.5rem;
        }

        .sidebar-footer-badge {
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 500;
            color: #58a6ff;
            background: rgba(88, 166, 255, 0.1);
            border: 1px solid rgba(88, 166, 255, 0.2);
            border-radius: 999px;
            padding: 0.2rem 0.65rem;
        }

        /* Corrige margin-bottom: -1rem do bloco st.markdown que envolve o footer */
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.sidebar-footer) {
            margin-bottom: 0.85rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.sidebar-footer) + div {
            margin-top: 0.35rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.sidebar-footer) + div [data-testid="stButton"] {
            margin-top: 0 !important;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.sidebar-footer) + div button {
            margin-top: 0 !important;
        }

        .hero-title-row {
            display: flex;
            align-items: center;
            gap: 0.85rem;
            margin-bottom: 0.25rem;
        }

        .hero-crest {
            width: 58px;
            height: 58px;
            object-fit: contain;
            border-radius: 12px;
            flex-shrink: 0;
            filter: drop-shadow(0 4px 14px rgba(0, 0, 0, 0.35));
        }

        .hero-title {
            font-size: 2.8rem;
            font-weight: 700;
            background: linear-gradient(90deg, #58a6ff, #a371f7, #f778ba);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.25rem;
        }

        .hero-subtitle {
            color: #8b949e;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            text-align: center;
            transition: border-color 0.2s;
            box-sizing: border-box;
            width: 100%;
        }

        .metric-card:hover {
            border-color: #58a6ff;
        }

        .dashboard-metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin: 0 0 1.5rem 0;
            width: 100%;
        }

        /* Corrige margin-bottom negativo do Streamlit em blocos com metric-card */
        [data-testid="stMarkdownContainer"]:has(.metric-card),
        [data-testid="stMarkdownContainer"]:has(.dashboard-metrics) {
            margin-bottom: 0 !important;
        }

        @media (max-width: 768px) {
            .dashboard-metrics {
                grid-template-columns: 1fr;
                gap: 0.85rem;
                margin-bottom: 1.25rem;
            }

            .metric-card {
                padding: 1rem 1.25rem;
            }

            section.main > div.block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                max-width: 100%;
            }

            .hero-title {
                font-size: 2rem;
            }

            .hero-subtitle {
                font-size: 1rem;
                margin-bottom: 1.5rem;
            }
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #58a6ff;
        }

        .metric-label {
            color: #8b949e;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .defense-card {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 0.75rem;
            height: 100%;
        }

        .defense-card h4 {
            color: #e6edf3;
            margin: 0 0 0.5rem 0;
            font-size: 1rem;
        }

        .defense-badge {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-right: 0.35rem;
        }

        .badge-spd { background: #1f3a5f; color: #58a6ff; }
        .badge-anti { background: #3d1f4a; color: #d2a8ff; }
        .badge-stars { background: #3d2e1f; color: #e3b341; }

        .defense-badge-efficiency {
            display: inline-block;
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            margin: 0 0 0.55rem 0;
            letter-spacing: 0.02em;
        }

        .efficiency-high {
            background: rgba(46, 160, 67, 0.18);
            color: #3fb950;
            border: 1px solid rgba(63, 185, 80, 0.35);
        }

        .efficiency-mid {
            background: rgba(210, 153, 34, 0.15);
            color: #e3b341;
            border: 1px solid rgba(227, 179, 65, 0.35);
        }

        .efficiency-low {
            background: rgba(248, 81, 73, 0.12);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.3);
        }

        .monster-row {
            display: flex;
            gap: 0.5rem;
            margin: 0.75rem 0;
            justify-content: center;
        }

        .monster-portrait {
            flex: 1;
            max-width: 88px;
            text-align: center;
        }

        .monster-portrait img {
            width: 72px;
            height: 72px;
            object-fit: contain;
            background: #0d1117;
            border: 2px solid #30363d;
            border-radius: 10px;
            padding: 4px;
            display: block;
            margin: 0 auto 0.35rem auto;
        }

        .monster-portrait span {
            display: block;
            font-size: 0.72rem;
            color: #8b949e;
            line-height: 1.2;
            word-break: break-word;
        }

        .monster-slot {
            flex: 1;
            background: #0d1117;
            border: 1px dashed #30363d;
            border-radius: 8px;
            padding: 0.5rem;
            text-align: center;
            font-size: 0.8rem;
            color: #c9d1d9;
        }

        div[data-testid="stMetric"] {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 1rem;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #238636, #2ea043);
            border: none;
            font-weight: 600;
        }

        .stButton > button[kind="secondary"] {
            background: #21262d;
            border: 1px solid #30363d;
            color: #e6edf3;
        }

        h1, h2, h3 { color: #e6edf3 !important; }

        .stDataFrame { border-radius: 12px; overflow: hidden; }

        /* ---- Guias e Regras ---- */
        .guide-page-subtitle {
            color: #8b949e;
            font-size: 1.05rem;
            margin: -1rem 0 1.75rem 0;
            max-width: 640px;
            line-height: 1.55;
        }

        .guide-header {
            padding: 1.35rem 1.4rem;
            margin-bottom: 1.25rem;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(33, 38, 45, 0.9), rgba(22, 27, 34, 0.95));
            border: 1px solid rgba(48, 54, 61, 0.8);
        }

        .guide-header-top {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.85rem;
        }

        .guide-header-icon {
            font-size: 2.2rem;
            width: 56px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 16px;
            background: rgba(8, 11, 18, 0.55);
            border: 1px solid rgba(88, 166, 255, 0.15);
        }

        .guide-badge {
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #58a6ff;
            background: rgba(88, 166, 255, 0.12);
            border: 1px solid rgba(88, 166, 255, 0.22);
            border-radius: 999px;
            padding: 0.15rem 0.55rem;
            margin-bottom: 0.3rem;
        }

        .guide-header-title {
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
            color: #e6edf3 !important;
        }

        .guide-intro {
            color: #b1bac4;
            font-size: 0.95rem;
            line-height: 1.65;
            margin: 0;
        }

        .guide-alert {
            display: flex;
            gap: 1rem;
            align-items: flex-start;
            padding: 1.15rem 1.25rem;
            margin-bottom: 1.25rem;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(248, 81, 73, 0.12), rgba(248, 81, 73, 0.04));
            border: 1px solid rgba(248, 81, 73, 0.28);
        }

        .guide-alert-icon { font-size: 1.6rem; line-height: 1; }

        .guide-alert-title {
            font-size: 1rem;
            font-weight: 700;
            color: #ffaba8;
            margin: 0 0 0.35rem 0;
        }

        .guide-alert-text {
            color: #e6edf3;
            font-size: 0.9rem;
            line-height: 1.6;
            margin: 0;
        }

        .guide-strategy-card {
            padding: 1.15rem 1.2rem;
            border-radius: 18px;
            height: 100%;
            border: 1px solid rgba(48, 54, 61, 0.8);
            background: rgba(22, 27, 34, 0.75);
            transition: border-color 0.2s, transform 0.2s;
        }

        .guide-strategy-card:hover {
            transform: translateY(-2px);
        }

        .guide-strategy-card.spd {
            border-color: rgba(88, 166, 255, 0.25);
            background: linear-gradient(160deg, rgba(31, 58, 95, 0.35), rgba(22, 27, 34, 0.8));
        }

        .guide-strategy-card.spd:hover { border-color: rgba(88, 166, 255, 0.45); }

        .guide-strategy-card.tank {
            border-color: rgba(163, 113, 247, 0.25);
            background: linear-gradient(160deg, rgba(61, 31, 74, 0.35), rgba(22, 27, 34, 0.8));
        }

        .guide-strategy-card.tank:hover { border-color: rgba(163, 113, 247, 0.45); }

        .guide-strategy-head {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin-bottom: 0.65rem;
        }

        .guide-strategy-icon { font-size: 1.35rem; }

        .guide-strategy-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: #e6edf3;
            margin: 0;
        }

        .guide-strategy-tag {
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 600;
            border-radius: 999px;
            padding: 0.12rem 0.5rem;
            margin-left: auto;
            color: #8b949e;
            background: rgba(0, 0, 0, 0.25);
        }

        .guide-strategy-text {
            color: #b1bac4;
            font-size: 0.88rem;
            line-height: 1.6;
            margin: 0;
        }

        .guide-goal-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin-bottom: 1.75rem;
        }

        .guide-goals-heading {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #6e7681;
            margin: 0 0 0.65rem 0.15rem;
        }

        @media (max-width: 768px) {
            .guide-goal-row { grid-template-columns: 1fr; }
        }

        .guide-goal-pill {
            text-align: center;
            padding: 0.85rem 0.75rem;
            border-radius: 16px;
            background: rgba(33, 38, 45, 0.8);
            border: 1px solid rgba(48, 54, 61, 0.7);
        }

        .guide-goal-pill .icon { font-size: 1.25rem; margin-bottom: 0.25rem; }

        .guide-goal-pill .label {
            display: block;
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #6e7681;
            margin-bottom: 0.2rem;
        }

        .guide-goal-pill .value {
            display: block;
            font-size: 0.88rem;
            font-weight: 600;
            color: #e6edf3;
            line-height: 1.4;
            word-break: break-word;
        }

        .guide-section-block {
            padding: 1.25rem 1.3rem;
            margin-bottom: 1rem;
            border-radius: 20px;
            border: 1px solid rgba(48, 54, 61, 0.8);
            background: rgba(22, 27, 34, 0.6);
        }

        .guide-section-block.spd { border-left: 3px solid #58a6ff; }
        .guide-section-block.tank { border-left: 3px solid #d2a8ff; }

        .guide-section-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #e6edf3;
            margin: 0 0 0.5rem 0;
        }

        .guide-section-desc {
            color: #8b949e;
            font-size: 0.88rem;
            line-height: 1.55;
            margin: 0 0 1rem 0;
        }

        .guide-examples-label {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #6e7681;
            margin: 0.75rem 0 0.5rem 0;
        }

        .guide-examples-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }

        .guide-example-chip {
            display: inline-block;
            font-size: 0.8rem;
            color: #c9d1d9;
            background: rgba(13, 17, 23, 0.8);
            border: 1px solid rgba(48, 54, 61, 0.9);
            border-radius: 12px;
            padding: 0.45rem 0.75rem;
            line-height: 1.35;
        }

        .guide-example-chip.stars-5 {
            border-color: rgba(227, 179, 65, 0.35);
            background: rgba(61, 46, 31, 0.35);
        }

        .guide-tip {
            display: flex;
            gap: 0.85rem;
            align-items: flex-start;
            padding: 1rem 1.15rem;
            margin-top: 1.25rem;
            border-radius: 16px;
            background: rgba(46, 160, 67, 0.08);
            border: 1px solid rgba(46, 160, 67, 0.22);
        }

        .guide-tip-icon { font-size: 1.25rem; }

        .guide-tip-text {
            color: #b1bac4;
            font-size: 0.9rem;
            line-height: 1.6;
            margin: 0;
        }

        .guide-help-banner {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1.1rem 1.25rem;
            margin-top: 2rem;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(88, 166, 255, 0.1), rgba(163, 113, 247, 0.08));
            border: 1px solid rgba(88, 166, 255, 0.18);
        }

        .guide-help-banner p {
            margin: 0;
            color: #b1bac4;
            font-size: 0.9rem;
            line-height: 1.55;
        }

        [data-testid="stTabs"] button {
            border-radius: 12px 12px 0 0 !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Helpers de cache (alta performance nas leituras)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=30, show_spinner=False)
def cached_guild_config() -> dict:
    return load_guild_config()


@st.cache_data(ttl=30, show_spinner=False)
def cached_membros(apenas_ativos: bool = False) -> pd.DataFrame:
    return load_membros(apenas_ativos)


@st.cache_data(ttl=30, show_spinner=False)
def cached_defesas() -> pd.DataFrame:
    return load_defesas()


def invalidate_cache() -> None:
    cached_guild_config.clear()
    cached_membros.clear()
    cached_defesas.clear()
    cached_monster_images.clear()


@st.cache_data(ttl=86400, show_spinner=False)
def cached_monster_images(monster_names: tuple[str, ...], _version: int = _IMAGE_CACHE_VERSION) -> dict[str, str]:
    """Cache de URLs de imagens SWARFARM (24h)."""
    return resolve_many(list(monster_names))


def _eficiencia_classe(score: float) -> str:
    if score >= 8.0:
        return "efficiency-high"
    if score >= 5.0:
        return "efficiency-mid"
    return "efficiency-low"


def _eficiencia_badge_html(score: float) -> str:
    valor = f"{float(score):.1f}"
    classe = _eficiencia_classe(float(score))
    return (
        f'<span class="defense-badge-efficiency {classe}">'
        f"🎯 Eficiência: {valor}/10</span>"
    )


def _render_monster_portraits(monsters: list[str], image_map: dict[str, str]) -> str:
    slots = []
    for name in monsters:
        url = image_map.get(name, PLACEHOLDER_IMG)
        safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        slots.append(
            f'<div class="monster-portrait">'
            f'<img src="{url}" alt="{safe_name}" loading="lazy" />'
            f"<span>{safe_name}</span></div>"
        )
    return f'<div class="monster-row">{"".join(slots)}</div>'


def _render_html(content: str) -> None:
    """Renderiza HTML sem o parser Markdown tratar blocos como código."""
    if hasattr(st, "html"):
        st.html(content)
    else:
        st.markdown(content, unsafe_allow_html=True)


def _guide_bold(text: str) -> str:
    """Converte **negrito** simples para HTML."""
    import html
    import re

    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _render_guide_header(guide: dict) -> None:
    st.markdown(
        f"""
        <div class="guide-header">
            <div class="guide-header-top">
                <span class="guide-header-icon">{guide["icon"]}</span>
                <div>
                    <span class="guide-badge">{guide["badge"]}</span>
                    <h2 class="guide-header-title">{guide["title"]}</h2>
                </div>
            </div>
            <p class="guide-intro">{guide["intro"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_wgb_guide(guide: dict) -> None:
    alert = guide["alert"]
    st.markdown(
        f"""
        <div class="guide-alert">
            <span class="guide-alert-icon">{alert["icon"]}</span>
            <div>
                <p class="guide-alert-title">{alert["title"]}</p>
                <p class="guide-alert-text">{_guide_bold(alert["text"])}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Como montar suas defesas?")
    st.caption("Use o melhor da sua box — cada defesa precisa de um objetivo claro.")

    col1, col2 = st.columns(2)
    for col, strategy in zip((col1, col2), guide["strategies"]):
        with col:
            st.markdown(
                f"""
                <div class="guide-strategy-card {strategy['variant']}">
                    <div class="guide-strategy-head">
                        <span class="guide-strategy-icon">{strategy["icon"]}</span>
                        <p class="guide-strategy-title">{strategy["title"]}</p>
                        <span class="guide-strategy-tag">{strategy["tag"]}</span>
                    </div>
                    <p class="guide-strategy-text">{strategy["text"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div class="guide-tip">
            <span class="guide-tip-icon">💡</span>
            <p class="guide-tip-text">{_guide_bold(guide["tip"])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_guide_goals(goals: list[dict]) -> None:
    import html as html_module

    if not goals:
        return

    goals_html = "".join(
        f'<div class="guide-goal-pill">'
        f'<div class="icon">{g["icon"]}</div>'
        f'<span class="label">{html_module.escape(g["label"])}</span>'
        f'<span class="value">{html_module.escape(g["value"])}</span>'
        f"</div>"
        for g in goals
    )
    _render_html(
        f'<p class="guide-goals-heading">Metas gerais da guilda</p>'
        f'<div class="guide-goal-row">{goals_html}</div>'
    )


def _render_siege_guide(guide: dict) -> None:
    for section in guide["sections"]:
        chips_4 = "".join(
            f'<span class="guide-example-chip">{ex}</span>' for ex in section["examples_4"]
        )
        chips_5 = "".join(
            f'<span class="guide-example-chip stars-5">{ex}</span>' for ex in section["examples_5"]
        )
        st.markdown(
            f"""
            <div class="guide-section-block {section['variant']}">
                <p class="guide-section-title">{section["icon"]} {section["title"]}</p>
                <p class="guide-section-desc">{section["description"]}</p>
                <p class="guide-examples-label"> 4 ⭐⭐⭐⭐</p>
                <div class="guide-examples-grid">{chips_4}</div>
                <p class="guide-examples-label"> 5 ⭐⭐⭐⭐⭐</p>
                <div class="guide-examples-grid">{chips_5}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="guide-tip">
            <span class="guide-tip-icon">💡</span>
            <p class="guide-tip-text">{_guide_bold(guide["tip"])}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------


def page_dashboard() -> None:
    config = cached_guild_config()
    membros = cached_membros()
    defesas = cached_defesas()

    ativos = len(membros[membros["status"] == "Ativo"]) if not membros.empty else 0
    lideres = len(membros[membros["cargo"].isin(["Líder", "Vice"])]) if not membros.empty else 0

    st.markdown(
        f'<div class="hero-title-row">{crest_img_html("hero-crest")}'
        f'<p class="hero-title">{config.get("nome_guilda", "Guilda")}</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-subtitle">Plataforma oficial de estratégia e gestão — Summoners War</p>',
        unsafe_allow_html=True,
    )

    boas_vindas = config.get("boas_vindas", "")
    if boas_vindas:
        with st.container():
            st.markdown(boas_vindas)

    inativos = len(membros[membros["status"] == "Inativo"]) if not membros.empty else 0
    st.markdown(
        f"""
        <div class="dashboard-metrics">
            <div class="metric-card">
                <div class="metric-value">{ativos}</div>
                <div class="metric-label">Membros Ativos</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{len(defesas)}</div>
                <div class="metric-label">Defesas no Banco</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{lideres}</div>
                <div class="metric-label">Liderança</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{inativos}</div>
                <div class="metric-label">Inativos</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    col_metas, col_links = st.columns([3, 2])

    with col_metas:
        st.subheader("🎯 Metas da Guilda")
        st.markdown(config.get("metas", "_Nenhuma meta definida._"))

    with col_links:
        st.subheader("🔗 Links Rápidos")
        discord_url = config.get("discord_url", "https://discord.gg/exemplo")
        st.link_button("💬 Entrar no Discord", discord_url, use_container_width=True)
        st.caption("Use o menu lateral para acessar Defesas, Membros e o Painel Admin.")

    st.divider()
    st.subheader("📊 Visão Geral dos Membros")
    if not membros.empty:
        st.dataframe(
            membros[membros["status"] == "Ativo"][["nickname", "nome", "cargo"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum membro cadastrado ainda.")


def page_guias_regras() -> None:
    config = cached_guild_config()
    discord_url = config.get("discord_url", "https://discord.gg/exemplo")

    st.markdown('<p class="hero-title">📜 Guias e Regras</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="guide-page-subtitle">'
        "Orientações da guilda para Siege e WGB"
        "</p>",
        unsafe_allow_html=True,
    )

    _render_guide_goals(guides.goals_from_config(config))

    tab_siege, tab_wgb = st.tabs(["🏰 Batalha de Assalto (Siege)", "🌍 Batalha Mundial (WGB)"])

    with tab_siege:
        siege = guides.siege_guide_from_config(config)
        _render_guide_header(siege)
        _render_siege_guide(siege)

    with tab_wgb:
        wgb = guides.wgb_guide_from_config(config)
        _render_guide_header(wgb)
        _render_wgb_guide(wgb)

    st.markdown(
        f"""
        <div class="guide-help-banner">
            <span style="font-size:1.5rem">🤝</span>
            <p>
                <strong style="color:#e6edf3">Ficou com dúvida?</strong>
                Pergunta no Discord antes de cada evento — a galera ajuda a fechar comps.
                Veja também o <strong>Banco de Defesas</strong> com exemplos visuais e ícones dos monstros.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button("💬 Abrir Discord", discord_url, use_container_width=True)


def page_banco_defesas() -> None:
    defesas = cached_defesas()

    st.title("🛡️ Banco de Defesas")
    st.caption("Exemplos oficiais da guilda para Siege e WGB — modo somente leitura.")

    if defesas.empty:
        st.warning("Nenhuma defesa cadastrada. O administrador pode adicionar no Painel Administrativo.")
        return

    monster_names = tuple(unique_monsters_from_defesas(defesas))
    image_map = cached_monster_images(monster_names)

    filtro_tipo = st.selectbox("Filtrar por tipo", ["Todos"] + TIPOS_DEFESA, key="filtro_tipo_defesa")
    filtro_estrelas = st.selectbox("Filtrar por estrelas", ["Todos"] + ESTRELAS, key="filtro_estrelas_defesa")

    df_filtrado = defesas.copy()
    if filtro_tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo"] == filtro_tipo]
    if filtro_estrelas != "Todos":
        df_filtrado = df_filtrado[df_filtrado["estrelas"] == filtro_estrelas]

    st.markdown(f"**{len(df_filtrado)}** defesa(s) encontrada(s)")

    cols_per_row = 3
    for i in range(0, len(df_filtrado), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(df_filtrado):
                break
            row = df_filtrado.iloc[idx]
            badge_class = "badge-spd" if row["tipo"] == "Conteste de SPD" else "badge-anti"
            eficiencia = float(row.get("eficiencia", 5.0))
            eficiencia_html = _eficiencia_badge_html(eficiencia)
            monsters = [row["monstro1"], row["monstro2"], row["monstro3"]]
            portraits_html = _render_monster_portraits(monsters, image_map)
            notas = (row["notas"] or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            with col:
                st.markdown(
                    f"""
                    <div class="defense-card">
                        <h4>{row['nome']}</h4>
                        {eficiencia_html}
                        <span class="defense-badge {badge_class}">{row['tipo']}</span>
                        <span class="defense-badge badge-stars">{row['estrelas']}</span>
                        {portraits_html}
                        <p style="color:#8b949e; font-size:0.85rem; margin:0;">{notas}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()
    with st.expander("📋 Ver tabela completa"):
        st.dataframe(df_filtrado.drop(columns=["id"]), use_container_width=True, hide_index=True)


def page_speed_calculator() -> None:
    render_speed_calculator()


def page_membros() -> None:
    membros = cached_membros()

    st.title("👥 Membros da Guilda")
    st.caption("Lista de jogadores com nickname (IGN) e cargos.")

    if membros.empty:
        st.warning("Nenhum membro cadastrado.")
        return

    filtro_status = st.radio("Exibir", ["Todos", "Ativos", "Inativos"], horizontal=True, key="filtro_status_membros")

    df = membros.copy()
    if filtro_status == "Ativos":
        df = df[df["status"] == "Ativo"]
    elif filtro_status == "Inativos":
        df = df[df["status"] == "Inativo"]

    col1, col2 = st.columns(2)
    col1.metric("Total exibido", len(df))
    col2.metric("Líderes/Vices", len(df[df["cargo"].isin(["Líder", "Vice"])]))

    st.dataframe(
        df.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "nickname": st.column_config.TextColumn("Nickname (IGN)", width="medium"),
            "nome": st.column_config.TextColumn("Nome", width="medium"),
            "cargo": st.column_config.TextColumn("Cargo", width="small"),
            "status": st.column_config.TextColumn("Status", width="small"),
        },
    )


def _admin_crud_membros() -> None:
    st.subheader("👥 Gerenciar Membros")
    membros = cached_membros()

    tab_criar, tab_editar, tab_deletar = st.tabs(["➕ Criar", "✏️ Editar", "🗑️ Deletar"])

    with tab_criar:
        with st.form("form_criar_membro", clear_on_submit=True):
            nickname = st.text_input("Nickname (IGN)", placeholder="Ex: SummonerX")
            nome = st.text_input("Nome", placeholder="Ex: Lucas Silva")
            cargo = st.selectbox("Cargo", CARGOS)
            status = st.selectbox("Status", STATUS_OPCOES)
            if st.form_submit_button("Adicionar Membro", type="primary", use_container_width=True):
                if not nickname.strip():
                    st.error("Informe o nickname (IGN) do jogador.")
                elif not nome.strip():
                    st.error("Informe o nome do jogador.")
                else:
                    try:
                        create_membro(nome.strip(), nickname.strip(), cargo, status)
                        invalidate_cache()
                        st.success(f"Membro **{nickname.strip()}** adicionado!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Erro ao criar: {exc}")

    with tab_editar:
        if membros.empty:
            st.info("Nenhum membro para editar.")
        else:
            opcoes = {
                f"{r['nickname']} — {r['nome']} ({r['cargo']})": r["id"] for _, r in membros.iterrows()
            }
            selecionado = st.selectbox("Selecione o membro", list(opcoes.keys()), key="edit_membro_sel")
            membro_id = opcoes[selecionado]
            atual = membros[membros["id"] == membro_id].iloc[0]

            with st.form("form_editar_membro"):
                nickname = st.text_input("Nickname (IGN)", value=atual.get("nickname", "") or "")
                nome = st.text_input("Nome", value=atual["nome"])
                cargo = st.selectbox("Cargo", CARGOS, index=CARGOS.index(atual["cargo"]))
                status = st.selectbox("Status", STATUS_OPCOES, index=STATUS_OPCOES.index(atual["status"]))
                if st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                    if not nickname.strip():
                        st.error("Informe o nickname (IGN).")
                    elif not nome.strip():
                        st.error("Informe o nome.")
                    else:
                        try:
                            update_membro(membro_id, nome.strip(), nickname.strip(), cargo, status)
                            invalidate_cache()
                            st.success("Membro atualizado!")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao atualizar: {exc}")

    with tab_deletar:
        if membros.empty:
            st.info("Nenhum membro para deletar.")
        else:
            opcoes = {
                f"{r['nickname']} — {r['nome']} (ID {r['id']})": r["id"] for _, r in membros.iterrows()
            }
            selecionado = st.selectbox("Membro a remover", list(opcoes.keys()), key="del_membro_sel")
            membro_id = opcoes[selecionado]
            st.warning("Esta ação é irreversível.")
            if st.button("Confirmar Exclusão", type="primary", key="btn_del_membro"):
                delete_membro(membro_id)
                invalidate_cache()
                st.success("Membro removido.")
                st.rerun()


def _admin_crud_defesas() -> None:
    st.subheader("🛡️ Gerenciar Defesas")
    defesas = cached_defesas()

    tab_criar, tab_editar, tab_deletar = st.tabs(["➕ Criar", "✏️ Editar", "🗑️ Deletar"])

    with tab_criar:
        with st.form("form_criar_defesa", clear_on_submit=True):
            nome = st.text_input("Nome da defesa", placeholder="Ex: Ragdoll + Giana + Seara")
            tipo = st.selectbox("Tipo", TIPOS_DEFESA)
            estrelas = st.radio("Estrelas", ESTRELAS, horizontal=True)
            eficiencia = st.number_input(
                "Eficiência",
                min_value=0.0,
                max_value=10.0,
                step=0.1,
                value=5.0,
                format="%.1f",
                help="Nota de 0 a 10 para ranqueamento interno das defesas.",
            )
            c1, c2, c3 = st.columns(3)
            monstro1 = c1.text_input("Monstro 1 (Lead)")
            monstro2 = c2.text_input("Monstro 2")
            monstro3 = c3.text_input("Monstro 3")
            notas = st.text_area("Notas / Estratégia", placeholder="Descrição breve da defesa...")
            if st.form_submit_button("Adicionar Defesa", type="primary", use_container_width=True):
                if not all([nome.strip(), monstro1.strip(), monstro2.strip(), monstro3.strip()]):
                    st.error("Preencha nome e os 3 monstros.")
                else:
                    create_defesa(
                        nome.strip(),
                        tipo,
                        estrelas,
                        monstro1.strip(),
                        monstro2.strip(),
                        monstro3.strip(),
                        notas,
                        float(eficiencia),
                    )
                    invalidate_cache()
                    st.success("Defesa adicionada!")
                    st.rerun()

    with tab_editar:
        if defesas.empty:
            st.info("Nenhuma defesa para editar.")
        else:
            opcoes = {
                f"{r['nome']} [{r['estrelas']}] — {float(r.get('eficiencia', 5.0)):.1f}/10": r["id"]
                for _, r in defesas.iterrows()
            }
            selecionado = st.selectbox("Selecione a defesa", list(opcoes.keys()), key="edit_defesa_sel")
            defesa_id = opcoes[selecionado]
            atual = defesas[defesas["id"] == defesa_id].iloc[0]

            with st.form("form_editar_defesa"):
                nome = st.text_input("Nome", value=atual["nome"])
                tipo = st.selectbox("Tipo", TIPOS_DEFESA, index=TIPOS_DEFESA.index(atual["tipo"]))
                estrelas = st.radio("Estrelas", ESTRELAS, index=ESTRELAS.index(atual["estrelas"]), horizontal=True)
                eficiencia = st.number_input(
                    "Eficiência",
                    min_value=0.0,
                    max_value=10.0,
                    step=0.1,
                    value=float(atual.get("eficiencia", 5.0)),
                    format="%.1f",
                )
                c1, c2, c3 = st.columns(3)
                monstro1 = c1.text_input("Monstro 1", value=atual["monstro1"])
                monstro2 = c2.text_input("Monstro 2", value=atual["monstro2"])
                monstro3 = c3.text_input("Monstro 3", value=atual["monstro3"])
                notas = st.text_area("Notas", value=atual["notas"] or "")
                if st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                    update_defesa(
                        defesa_id,
                        nome.strip(),
                        tipo,
                        estrelas,
                        monstro1.strip(),
                        monstro2.strip(),
                        monstro3.strip(),
                        notas,
                        float(eficiencia),
                    )
                    invalidate_cache()
                    st.success("Defesa atualizada!")
                    st.rerun()

    with tab_deletar:
        if defesas.empty:
            st.info("Nenhuma defesa para deletar.")
        else:
            opcoes = {f"{r['nome']} (ID {r['id']})": r["id"] for _, r in defesas.iterrows()}
            selecionado = st.selectbox("Defesa a remover", list(opcoes.keys()), key="del_defesa_sel")
            defesa_id = opcoes[selecionado]
            st.warning("Esta ação é irreversível.")
            if st.button("Confirmar Exclusão", type="primary", key="btn_del_defesa"):
                delete_defesa(defesa_id)
                invalidate_cache()
                st.success("Defesa removida.")
                st.rerun()


def _admin_config_guilda() -> None:
    st.subheader("⚙️ Configurações da Guilda")
    config = cached_guild_config()

    st.caption(
        "As alterações em **Metas**, **WGB** e **Siege** são salvas e refletidas automaticamente "
        "na página **Guias e Regras** (layout amigável). Use emojis como 🚨 ⚡ 🧱 💡 🛡️ para organizar seções."
    )

    with st.form("form_config_guilda"):
        nome_guilda = st.text_input("Nome da Guilda", value=config.get("nome_guilda", ""))
        discord_url = st.text_input("URL do Discord", value=config.get("discord_url", ""))
        boas_vindas = st.text_area("Boas-vindas (Dashboard)", value=config.get("boas_vindas", ""), height=120)
        metas = st.text_area(
            "Metas (Dashboard + pills do Siege)",
            value=config.get("metas", ""),
            height=120,
            help="Use bullets (- item) para preencher os cards de meta na aba Siege.",
        )
        wgb_rules = st.text_area(
            "Regras WGB",
            value=config.get("wgb_rules", ""),
            height=220,
            help="Texto livre com emojis 🚨 ⚡ 🧱 💡 para alertas, estratégias e dicas.",
        )
        siege_rules = st.text_area(
            "Regras Siege",
            value=config.get("siege_rules", ""),
            height=280,
            help="Use 🛡️ 1. Defesa SPD / 🛡️ 2. Defesa Tank e linhas Exemplo 4⭐ / Exemplo 5⭐.",
        )
        if st.form_submit_button("Salvar Configurações", type="primary", use_container_width=True):
            update_guild_config(nome_guilda, discord_url, boas_vindas, metas, siege_rules, wgb_rules)
            invalidate_cache()
            st.success("Configurações salvas!")
            st.rerun()


def page_admin() -> None:
    require_admin()
    st.title("⚙️ Painel Administrativo")
    st.caption("CRUD completo para membros, defesas e configurações da guilda.")

    secao = st.radio(
        "Seção",
        ["Configurações da Guilda", "Membros", "Defesas"],
        horizontal=True,
        key="admin_secao",
    )

    st.divider()

    if secao == "Configurações da Guilda":
        _admin_config_guilda()
    elif secao == "Membros":
        _admin_crud_membros()
    else:
        _admin_crud_defesas()


# ---------------------------------------------------------------------------
# Roteador principal
# ---------------------------------------------------------------------------

ROTEADOR = {
    "🏠 Dashboard": page_dashboard,
    "📜 Guias e Regras": page_guias_regras,
    "🛡️ Banco de Defesas": page_banco_defesas,
    "⚡ Calculadora de Speed Tuning": page_speed_calculator,
    "👥 Membros da Guilda": page_membros,
    PAGE_ADMIN: page_admin,
}


def inject_login_layout() -> None:
    """Esconde a sidebar na tela de identificação."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        section.main > div.block-container {
            max-width: 520px;
            padding-top: 2.5rem;
        }
        .login-gateway {
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .login-gateway .login-crest {
            width: 88px;
            height: 88px;
            margin: 0 auto 1rem;
            border-radius: 22px;
            background: rgba(8, 11, 18, 0.65);
            border: 1px solid rgba(88, 166, 255, 0.22);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 8px;
        }
        .login-gateway h1 {
            font-size: 1.65rem;
            margin: 0 0 0.35rem;
            background: linear-gradient(90deg, #e6edf3, #a8c7fa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .login-gateway p {
            color: #8b949e;
            margin: 0;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _tentativas_pin_bloqueadas() -> bool:
    return int(st.session_state.get("pin_attempts", 0)) >= MAX_PIN_ATTEMPTS


def _login_membro_existente(nickname: str, pin: str) -> None:
    if _tentativas_pin_bloqueadas():
        st.error(f"Muitas tentativas incorretas. Aguarde e recarregue a página.")
        return

    membro = get_membro_by_nickname(nickname)
    if not membro:
        st.error("Membro não encontrado.")
        return
    if membro.get("status") != "Ativo":
        st.error("Este membro está inativo. Fale com a liderança.")
        return

    cargo = membro.get("cargo", "Membro")
    if is_admin_cargo(cargo):
        admin_pin = get_admin_pin()
        if admin_pin is None:
            st.error(
                "PIN de administração não configurado. "
                "Defina `admin_pin` em `.streamlit/secrets.toml` antes do deploy."
            )
            return
        if pin != admin_pin:
            st.session_state.pin_attempts = int(st.session_state.get("pin_attempts", 0)) + 1
            restantes = MAX_PIN_ATTEMPTS - st.session_state.pin_attempts
            if restantes <= 0:
                st.error("PIN incorreto. Limite de tentativas atingido — recarregue a página.")
            else:
                st.error(f"PIN incorreto. {restantes} tentativa(s) restante(s).")
            return
        complete_login(membro, ROLE_ADMIN)
    else:
        complete_login(membro, ROLE_MEMBER)

    st.rerun()


def _login_novo_membro(nickname: str) -> None:
    try:
        membro = register_membro_onboarding(nickname)
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Não foi possível concluir o cadastro. Tente novamente.")
        return

    complete_login(membro, ROLE_MEMBER)
    st.rerun()


def render_login_gateway() -> None:
    """Tela central de identificação (sem sidebar nem páginas internas)."""
    inject_login_layout()

    crest_html = crest_img_html("guild-crest", size=72)
    st.markdown(
        f"""
        <div class="login-gateway">
            <div class="login-crest">{crest_html}</div>
            <h1>24/7 Farming — Guild Hub</h1>
            <p>Identifique-se para acessar a plataforma da guilda.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_existente, tab_novo = st.tabs(["Já sou da Guilda", "Sou Novo Aqui"])

    with tab_existente:
        nicknames = load_nicknames_ativos()
        if not nicknames:
            st.info("Nenhum membro ativo cadastrado ainda. Use a aba **Sou Novo Aqui**.")
        else:
            nickname = st.selectbox(
                "Seu nickname (IGN)",
                nicknames,
                key="login_nickname_existente",
            )
            membro_sel = get_membro_by_nickname(nickname)
            pin = ""
            if membro_sel and is_admin_cargo(membro_sel.get("cargo", "")):
                st.caption("Liderança: informe o PIN da guilda para continuar.")
                pin = st.text_input(
                    "PIN da liderança",
                    type="password",
                    key="login_pin",
                    disabled=_tentativas_pin_bloqueadas(),
                )

            if st.button(
                "Entrar",
                type="primary",
                use_container_width=True,
                key="login_btn_existente",
                disabled=not nicknames or _tentativas_pin_bloqueadas(),
            ):
                _login_membro_existente(nickname, pin)

    with tab_novo:
        st.caption("Cadastro automático como **Membro** · status **Ativo**.")
        novo_nick = st.text_input(
            "Seu nickname no jogo (IGN)",
            placeholder="Ex.: Japoneix28",
            key="login_nickname_novo",
        ).strip()

        if st.button("Entrar na Guilda", type="primary", use_container_width=True, key="login_btn_novo"):
            if not novo_nick:
                st.warning("Informe seu nickname.")
            else:
                _login_novo_membro(novo_nick)


def render_sidebar() -> str:
    """Menu lateral com visual moderno em pills."""
    crest_html = crest_img_html("guild-crest")
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">{crest_html}</div>
            <div>
                <div class="sidebar-brand-title">24/7 Farming - Guild Hub</div>
                <div class="sidebar-brand-sub">Summoners War</div>
            </div>
        </div>
        <p class="sidebar-nav-label">Menu</p>
        """,
        unsafe_allow_html=True,
    )

    paginas = paginas_para_usuario()
    nav_atual = st.session_state.get("nav_pagina")
    if nav_atual not in paginas:
        st.session_state.nav_pagina = paginas[0]

    pagina = st.radio("Menu", paginas, label_visibility="collapsed", key="nav_pagina")

    nick = st.session_state.get("nickname") or "—"
    cargo = st.session_state.get("cargo") or ""
    role_badge = "Liderança" if is_admin() else "Membro"
    safe_nick = (
        str(nick).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    safe_cargo = (
        str(cargo).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    st.markdown(
        f"""
        <div class="sidebar-footer">
            <span class="sidebar-footer-label">Conectado como</span>
            <span class="sidebar-footer-name">{safe_nick}</span>
            <span class="sidebar-footer-badge">● {role_badge}{f" · {safe_cargo}" if safe_cargo else ""}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Sair", use_container_width=True, key="btn_logout"):
        logout()
        st.rerun()

    return pagina


def main() -> None:
    configure_page()
    inject_dark_theme()
    init_session_auth()

    try:
        init_db()
    except DatabaseConnectionError as exc:
        st.error("Não foi possível conectar ao banco PostgreSQL (Supabase).")
        st.code(str(exc))
        st.markdown("**Como corrigir nos Secrets do Streamlit:**")
        for hint in connection_setup_hints():
            st.markdown(f"- {hint}")
        st.markdown(
            "**Alternativa (senha com caracteres especiais):** use campos separados "
            "em vez de `DATABASE_URL` — veja `.streamlit/secrets.toml.example`."
        )
        return

    if not is_logged_in():
        render_login_gateway()
        return

    with st.sidebar:
        pagina = render_sidebar()

    if pagina == PAGE_ADMIN and not is_admin():
        st.error("Acesso restrito à liderança da guilda.")
        pagina = "🏠 Dashboard"

    ROTEADOR[pagina]()


if __name__ == "__main__":
    main()
