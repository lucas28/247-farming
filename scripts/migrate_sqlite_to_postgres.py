#!/usr/bin/env python3
"""
Copia dados do SQLite local para PostgreSQL/Supabase.

Requer DATABASE_URL no ambiente apontando para o Postgres de destino.
O SQLite em data/guilda.db deve existir.

Uso:
  set DATABASE_URL=postgresql://...
  python scripts/migrate_sqlite_to_postgres.py
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "guilda.db"
sys.path.insert(0, str(ROOT))


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("Defina DATABASE_URL com a connection string do Supabase.")
        return 1
    if not DB_PATH.exists():
        print(f"SQLite não encontrado: {DB_PATH}")
        return 1

    os.environ["DATABASE_URL"] = url
    import database as db

    importlib.reload(db)

    if not db.uses_postgres():
        print("DATABASE_URL inválida ou psycopg2 não instalado.")
        return 1

    src = sqlite3.connect(DB_PATH)
    src.row_factory = sqlite3.Row
    dst = db.get_connection()

    try:
        db.init_db()

        tables = [
            (
                "guild_config",
                "id, nome_guilda, discord_url, boas_vindas, metas, siege_rules, wgb_rules, "
                "wgb_guide_json, siege_guide_json, content_version",
            ),
            ("membros", "id, nome, nickname, cargo, status"),
            (
                "defesas",
                "id, nome, tipo, estrelas, monstro1, monstro2, monstro3, notas, eficiencia",
            ),
        ]

        for table, cols in tables:
            rows = src.execute(f"SELECT {cols} FROM {table}").fetchall()
            if not rows:
                continue
            db.db_execute(dst, f"DELETE FROM {table}")
            placeholders = ", ".join(["?"] * len(cols.split(",")))
            for row in rows:
                db.db_execute(
                    dst,
                    f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                    tuple(row),
                )
            if table != "guild_config":
                db.db_execute(
                    dst,
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table}), 1)
                    )
                    """,
                )
            print(f"{table}: {len(rows)} registro(s) migrado(s).")

        dst.commit()
        print("Migração concluída.")
        return 0
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    raise SystemExit(main())
