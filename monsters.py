"""
Resolução de imagens de monstros via API do SWARFARM.
Cache local em data/monster_cache.json para alta performance.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SWARFARM_API = "https://swarfarm.com/api/v2/monsters/"
SWARFARM_IMG = "https://swarfarm.com/static/herders/images/monsters/"
CACHE_PATH = Path(__file__).parent / "data" / "monster_cache.json"
MONSTER_CACHE_VERSION = 3  # incrementar ao mudar regras de elemento/imagem

# Apelidos / grafias usadas pela guilda → nome oficial no SWARFARM
NAME_ALIASES: dict[str, str] = {
    "cichild": "Cichlid",
    "byoungchu": "Byungchul",
    "zen": "Byungchul",
    "jeogun": "Jeogun",
    "7r1x": "7R1X",
    "irene": "Irène",
    "iréne": "Irène",
    "irène": "Irène",
    "tyranys": "Taranys",
    "taranys": "Taranys",
    "flex ld/dano": "",
    "reviver": "Taranys",
}

# Elemento preferido quando o monstro existe em várias atributos
ELEMENT_PREFERENCES: dict[str, str] = {}

# Prefixos usados pelo SWGT (ex.: "Wind Qilin Slasher" → Qilin Slasher + Wind)
ELEMENT_PREFIXES: dict[str, str] = {
    "wind": "Wind",
    "fire": "Fire",
    "water": "Water",
    "light": "Light",
    "dark": "Dark",
}

PLACEHOLDER_KEY = "__placeholder__"
PLACEHOLDER_IMG = (
    "https://swarfarm.com/static/herders/images/monsters/unit_icon_0000_0_0.png"
)


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _split_element_prefix(name: str) -> tuple[str | None, str]:
    """SWGT prefixa o elemento no nome (ex.: Wind Qilin Slasher)."""
    parts = name.strip().split(maxsplit=1)
    if len(parts) != 2:
        return None, name.strip()
    element = ELEMENT_PREFIXES.get(parts[0].lower())
    if not element:
        return None, name.strip()
    return element, parts[1]


def _api_lookup(query: str) -> list[dict]:
    url = f"{SWARFARM_API}?name={urllib.parse.quote(query)}&limit=20"
    req = urllib.request.Request(url, headers={"User-Agent": "Guilda247-Streamlit/1.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("results", [])


def _pick_best_match(
    query: str, results: list[dict], preferred_element: str | None = None
) -> dict | None:
    if not results:
        return None

    if preferred_element:
        elemental = [m for m in results if m.get("element") == preferred_element]
        if elemental:
            results = elemental

    q = query.strip().lower()

    for monster in results:
        if monster.get("name", "").lower() == q:
            return monster

    for monster in results:
        if monster.get("name", "").lower().startswith(q):
            return monster

    for monster in results:
        if q in monster.get("name", "").lower():
            return monster

    return results[0]


def resolve_monster_image(name: str, cache: dict[str, str] | None = None) -> str:
    """
    Retorna URL da imagem do monstro.
    Usa cache em memória/disco; consulta SWARFARM apenas para nomes novos.
    """
    raw = name.strip()
    if not raw:
        return PLACEHOLDER_IMG

    key = _normalize_key(raw)
    if cache is None:
        cache = _load_cache()

    if key in cache:
        return cache[key] or PLACEHOLDER_IMG

    alias = NAME_ALIASES.get(key)
    if alias == "":
        cache[key] = PLACEHOLDER_IMG
        _save_cache(cache)
        return PLACEHOLDER_IMG

    parsed_element, base_name = _split_element_prefix(raw)
    search_name = alias or (base_name if parsed_element else raw)
    preferred_element = ELEMENT_PREFERENCES.get(key) or parsed_element

    try:
        results = _api_lookup(search_name)
        monster = _pick_best_match(search_name, results, preferred_element)
        if monster and monster.get("image_filename"):
            url = f"{SWARFARM_IMG}{monster['image_filename']}"
            cache[key] = url
            _save_cache(cache)
            return url
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass

    cache[key] = PLACEHOLDER_IMG
    _save_cache(cache)
    return PLACEHOLDER_IMG


def resolve_many(names: list[str]) -> dict[str, str]:
    """Resolve vários nomes reutilizando o mesmo cache."""
    cache = _load_cache()
    return {name: resolve_monster_image(name, cache) for name in names}


def unique_monsters_from_defesas(defesas_df) -> list[str]:
    if defesas_df is None or defesas_df.empty:
        return []
    cols = ["monstro1", "monstro2", "monstro3"]
    names: set[str] = set()
    for col in cols:
        if col in defesas_df.columns:
            names.update(defesas_df[col].dropna().astype(str).tolist())
    return sorted(n for n in names if n.strip())
