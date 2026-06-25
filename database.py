"""
Camada de persistência — SQLite (local) ou PostgreSQL/Supabase (produção).

Configure DATABASE_URL nos secrets do Streamlit ou na variável de ambiente.
Sem DATABASE_URL, usa data/guilda.db (desenvolvimento local).
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pandas as pd

from content import (
    CONTENT_VERSION,
    get_boas_vindas,
    get_defesas_seed,
    get_metas,
    get_siege_rules,
    get_wgb_rules,
)
from guides import build_guides_payload

DB_PATH = Path(__file__).parent / "data" / "guilda.db"

CARGOS = ["Líder", "Vice", "Membro"]
ADMIN_CARGOS = ("Líder", "Vice")
STATUS_OPCOES = ["Ativo", "Inativo"]
TIPOS_DEFESA = ["Conteste de SPD", "Anti-Cleave"]
ESTRELAS = ["4⭐", "5⭐"]

_USE_POSTGRES: bool | None = None
_DATABASE_URL: str | None = None
_DB_CONFIG: dict[str, Any] | None = None
_DB_CONFIG_LOADED = False

SUPABASE_PROJECT_REF = "cugzgfbbtugeleotqwuc"


class DatabaseConnectionError(RuntimeError):
    """Erro de conexão sem expor senha (seguro para exibir no Streamlit Cloud)."""


def _secret_value(*keys: str) -> str | None:
    for key in keys:
        env_val = os.environ.get(key, "").strip()
        if env_val:
            return env_val
    try:
        import streamlit as st

        for key in keys:
            if key in st.secrets:
                value = str(st.secrets[key]).strip()
                if value:
                    return value
        if "database" in st.secrets:
            section = st.secrets["database"]
            for key in keys:
                if key in section:
                    value = str(section[key]).strip()
                    if value:
                        return value
    except Exception:
        pass
    return None


def _resolve_database_url() -> str | None:
    return _secret_value("DATABASE_URL", "database_url")


def _resolve_db_config() -> dict[str, Any] | None:
    """Monta config a partir de DATABASE_URL ou campos separados nos secrets."""
    url = _resolve_database_url()
    if url:
        url = _normalize_database_url(url)
        parsed = urlparse(url)
        if not parsed.hostname:
            return None
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "dbname": (parsed.path or "/postgres").lstrip("/") or "postgres",
            "source": "DATABASE_URL",
        }

    host = _secret_value("DB_HOST", "db_host")
    password = _secret_value("DB_PASSWORD", "db_password")
    if not host or not password:
        return None

    port_raw = _secret_value("DB_PORT", "db_port") or "6543"
    return {
        "host": host,
        "port": int(port_raw),
        "user": _secret_value("DB_USER", "db_user") or f"postgres.{SUPABASE_PROJECT_REF}",
        "password": password,
        "dbname": _secret_value("DB_NAME", "db_name") or "postgres",
        "source": "DB_HOST/DB_PASSWORD",
    }


def _load_db_config() -> dict[str, Any] | None:
    global _DB_CONFIG, _DATABASE_URL, _USE_POSTGRES, _DB_CONFIG_LOADED
    if _DB_CONFIG_LOADED:
        return _DB_CONFIG
    _DB_CONFIG_LOADED = True
    _DB_CONFIG = _resolve_db_config()
    if _DB_CONFIG:
        _DATABASE_URL = _resolve_database_url()
        _USE_POSTGRES = True
    else:
        _DATABASE_URL = None
        _USE_POSTGRES = False
    return _DB_CONFIG


def describe_connection_target() -> str:
    """Resumo seguro da config (sem senha) para diagnóstico na UI."""
    if not uses_postgres():
        return f"Backend: SQLite ({DB_PATH})"

    cfg = _load_db_config()
    if not cfg:
        return "Backend: PostgreSQL — DATABASE_URL ou DB_HOST/DB_PASSWORD não configurados."

    lines = [
        "Backend: PostgreSQL (Supabase)",
        f"Origem da config: {cfg.get('source', '?')}",
        f"Host: {cfg.get('host', '?')}",
        f"Porta: {cfg.get('port', '?')}",
        f"Usuário: {cfg.get('user', '?')}",
        f"Banco: {cfg.get('dbname', '?')}",
        f"Senha: {'configurada' if cfg.get('password') else 'AUSENTE'}",
        "SSL: require",
    ]

    host = str(cfg.get("host", ""))
    user = str(cfg.get("user", ""))
    port = int(cfg.get("port", 0))

    if host.startswith("db.") and host.endswith(".supabase.co"):
        lines.append(
            "⚠ Host direto (db.*.supabase.co) — use *.pooler.supabase.com no Streamlit Cloud."
        )
    if "pooler.supabase.com" in host and user == "postgres":
        lines.append(
            f"⚠ Usuário deve ser postgres.{SUPABASE_PROJECT_REF}, não apenas postgres."
        )
    if "pooler.supabase.com" in host and port == 5432 and user.startswith("postgres."):
        lines.append("Dica: Session pooler (5432) — OK para este app.")
    if "pooler.supabase.com" in host and port == 6543:
        lines.append("Dica: Transaction pooler (6543) — OK para este app.")

    return "\n".join(lines)


def connection_setup_hints() -> list[str]:
    """Passos para corrigir conexão no Streamlit Cloud."""
    return [
        "Supabase → Connect → Connection pooling → copie host, porta e usuário.",
        "Use host *.pooler.supabase.com (não db.*.supabase.co).",
        f"Usuário: postgres.{SUPABASE_PROJECT_REF}",
        "Porta 6543 (Transaction) ou 5432 (Session) no pooler.",
        "Se a senha tiver @ # ! etc., use DB_PASSWORD separado em vez de DATABASE_URL.",
        "Supabase → Project Settings → Database → Network: Allow all IP addresses.",
    ]


def uses_postgres() -> bool:
    global _USE_POSTGRES
    if _USE_POSTGRES is None:
        _load_db_config()
    return bool(_USE_POSTGRES)


def get_backend_label() -> str:
    if uses_postgres():
        return "PostgreSQL (Supabase)"
    return f"SQLite ({DB_PATH})"


def _adapt_sql(sql: str) -> str:
    if uses_postgres():
        sql = sql.replace("?", "%s")
        # psycopg2 interpreta % como placeholder — escapa % literais (ex.: LIKE 'Exemplo 5%')
        sql = re.sub(r"%(?!s)", "%%", sql)
    return sql


def _adapt_nickname_lookup(sql: str) -> str:
    if uses_postgres():
        return sql.replace("nickname = ? COLLATE NOCASE", "LOWER(nickname) = LOWER(?)")
    return sql


def _normalize_database_url(url: str) -> str:
    """Remove aspas acidentais e garante SSL (obrigatório no Supabase)."""
    url = url.strip().strip('"').strip("'")
    if "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


def get_connection() -> Any:
    if uses_postgres():
        import psycopg2

        cfg = _load_db_config()
        if not cfg:
            raise DatabaseConnectionError("DATABASE_URL ou DB_HOST/DB_PASSWORD não configurados.")

        try:
            return psycopg2.connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                dbname=cfg["dbname"],
                sslmode="require",
                connect_timeout=15,
            )
        except psycopg2.OperationalError as exc:
            safe_msg = str(exc).split("connection to server")[0].strip() or "Falha na conexão"
            raise DatabaseConnectionError(
                f"{safe_msg}\n\n{describe_connection_target()}"
            ) from exc

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def db_execute(conn: Any, sql: str, params: tuple | list = ()) -> Any:
    sql = _adapt_sql(sql)
    if uses_postgres():
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


def db_executemany(conn: Any, sql: str, params_seq: list[tuple]) -> None:
    sql = _adapt_sql(sql)
    if uses_postgres():
        cur = conn.cursor()
        cur.executemany(sql, params_seq)
        return
    conn.executemany(sql, params_seq)


def db_fetchone(cursor: Any) -> tuple | None:
    row = cursor.fetchone()
    return row


def db_fetchall(cursor: Any) -> list[tuple]:
    return cursor.fetchall()


def _table_columns(conn: Any, table: str) -> set[str]:
    if uses_postgres():
        cur = db_execute(
            conn,
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table,),
        )
        return {row[0] for row in db_fetchall(cur)}
    cur = db_execute(conn, f"PRAGMA table_info({table})")
    return {row[1] for row in db_fetchall(cur)}


def _guides_json_from_text(wgb_rules: str, siege_rules: str, metas: str) -> tuple[str, str]:
    return build_guides_payload(wgb_rules, siege_rules, metas)


def _create_schema_sqlite(conn: Any) -> None:
    db_execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS guild_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome_guilda TEXT NOT NULL DEFAULT 'Guilda 247',
            discord_url TEXT DEFAULT 'https://discord.gg/exemplo',
            boas_vindas TEXT,
            metas TEXT,
            siege_rules TEXT,
            wgb_rules TEXT,
            wgb_guide_json TEXT,
            siege_guide_json TEXT,
            content_version INTEGER DEFAULT 0
        )
        """,
    )
    db_execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS membros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            nickname TEXT NOT NULL DEFAULT '',
            cargo TEXT NOT NULL CHECK (cargo IN ('Líder', 'Vice', 'Membro')),
            status TEXT NOT NULL CHECK (status IN ('Ativo', 'Inativo'))
        )
        """,
    )
    db_execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS defesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('Conteste de SPD', 'Anti-Cleave')),
            estrelas TEXT NOT NULL CHECK (estrelas IN ('4⭐', '5⭐')),
            monstro1 TEXT NOT NULL,
            monstro2 TEXT NOT NULL,
            monstro3 TEXT NOT NULL,
            notas TEXT DEFAULT '',
            eficiencia REAL NOT NULL DEFAULT 5.0
        )
        """,
    )


