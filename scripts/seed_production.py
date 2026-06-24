#!/usr/bin/env python3
"""
Ferramentas de banco para deploy da guilda 24/7 Farming.

Uso:
  python scripts/seed_production.py fresh --force
  python scripts/seed_production.py fresh --force --guild "24/7 Farming" --discord "https://discord.gg/..."
  python scripts/seed_production.py import-membros scripts/membros.exemplo.json
  python scripts/seed_production.py backup
  python scripts/seed_production.py status
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database import CARGOS, DB_PATH, STATUS_OPCOES, create_membro, get_connection, init_db  # noqa: E402


def _confirm_force() -> None:
    if not DB_PATH.exists():
        return
    print(f"AVISO: isto substitui ou altera {DB_PATH}")


def cmd_status(_: argparse.Namespace) -> int:
    if not DB_PATH.exists():
        print("Banco não encontrado. Rode: python scripts/seed_production.py fresh --force")
        return 1
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nome_guilda, discord_url FROM guild_config WHERE id = 1")
    guild = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM membros")
    membros = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM defesas")
    defesas = cur.fetchone()[0]
    conn.close()
    print(f"Banco: {DB_PATH}")
    print(f"Guilda: {guild[0] if guild else '?'}")
    print(f"Discord: {guild[1] if guild else '?'}")
    print(f"Membros: {membros}")
    print(f"Defesas: {defesas}")
    return 0


def cmd_fresh(args: argparse.Namespace) -> int:
    _confirm_force()
    if DB_PATH.exists():
        if not args.force:
            print("O banco já existe. Use --force para recriar.")
            return 1
        DB_PATH.unlink()
        print("Banco anterior removido.")

    init_db()
    conn = get_connection()
    cur = conn.cursor()

    if args.no_demo_members:
        cur.execute("DELETE FROM membros")
        print("Membros de demonstração removidos.")

    if args.guild:
        cur.execute("UPDATE guild_config SET nome_guilda = ? WHERE id = 1", (args.guild,))
    if args.discord:
        cur.execute("UPDATE guild_config SET discord_url = ? WHERE id = 1", (args.discord,))

    conn.commit()
    conn.close()
    print(f"Banco pronto em {DB_PATH}")
    return 0


def cmd_import_membros(args: argparse.Namespace) -> int:
    path = Path(args.arquivo)
    if not path.is_file():
        print(f"Arquivo não encontrado: {path}")
        return 1
    if not DB_PATH.exists():
        print("Banco não existe. Rode fresh --force antes.")
        return 1

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        print("JSON deve ser uma lista de membros.")
        return 1

    inseridos = 0
    for item in payload:
        nome = str(item.get("nome", "")).strip()
        nickname = str(item.get("nickname", nome)).strip()
        cargo = str(item.get("cargo", "Membro")).strip()
        status = str(item.get("status", "Ativo")).strip()
        if not nome or not nickname:
            print(f"Ignorado (nome/nickname vazio): {item}")
            continue
        if cargo not in CARGOS:
            print(f"Cargo inválido '{cargo}' para {nickname}. Use: {CARGOS}")
            return 1
        if status not in STATUS_OPCOES:
            print(f"Status inválido '{status}' para {nickname}. Use: {STATUS_OPCOES}")
            return 1
        try:
            create_membro(nome, nickname, cargo, status)
            inseridos += 1
        except Exception as exc:
            print(f"Falha ao inserir {nickname}: {exc}")
            return 1

    print(f"{inseridos} membro(s) importado(s).")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    if not DB_PATH.exists():
        print("Nada para backup — banco não existe.")
        return 1
    dest_dir = Path(args.destino)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"guilda_backup_{stamp}.db"
    shutil.copy2(DB_PATH, dest)
    print(f"Backup salvo em {dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed e manutenção do banco da guilda")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Mostra resumo do banco")
    p_status.set_defaults(func=cmd_status)

    p_fresh = sub.add_parser("fresh", help="Recria o banco (guild config + defesas seed)")
    p_fresh.add_argument("--force", action="store_true", help="Sobrescreve banco existente")
    p_fresh.add_argument("--no-demo-members", action="store_true", default=True,
                         help="Remove membros de exemplo (padrão: sim)")
    p_fresh.add_argument("--keep-demo-members", action="store_true",
                         help="Mantém Lucas/Rafael/Ana/Bruno de demonstração")
    p_fresh.add_argument("--guild", help="Nome da guilda")
    p_fresh.add_argument("--discord", help="URL do Discord")
    p_fresh.set_defaults(func=cmd_fresh)

    p_import = sub.add_parser("import-membros", help="Importa membros de um JSON")
    p_import.add_argument("arquivo", help="Caminho do JSON (lista de membros)")
    p_import.set_defaults(func=cmd_import_membros)

    p_backup = sub.add_parser("backup", help="Cópia de segurança do SQLite")
    p_backup.add_argument(
        "--destino",
        default=str(ROOT / "data" / "backups"),
        help="Pasta de destino (padrão: data/backups)",
    )
    p_backup.set_defaults(func=cmd_backup)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "fresh" and args.keep_demo_members:
        args.no_demo_members = False
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
