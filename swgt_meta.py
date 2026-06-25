"""
Coleta e agregação de meta de defesa a partir do SWGT.io.

Fonte: All Server Analytics → Defense - Trending
"""

from __future__ import annotations

import math
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from monsters import NAME_ALIASES

SWGT_DEFENSE_URL = "https://swgt.io/controllers/allServerAnalytics/defenseTrending/load"
USER_AGENT = "247Farming-GuildHub/1.0 (+https://github.com/lucas28/247-farming)"

# Usado só se o SWGT estiver fora ou mudar o layout da página.
FALLBACK_SIEGES_SEASONS: dict[str, str] = {
    "Season 21 (atual)": "SSD_64",
    "Season 20": "SSD_58",
    "Season 19": "SSD_55",
}

BATTLE_TYPES: dict[str, str] = {
    "Todos": "*",
    "Siege": "SIEGE",
    "WGB": "WORLDGUILDBATTLE",
}

BATTLE_RANKS: dict[str, str] = {
    "Todos": "*",
    "G1": "G1",
    "G2": "G2",
    "G3": "G3",
}

NATURAL_STARS: dict[str, str] = {
    "Todos": "*",
    "Sem LD5": "NLD5",
    "NAT4": "N4",
}

SORT_OPTIONS: dict[str, str] = {
    "Meta Score": "meta_score",
    "WR ponderado": "wr_ponderado",
    "Aparições": "aparicoes",
    "Batalhas totais": "batalhas_totais",
}


@dataclass(frozen=True)
class DefenseRow:
    leader: str
    monstro2: str
    monstro3: str
    battles: int
    wr_pct: float

    @property
    def monsters(self) -> tuple[str, str, str]:
        return (self.leader, self.monstro2, self.monstro3)

    @property
    def label(self) -> str:
        return f"{self.leader} + {self.monstro2} + {self.monstro3}"


@dataclass(frozen=True)
class MonsterMeta:
    nome: str
    aparicoes: int
    batalhas_totais: int
    wr_ponderado: float
    wr_max: float
    melhor_defesa: str
    melhor_wr: float
    meta_score: float


def _normalize_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def canonical_monster_name(name: str) -> str:
    """Unifica grafias SWGT com apelidos da guilda / SWARFARM."""
    cleaned = name.strip()
    if not cleaned:
        return cleaned
    alias = NAME_ALIASES.get(_normalize_key(cleaned))
    return alias if alias else cleaned


def build_swgt_url(
    siege_special_date: str,
    battle_type: str = "*",
    battle_rank: str = "*",
    natural_stars: str = "*",
    selected_focus: str = "",
) -> str:
    params = urllib.parse.urlencode(
        {
            "selectedFocus": selected_focus,
            "siegeSpecialDate": siege_special_date,
            "battleType": battle_type,
            "battleRank": battle_rank,
            "naturalStars": natural_stars,
        }
    )
    return f"{SWGT_DEFENSE_URL}?{params}"


def _swgt_request(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"SWGT retornou HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Não foi possível acessar o SWGT: {exc.reason}") from exc


def parse_siege_seasons(html: str) -> dict[str, str]:
    """Extrai seasons do dropdown siegeSpecialDate na página do SWGT."""
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", attrs={"name": "siegeSpecialDate"})
    if not select:
        select = soup.find("select", id=re.compile(r"siegeSpecialDate", re.I))

    seasons: dict[str, str] = {}
    if not select:
        raise ValueError("Dropdown siegeSpecialDate não encontrado no HTML do SWGT.")

    for index, option in enumerate(select.find_all("option")):
        code = (option.get("value") or "").strip()
        label = option.get_text(strip=True)
        if not code or not label:
            continue
        if index == 0 and "(atual)" not in label.lower():
            label = f"{label} (atual)"
        seasons[label] = code

    if not seasons:
        raise ValueError("Nenhuma season Siege encontrada no HTML do SWGT.")
    return seasons


def fetch_siege_seasons(timeout: int = 30) -> dict[str, str]:
    """Lista seasons disponíveis no SWGT (mais recente primeiro)."""
    fallback_code = next(iter(FALLBACK_SIEGES_SEASONS.values()))
    html = _swgt_request(build_swgt_url(fallback_code), timeout=timeout)
    return parse_siege_seasons(html)