def _create_schema_postgres(conn: Any) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS guild_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome_guilda TEXT NOT NULL DEFAULT 'Guilda 247',
            discord_url TEXT DEFAULT 'https://discord.gg/exemplo',
            boas_vindas TEXT,
            metas TEXT,
            siege_rules TEXT,
            wgb_rules TEXT,
            wgb_guide_json TEXT,
            siege_guide_json TEXT,
            content_version INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS membros (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE,
            nickname TEXT NOT NULL DEFAULT '',
            cargo TEXT NOT NULL CHECK (cargo IN ('Líder', 'Vice', 'Membro')),
            status TEXT NOT NULL CHECK (status IN ('Ativo', 'Inativo'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS defesas (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('Conteste de SPD', 'Anti-Cleave')),
            estrelas TEXT NOT NULL CHECK (estrelas IN ('4⭐', '5⭐')),
            monstro1 TEXT NOT NULL,
            monstro2 TEXT NOT NULL,
            monstro3 TEXT NOT NULL,
            notas TEXT DEFAULT '',
            eficiencia DOUBLE PRECISION NOT NULL DEFAULT 5.0
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_membros_nickname
        ON membros (LOWER(nickname))
        """,
    ]
    for sql in statements:
        db_execute(conn, sql)


def _migrate_sqlite(conn: Any) -> None:
    colunas = _table_columns(conn, "guild_config")
    if "boas_vindas" not in colunas:
        db_execute(conn, "ALTER TABLE guild_config ADD COLUMN boas_vindas TEXT")
    if "content_version" not in colunas:
        db_execute(conn, "ALTER TABLE guild_config ADD COLUMN content_version INTEGER DEFAULT 0")
    if "wgb_guide_json" not in colunas:
        db_execute(conn, "ALTER TABLE guild_config ADD COLUMN wgb_guide_json TEXT")
    if "siege_guide_json" not in colunas:
        db_execute(conn, "ALTER TABLE guild_config ADD COLUMN siege_guide_json TEXT")

    colunas_membros = _table_columns(conn, "membros")
    if "nickname" not in colunas_membros:
        db_execute(conn, "ALTER TABLE membros ADD COLUMN nickname TEXT NOT NULL DEFAULT ''")
        db_execute(conn, "UPDATE membros SET nickname = nome WHERE COALESCE(nickname, '') = ''")
    if "foco" in colunas_membros:
        db_execute(
            conn,
            """
            CREATE TABLE membros_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                nickname TEXT NOT NULL DEFAULT '',
                cargo TEXT NOT NULL CHECK (cargo IN ('Líder', 'Vice', 'Membro')),
                status TEXT NOT NULL CHECK (status IN ('Ativo', 'Inativo'))
            )
            """,
        )
        db_execute(
            conn,
            """
            INSERT INTO membros_new (id, nome, nickname, cargo, status)
            SELECT id, nome, COALESCE(nickname, ''), cargo, status FROM membros
            """,
        )
        db_execute(conn, "DROP TABLE membros")
        db_execute(conn, "ALTER TABLE membros_new RENAME TO membros")

    db_execute(
        conn,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_membros_nickname "
        "ON membros(nickname COLLATE NOCASE)",
    )

    colunas_defesas = _table_columns(conn, "defesas")
    if "eficiencia" not in colunas_defesas:
        db_execute(conn, "ALTER TABLE defesas ADD COLUMN eficiencia REAL NOT NULL DEFAULT 5.0")
        db_execute(conn, "UPDATE defesas SET eficiencia = 5.0 WHERE eficiencia IS NULL")


def _seed_and_sync(conn: Any) -> None:
    versao_anterior = 0
    cur = db_execute(conn, "SELECT COUNT(*) FROM guild_config")
    if db_fetchone(cur)[0] == 0:
        wgb_md = get_wgb_rules()
        siege_md = get_siege_rules()
        metas_md = get_metas()
        wgb_json, siege_json = _guides_json_from_text(wgb_md, siege_md, metas_md)
        db_execute(
            conn,
            """
            INSERT INTO guild_config (
                id, nome_guilda, discord_url, boas_vindas, metas,
                siege_rules, wgb_rules, wgb_guide_json, siege_guide_json, content_version
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Guilda 247",
                "https://discord.gg/exemplo",
                get_boas_vindas(),
                metas_md,
                siege_md,
                wgb_md,
                wgb_json,
                siege_json,
                CONTENT_VERSION,
            ),
        )
    else:
        cur = db_execute(conn, "SELECT COALESCE(content_version, 0) FROM guild_config WHERE id = 1")
        row = db_fetchone(cur)
        versao_anterior = row[0] if row else 0
        if versao_anterior < CONTENT_VERSION:
            wgb_md = get_wgb_rules()
            siege_md = get_siege_rules()
            metas_md = get_metas()
            wgb_json, siege_json = _guides_json_from_text(wgb_md, siege_md, metas_md)
            db_execute(
                conn,
                """
                UPDATE guild_config
                SET boas_vindas = ?, metas = ?, siege_rules = ?, wgb_rules = ?,
                    wgb_guide_json = ?, siege_guide_json = ?, content_version = ?
                WHERE id = 1
                """,
                (
                    get_boas_vindas(),
                    metas_md,
                    siege_md,
                    wgb_md,
                    wgb_json,
                    siege_json,
                    CONTENT_VERSION,
                ),
            )

    cur = db_execute(conn, "SELECT wgb_rules, siege_rules, metas FROM guild_config WHERE id = 1")
    guide_row = db_fetchone(cur)
    if guide_row:
        wgb_json, siege_json = _guides_json_from_text(
            guide_row[0] or "",
            guide_row[1] or "",
            guide_row[2] or "",
        )
        db_execute(
            conn,
            """
            UPDATE guild_config
            SET wgb_guide_json = ?, siege_guide_json = ?
            WHERE id = 1
            """,
            (wgb_json, siege_json),
        )

    cur = db_execute(conn, "SELECT COUNT(*) FROM membros")
    if db_fetchone(cur)[0] == 0:
        seed_membros = [
            ("Lucas", "Lucas247", "Líder", "Ativo"),
            ("Rafael", "RafaSW", "Vice", "Ativo"),
            ("Ana", "AnaPvP", "Membro", "Ativo"),
            ("Bruno", "BrunoFarm", "Membro", "Ativo"),
        ]
        db_executemany(
            conn,
            "INSERT INTO membros (nome, nickname, cargo, status) VALUES (?, ?, ?, ?)",
            seed_membros,
        )

    cur = db_execute(conn, "SELECT COUNT(*) FROM defesas")
    defesas_vazias = db_fetchone(cur)[0] == 0

    if defesas_vazias or versao_anterior < CONTENT_VERSION:
        db_execute(conn, "DELETE FROM defesas")
        db_executemany(
            conn,
            """
            INSERT INTO defesas (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            get_defesas_seed(),
        )

    db_execute(
        conn,
        "UPDATE defesas SET monstro2 = 'Irène' WHERE monstro2 IN ('Irene', 'Iréne')",
    )
    db_execute(
        conn,
        """
        UPDATE defesas SET monstro3 = 'Qilin Slasher'
        WHERE monstro3 = 'Zenitsu'
        """,
    )
    db_execute(
        conn,
        "UPDATE defesas SET notas = 'Zenitsu de Vento (5⭐ SPD).'"
        " WHERE 'Qilin Slasher' IN (monstro1, monstro2, monstro3)"
        " AND notas LIKE 'Exemplo 5%'",
    )
    db_execute(
        conn,
        """
        UPDATE defesas SET notas = 'Zenitsu de Vento (5⭐ SPD).'
        WHERE 'Zenitsu' IN (monstro1, monstro2, monstro3)
          AND notas LIKE 'Exemplo 5%'
        """,
    )
    db_execute(
        conn,
        """
        UPDATE defesas
        SET nome = 'Ashour + Brita + Taranys', monstro3 = 'Taranys',
            notas = 'Taranys (Druida de Vento) como reviver.'
        WHERE monstro3 IN ('Reviver', 'Taranys') AND monstro1 = 'Ashour' AND monstro2 = 'Brita'
        """,
    )


def init_db() -> None:
    """Cria tabelas e insere dados iniciais se o banco estiver vazio."""
    conn = get_connection()
    try:
        if uses_postgres():
            _create_schema_postgres(conn)
        else:
            _create_schema_sqlite(conn)
            _migrate_sqlite(conn)
        _seed_and_sync(conn)
        conn.commit()
    finally:
        conn.close()


def reset_all_data() -> None:
    """Apaga todos os dados (Postgres ou SQLite) e reexecuta o seed."""
    if uses_postgres():
        conn = get_connection()
        try:
            db_execute(conn, "TRUNCATE defesas, membros, guild_config RESTART IDENTITY CASCADE")
            conn.commit()
        finally:
            conn.close()
    elif DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


# --- Leitura (pandas) ---


def load_guild_config() -> dict:
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM guild_config WHERE id = 1", conn)
    finally:
        conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}


def load_membros(apenas_ativos: bool = False) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT id, nome, nickname, cargo, status FROM membros"
    if apenas_ativos:
        query += " WHERE status = 'Ativo'"
    query += " ORDER BY CASE cargo WHEN 'Líder' THEN 1 WHEN 'Vice' THEN 2 ELSE 3 END, nome"
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


def get_membro_by_nickname(nickname: str) -> dict | None:
    nick = nickname.strip()
    if not nick:
        return None
    conn = get_connection()
    sql = _adapt_sql(
        _adapt_nickname_lookup(
            """
            SELECT id, nome, nickname, cargo, status
            FROM membros
            WHERE nickname = ? COLLATE NOCASE
            """
        )
    )
    try:
        cur = db_execute(conn, sql, (nick,))
        row = db_fetchone(cur)
    finally:
        conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "nome": row[1],
        "nickname": row[2],
        "cargo": row[3],
        "status": row[4],
    }


def nickname_disponivel(nickname: str) -> bool:
    return get_membro_by_nickname(nickname) is None


def register_membro_onboarding(nickname: str) -> dict:
    """Registra novo membro (Membro / Ativo) e retorna o registro criado."""
    nick = nickname.strip()
    if not nick:
        raise ValueError("Informe um nickname válido.")
    if not nickname_disponivel(nick):
        raise ValueError("Este nickname já está cadastrado. Use a aba 'Já sou da Guilda'.")
    create_membro(nick, nick, "Membro", "Ativo")
    membro = get_membro_by_nickname(nick)
    if not membro:
        raise RuntimeError("Falha ao registrar o novo membro.")
    return membro


def load_nicknames_ativos() -> list[str]:
    df = load_membros(apenas_ativos=True)
    if df.empty:
        return []
    return sorted(df["nickname"].astype(str).tolist())


def load_defesas() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia
            FROM defesas
            ORDER BY eficiencia DESC, estrelas DESC, nome ASC
            """,
            conn,
        )
    finally:
        conn.close()
    return df


# --- Escrita (CRUD) ---


def update_guild_config(
    nome_guilda: str,
    discord_url: str,
    boas_vindas: str,
    metas: str,
    siege_rules: str,
    wgb_rules: str,
) -> None:
    wgb_json, siege_json = _guides_json_from_text(wgb_rules, siege_rules, metas)
    conn = get_connection()
    try:
        db_execute(
            conn,
            """
            UPDATE guild_config
            SET nome_guilda = ?, discord_url = ?, boas_vindas = ?, metas = ?,
                siege_rules = ?, wgb_rules = ?, wgb_guide_json = ?, siege_guide_json = ?
            WHERE id = 1
            """,
            (
                nome_guilda,
                discord_url,
                boas_vindas,
                metas,
                siege_rules,
                wgb_rules,
                wgb_json,
                siege_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def create_membro(nome: str, nickname: str, cargo: str, status: str) -> None:
    conn = get_connection()
    try:
        db_execute(
            conn,
            "INSERT INTO membros (nome, nickname, cargo, status) VALUES (?, ?, ?, ?)",
            (nome, nickname, cargo, status),
        )
        conn.commit()
    finally:
        conn.close()


def update_membro(membro_id: int, nome: str, nickname: str, cargo: str, status: str) -> None:
    conn = get_connection()
    try:
        db_execute(
            conn,
            "UPDATE membros SET nome = ?, nickname = ?, cargo = ?, status = ? WHERE id = ?",
            (nome, nickname, cargo, status, membro_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_membro(membro_id: int) -> None:
    conn = get_connection()
    try:
        db_execute(conn, "DELETE FROM membros WHERE id = ?", (membro_id,))
        conn.commit()
    finally:
        conn.close()


def create_defesa(
    nome: str,
    tipo: str,
    estrelas: str,
    monstro1: str,
    monstro2: str,
    monstro3: str,
    notas: str,
    eficiencia: float = 5.0,
) -> None:
    conn = get_connection()
    try:
        db_execute(
            conn,
            """
            INSERT INTO defesas (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia),
        )
        conn.commit()
    finally:
        conn.close()


def update_defesa(
    defesa_id: int,
    nome: str,
    tipo: str,
    estrelas: str,
    monstro1: str,
    monstro2: str,
    monstro3: str,
    notas: str,
    eficiencia: float,
) -> None:
    conn = get_connection()
    try:
        db_execute(
            conn,
            """
            UPDATE defesas
            SET nome = ?, tipo = ?, estrelas = ?, monstro1 = ?, monstro2 = ?, monstro3 = ?,
                notas = ?, eficiencia = ?
            WHERE id = ?
            """,
            (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia, defesa_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_defesa(defesa_id: int) -> None:
    conn = get_connection()
    try:
        db_execute(conn, "DELETE FROM defesas WHERE id = ?", (defesa_id,))
        conn.commit()
    finally:
        conn.close()
