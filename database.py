"""
Camada de persistência SQLite para a plataforma da guilda.
Utiliza sqlite3 para escrita e pandas para leitura em lote.
"""

import sqlite3
from pathlib import Path

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


def _guides_json_from_text(wgb_rules: str, siege_rules: str, metas: str) -> tuple[str, str]:
    return build_guides_payload(wgb_rules, siege_rules, metas)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Cria tabelas e insere dados iniciais se o banco estiver vazio."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript(
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
        );

        CREATE TABLE IF NOT EXISTS membros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            nickname TEXT NOT NULL DEFAULT '',
            cargo TEXT NOT NULL CHECK (cargo IN ('Líder', 'Vice', 'Membro')),
            status TEXT NOT NULL CHECK (status IN ('Ativo', 'Inativo'))
        );

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
        );
        """
    )

    # Migração inline (evita problemas de cache/reload do Streamlit)
    cursor.execute("PRAGMA table_info(guild_config)")
    colunas = {row[1] for row in cursor.fetchall()}
    if "boas_vindas" not in colunas:
        cursor.execute("ALTER TABLE guild_config ADD COLUMN boas_vindas TEXT")
    if "content_version" not in colunas:
        cursor.execute("ALTER TABLE guild_config ADD COLUMN content_version INTEGER DEFAULT 0")
    if "wgb_guide_json" not in colunas:
        cursor.execute("ALTER TABLE guild_config ADD COLUMN wgb_guide_json TEXT")
    if "siege_guide_json" not in colunas:
        cursor.execute("ALTER TABLE guild_config ADD COLUMN siege_guide_json TEXT")

    cursor.execute("PRAGMA table_info(membros)")
    colunas_membros = {row[1] for row in cursor.fetchall()}
    if "nickname" not in colunas_membros:
        cursor.execute("ALTER TABLE membros ADD COLUMN nickname TEXT NOT NULL DEFAULT ''")
        cursor.execute("UPDATE membros SET nickname = nome WHERE COALESCE(nickname, '') = ''")
    if "foco" in colunas_membros:
        cursor.executescript(
            """
            CREATE TABLE membros_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                nickname TEXT NOT NULL DEFAULT '',
                cargo TEXT NOT NULL CHECK (cargo IN ('Líder', 'Vice', 'Membro')),
                status TEXT NOT NULL CHECK (status IN ('Ativo', 'Inativo'))
            );
            INSERT INTO membros_new (id, nome, nickname, cargo, status)
            SELECT id, nome, COALESCE(nickname, ''), cargo, status FROM membros;
            DROP TABLE membros;
            ALTER TABLE membros_new RENAME TO membros;
            """
        )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_membros_nickname "
        "ON membros(nickname COLLATE NOCASE)"
    )

    cursor.execute("PRAGMA table_info(defesas)")
    colunas_defesas = {row[1] for row in cursor.fetchall()}
    if "eficiencia" not in colunas_defesas:
        cursor.execute(
            "ALTER TABLE defesas ADD COLUMN eficiencia REAL NOT NULL DEFAULT 5.0"
        )
        cursor.execute("UPDATE defesas SET eficiencia = 5.0 WHERE eficiencia IS NULL")

    versao_anterior = 0
    cursor.execute("SELECT COUNT(*) FROM guild_config")
    if cursor.fetchone()[0] == 0:
        wgb_md = get_wgb_rules()
        siege_md = get_siege_rules()
        metas_md = get_metas()
        wgb_json, siege_json = _guides_json_from_text(wgb_md, siege_md, metas_md)
        cursor.execute(
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
        cursor.execute("SELECT COALESCE(content_version, 0) FROM guild_config WHERE id = 1")
        row = cursor.fetchone()
        versao_anterior = row[0] if row else 0
        if versao_anterior < CONTENT_VERSION:
            wgb_md = get_wgb_rules()
            siege_md = get_siege_rules()
            metas_md = get_metas()
            wgb_json, siege_json = _guides_json_from_text(wgb_md, siege_md, metas_md)
            cursor.execute(
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

    # Sincroniza JSON estruturado a partir do Markdown (fonte: admin / textos.md)
    cursor.execute("SELECT wgb_rules, siege_rules, metas FROM guild_config WHERE id = 1")
    guide_row = cursor.fetchone()
    if guide_row:
        wgb_json, siege_json = _guides_json_from_text(
            guide_row[0] or "",
            guide_row[1] or "",
            guide_row[2] or "",
        )
        cursor.execute(
            """
            UPDATE guild_config
            SET wgb_guide_json = ?, siege_guide_json = ?
            WHERE id = 1
            """,
            (wgb_json, siege_json),
        )

    cursor.execute("SELECT COUNT(*) FROM membros")
    if cursor.fetchone()[0] == 0:
        seed_membros = [
            ("Lucas", "Lucas247", "Líder", "Ativo"),
            ("Rafael", "RafaSW", "Vice", "Ativo"),
            ("Ana", "AnaPvP", "Membro", "Ativo"),
            ("Bruno", "BrunoFarm", "Membro", "Ativo"),
        ]
        cursor.executemany(
            "INSERT INTO membros (nome, nickname, cargo, status) VALUES (?, ?, ?, ?)",
            seed_membros,
        )

    cursor.execute("SELECT COUNT(*) FROM defesas")
    defesas_vazias = cursor.fetchone()[0] == 0

    if defesas_vazias or versao_anterior < CONTENT_VERSION:
        cursor.execute("DELETE FROM defesas")
        cursor.executemany(
            """
            INSERT INTO defesas (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            get_defesas_seed(),
        )

    cursor.execute(
        "UPDATE defesas SET monstro2 = 'Irène' WHERE monstro2 IN ('Irene', 'Iréne')"
    )
    cursor.execute(
        """
        UPDATE defesas SET notas = 'Zenitsu de Vento (5⭐ SPD).'
        WHERE 'Zenitsu' IN (monstro1, monstro2, monstro3)
          AND notas LIKE 'Exemplo 5%'
        """
    )
    cursor.execute(
        """
        UPDATE defesas
        SET nome = 'Ashour + Brita + Taranys', monstro3 = 'Taranys',
            notas = 'Taranys (Druida de Vento) como reviver.'
        WHERE monstro3 IN ('Reviver', 'Taranys') AND monstro1 = 'Ashour' AND monstro2 = 'Brita'
        """
    )

    conn.commit()
    conn.close()