def _monster_name_from_cell(td: Any) -> str:
    img = td.find("img")
    if img:
        return canonical_monster_name((img.get("title") or img.get("alt") or "").strip())
    return canonical_monster_name(td.get_text(strip=True))


def parse_defense_table(html: str) -> list[DefenseRow]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="searchResults")
    if not table:
        raise ValueError("Tabela #searchResults não encontrada no HTML do SWGT.")

    tbody = table.find("tbody")
    if not tbody:
        return []

    rows: list[DefenseRow] = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue
        leader = _monster_name_from_cell(cells[0])
        monstro2 = _monster_name_from_cell(cells[1])
        monstro3 = _monster_name_from_cell(cells[2])
        if not leader or not monstro2 or not monstro3:
            continue
        battles = int(float(cells[3].get("data-sort", "0") or 0))
        wr_pct = float(cells[4].get("data-sort", "0") or 0)
        rows.append(
            DefenseRow(
                leader=leader,
                monstro2=monstro2,
                monstro3=monstro3,
                battles=battles,
                wr_pct=wr_pct,
            )
        )
    return rows


def fetch_defense_rows(
    siege_special_date: str,
    battle_type: str = "*",
    battle_rank: str = "*",
    natural_stars: str = "*",
    timeout: int = 30,
) -> list[DefenseRow]:
    url = build_swgt_url(siege_special_date, battle_type, battle_rank, natural_stars)
    html = _swgt_request(url, timeout=timeout)
    rows = parse_defense_table(html)
    if not rows:
        raise ValueError("Nenhuma defesa encontrada na resposta do SWGT.")
    return rows


def aggregate_monsters(
    rows: list[DefenseRow],
    min_battles_monster: int = 0,
) -> list[MonsterMeta]:
    stats: dict[str, dict[str, Any]] = {}

    for row in rows:
        for name in row.monsters:
            if not name:
                continue
            if name not in stats:
                stats[name] = {
                    "aparicoes": 0,
                    "batalhas": 0,
                    "wr_sum": 0.0,
                    "wr_max": 0.0,
                    "melhor_defesa": "",
                    "melhor_wr": -1.0,
                    "melhor_battles": -1,
                }
            entry = stats[name]
            entry["aparicoes"] += 1
            entry["batalhas"] += row.battles
            entry["wr_sum"] += row.battles * row.wr_pct
            entry["wr_max"] = max(entry["wr_max"], row.wr_pct)
            if row.wr_pct > entry["melhor_wr"] or (
                row.wr_pct == entry["melhor_wr"] and row.battles > entry["melhor_battles"]
            ):
                entry["melhor_wr"] = row.wr_pct
                entry["melhor_battles"] = row.battles
                entry["melhor_defesa"] = row.label

    result: list[MonsterMeta] = []
    for nome, entry in stats.items():
        batalhas = int(entry["batalhas"])
        if batalhas < min_battles_monster:
            continue
        wr_ponderado = entry["wr_sum"] / batalhas if batalhas else 0.0
        meta_score = wr_ponderado * math.log10(batalhas + 1)
        result.append(
            MonsterMeta(
                nome=nome,
                aparicoes=int(entry["aparicoes"]),
                batalhas_totais=batalhas,
                wr_ponderado=round(wr_ponderado, 2),
                wr_max=round(float(entry["wr_max"]), 2),
                melhor_defesa=str(entry["melhor_defesa"]),
                melhor_wr=round(float(entry["melhor_wr"]), 2),
                meta_score=round(meta_score, 2),
            )
        )
    return result


def monster_meta_to_dataframe(
    monsters: list[MonsterMeta],
    sort_by: str = "meta_score",
) -> pd.DataFrame:
    if not monsters:
        return pd.DataFrame(
            columns=[
                "nome",
                "meta_score",
                "wr_ponderado",
                "aparicoes",
                "batalhas_totais",
                "wr_max",
                "melhor_wr",
                "melhor_defesa",
            ]
        )
    df = pd.DataFrame([m.__dict__ for m in monsters])
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)
    return df.reset_index(drop=True)
