"""Seed asset management tables from CSV exports of the existing spreadsheet.

Usage:
    uv run python scripts/seed_assets.py --notebooks notebooks.csv --phones smartphones.csv

CSV format for notebooks (tab or comma separated):
  Modelo, Nome do Computador, Usuário, Setor, Antivirus, Fusion Inventário,
  Termo de Resp., Placa Nova Inventário, Versão S.O, Processador, Memoria RAM, HD, Status, Aquisição

CSV format for smartphones (tab or comma separated):
  Área, Colaborador, Número, Aparelho, Data recebimento, N°, Status
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import date
from pathlib import Path

import asyncpg

# Adjust to your .env or pass DATABASE_URL env var
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://").replace("+psycopg://", "")


def _parse_date(s: str) -> date | None:
    s = s.strip()
    if not s or s in {"(S/D)", "S/D", "?", ""}:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _ok(s: str) -> bool:
    return s.strip().upper() in {"OK", "SIM", "✅", "TRUE", "1", "S"}


async def seed_notebooks(conn: asyncpg.Connection, path: Path) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        dialect = csv.Sniffer().sniff(f.read(4096), delimiters="\t,;")
        f.seek(0)
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            modelo = (row.get("Modelo") or "").strip()
            if not modelo:
                continue

            specs = {
                "computer_name": (row.get("Nome do Computador") or "").strip(),
                "os_version": (row.get("Versão S.O") or row.get("Versao S.O") or "").strip(),
                "processor": (row.get("Processador") or "").strip(),
                "ram": (row.get("Memoria RAM") or row.get("Memória RAM") or "").strip(),
                "storage": (row.get("HD") or "").strip(),
            }
            compliance = {
                "antivirus": _ok(row.get("Antivirus instalado") or row.get("Antivirus") or ""),
                "fusion_inventory": _ok(row.get("Fusion Inventário") or row.get("Fusion Inventario") or ""),
                "responsibility_term": _ok(row.get("Termo de Resp.") or row.get("Termo de Responsabilidade") or ""),
            }
            asset_tag = (row.get("Placa Nova Inventário") or row.get("Placa Nova Inventario") or "").strip() or None
            status_raw = (row.get("Status") or "active").lower()
            status = "active" if "ot" in status_raw or "ok" in status_raw else "maintenance"
            acquired = _parse_date(row.get("Aquisição") or row.get("Aquisicao") or "")
            holder_name = (row.get("Usuário") or row.get("Usuario") or "").strip() or None
            holder_dept = (row.get("Setor") or "").strip() or None

            # Extract brand from model
            parts = modelo.split()
            brand = parts[0] if parts else "Dell"

            await conn.execute(
                """
                INSERT INTO helpdesk.assets
                    (asset_type, brand, model, asset_tag, status, holder_name, holder_dept,
                     acquired_at, specs, compliance, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                        $9::jsonb, $10::jsonb, 'seed_script')
                ON CONFLICT (asset_tag) DO NOTHING
                """,
                "notebook",
                brand,
                modelo,
                asset_tag,
                status,
                holder_name,
                holder_dept,
                acquired,
                json.dumps(specs),
                json.dumps(compliance),
            )

            count += 1
    return count


async def seed_smartphones(conn: asyncpg.Connection, path: Path) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        dialect = csv.Sniffer().sniff(f.read(4096), delimiters="\t,;")
        f.seek(0)
        reader = csv.DictReader(f, dialect=dialect)
        for row in reader:
            aparelho = (row.get("Aparelho") or "").strip()
            if not aparelho:
                continue

            parts = aparelho.split()
            brand = parts[0] if parts else "Samsung"

            specs = {
                "phone_number": (row.get("Número") or row.get("Numero") or "").strip(),
            }

            asset_tag = (row.get("N°") or row.get("N") or "").strip() or None
            status_raw = (row.get("Status") or "").strip()
            if "quebrad" in status_raw.lower():
                status = "maintenance"
            elif "✅" in status_raw or "ok" in status_raw.lower():
                status = "active"
            else:
                status = "active"

            acquired = _parse_date(row.get("Data recebimento") or "")
            holder_name = (row.get("Colaborador") or "").strip() or None
            holder_dept = (row.get("Área") or row.get("Area") or "").strip() or None

            await conn.execute(
                """
                INSERT INTO helpdesk.assets
                    (asset_type, brand, model, asset_tag, status, holder_name, holder_dept,
                     acquired_at, specs, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, 'seed_script')
                ON CONFLICT (asset_tag) DO NOTHING
                """,
                "smartphone",
                brand,
                aparelho,
                asset_tag,
                status,
                holder_name,
                holder_dept,
                acquired,
                json.dumps(specs),
            )
            count += 1
    return count


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed assets from CSV spreadsheet exports")
    parser.add_argument("--notebooks", type=Path, help="Path to notebooks CSV")
    parser.add_argument("--phones", type=Path, help="Path to smartphones CSV")
    args = parser.parse_args()

    if not args.notebooks and not args.phones:
        parser.print_help()
        sys.exit(1)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if args.notebooks:
            n = await seed_notebooks(conn, args.notebooks)
            print(f"Notebooks: {n} rows processed")
        if args.phones:
            n = await seed_smartphones(conn, args.phones)
            print(f"Smartphones: {n} rows processed")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