# --- Leitura (pandas) ---


def load_guild_config() -> dict:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM guild_config WHERE id = 1", conn)
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}


def load_membros(apenas_ativos: bool = False) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT id, nome, nickname, cargo, status FROM membros"
    if apenas_ativos:
        query += " WHERE status = 'Ativo'"
    query += " ORDER BY CASE cargo WHEN 'Líder' THEN 1 WHEN 'Vice' THEN 2 ELSE 3 END, nome"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_membro_by_nickname(nickname: str) -> dict | None:
    nick = nickname.strip()
    if not nick:
        return None
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT id, nome, nickname, cargo, status
        FROM membros
        WHERE nickname = ? COLLATE NOCASE
        """,
        conn,
        params=(nick,),
    )
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


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
    df = pd.read_sql_query(
        """
        SELECT id, nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia
        FROM defesas
        ORDER BY eficiencia DESC, estrelas DESC, nome ASC
        """,
        conn,
    )
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
    conn.execute(
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
    conn.close()


def create_membro(nome: str, nickname: str, cargo: str, status: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO membros (nome, nickname, cargo, status) VALUES (?, ?, ?, ?)",
        (nome, nickname, cargo, status),
    )
    conn.commit()
    conn.close()


def update_membro(membro_id: int, nome: str, nickname: str, cargo: str, status: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE membros SET nome = ?, nickname = ?, cargo = ?, status = ? WHERE id = ?",
        (nome, nickname, cargo, status, membro_id),
    )
    conn.commit()
    conn.close()


def delete_membro(membro_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM membros WHERE id = ?", (membro_id,))
    conn.commit()
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
    conn.execute(
        """
        INSERT INTO defesas (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia),
    )
    conn.commit()
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
    conn.execute(
        """
        UPDATE defesas
        SET nome = ?, tipo = ?, estrelas = ?, monstro1 = ?, monstro2 = ?, monstro3 = ?,
            notas = ?, eficiencia = ?
        WHERE id = ?
        """,
        (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia, defesa_id),
    )
    conn.commit()
    conn.close()


def delete_defesa(defesa_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM defesas WHERE id = ?", (defesa_id,))
    conn.commit()
    conn.close()
