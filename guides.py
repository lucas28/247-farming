"""
Conversão entre Markdown (admin) e guias estruturados (página Guias e Regras).
"""

from __future__ import annotations

import copy
import json
import re

from content import get_siege_guide, get_wgb_guide

_EMOJI_HEADER = re.compile(
    r"^([\U0001F300-\U0001FAFF\u2600-\u27BF🚨⚡🧱💡🛡️🌍🏰🎯🌈].+)$",
    re.MULTILINE,
)
_EXAMPLE_4 = re.compile(r"Exemplo\s*4\s*[⭐★]*\s*:?\s*(.+)", re.IGNORECASE)
_EXAMPLE_5 = re.compile(r"Exemplo\s*5\s*[⭐★]*\s*:?\s*(.+)", re.IGNORECASE)


def _deep_default_wgb() -> dict:
    return copy.deepcopy(get_wgb_guide())


def _deep_default_siege() -> dict:
    return copy.deepcopy(get_siege_guide())


def _strip_md_headers(text: str) -> str:
    return re.sub(r"^#+\s*", "", text, flags=re.MULTILINE).strip()


def _first_paragraph(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    if lines[0].startswith("##") or "Batalha" in lines[0] or "World Guild" in lines[0]:
        lines = lines[1:]
    chunks: list[str] = []
    for ln in lines:
        if _EMOJI_HEADER.match(ln) or ln.startswith("🛡️"):
            break
        chunks.append(ln)
    return " ".join(chunks).strip()


def _block_after(text: str, starters: tuple[str, ...]) -> str:
    for starter in starters:
        idx = text.find(starter)
        if idx >= 0:
            rest = text[idx + len(starter) :]
            nxt = _EMOJI_HEADER.search(rest)
            return rest[: nxt.start()].strip() if nxt else rest.strip()
    return ""


def _title_from_alert(text: str, fallback: str) -> str:
    first = text.splitlines()[0].strip() if text else ""
    first = re.sub(r"^🚨\s*", "", first)
    if ":" in first:
        return first.split(":", 1)[1].strip()
    return first or fallback


def parse_wgb_markdown(markdown: str) -> dict:
    """Converte Markdown da WGB em dict para a UI amigável."""
    guide = _deep_default_wgb()
    if not markdown or not markdown.strip():
        return guide

    text = _strip_md_headers(markdown)
    intro = _first_paragraph(text)
    if intro:
        guide["intro"] = intro

    alert_raw = _block_after(text, ("🚨",))
    if alert_raw:
        guide["alert"]["title"] = _title_from_alert("🚨" + alert_raw.splitlines()[0], guide["alert"]["title"])
        alert_body = "\n".join(alert_raw.splitlines()[1:]).strip() or alert_raw
        guide["alert"]["text"] = alert_body

    spd_raw = _block_after(text, ("⚡",))
    if spd_raw:
        lines = spd_raw.splitlines()
        guide["strategies"][0]["title"] = re.sub(
            r"^Opção\s*\d+\s*:\s*", "", lines[0].replace("⚡", "").strip()
        ) or guide["strategies"][0]["title"]
        guide["strategies"][0]["text"] = "\n".join(lines[1:]).strip() or spd_raw

    tank_raw = _block_after(text, ("🧱",))
    if tank_raw:
        lines = tank_raw.splitlines()
        guide["strategies"][1]["title"] = re.sub(
            r"^Opção\s*\d+\s*:\s*", "", lines[0].replace("🧱", "").strip()
        ) or guide["strategies"][1]["title"]
        guide["strategies"][1]["text"] = "\n".join(lines[1:]).strip() or tank_raw

    tip_raw = _block_after(text, ("💡",))
    if tip_raw:
        tip = tip_raw.split(":", 1)[-1].strip() if ":" in tip_raw.splitlines()[0] else tip_raw
        guide["tip"] = tip

    return guide


def _parse_siege_section(block: str, variant: str) -> dict | None:
    if not block.strip():
        return None

    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if not lines:
        return None

    title_line = lines[0].replace("🛡️", "").strip()
    title_line = re.sub(r"^\d+\.\s*", "", title_line)

    description_lines: list[str] = []
    examples_4: list[str] = []
    examples_5: list[str] = []

    for ln in lines[1:]:
        m4 = _EXAMPLE_4.match(ln)
        m5 = _EXAMPLE_5.match(ln)
        if m5:
            examples_5.append(m5.group(1).strip())
        elif m4:
            examples_4.append(m4.group(1).strip())
        elif not ln.startswith("---"):
            description_lines.append(ln)

    icon = "⚡" if variant == "spd" else "🧱"
    default = next((s for s in get_siege_guide()["sections"] if s["variant"] == variant), None)

    return {
        "icon": icon,
        "title": title_line or (default["title"] if default else "Seção"),
        "variant": variant,
        "description": " ".join(description_lines).strip() or (default["description"] if default else ""),
        "examples_4": examples_4 or (default["examples_4"] if default else []),
        "examples_5": examples_5 or (default["examples_5"] if default else []),
    }


def parse_siege_markdown(markdown: str, metas: str = "") -> dict:
    """Converte Markdown do Siege em dict para a UI amigável."""
    _ = metas  # metas gerais são exibidas fora da aba Siege
    guide = _deep_default_siege()
    if not markdown or not markdown.strip():
        if metas:
            guide["goals"] = _parse_metas_goals(metas, guide["goals"])
        return guide

    text = _strip_md_headers(markdown)
    intro = _first_paragraph(text)
    if intro:
        guide["intro"] = intro

    # Dica final (após última seção tank ou linha com Lembrando/💡)
    tip_match = re.search(r"(?:💡|Lembrando que)(.+)$", text, re.DOTALL | re.IGNORECASE)
    if tip_match:
        guide["tip"] = tip_match.group(1).strip()

    parts = re.split(r"(?=🛡️\s*\d+\.)", text)
    sections: list[dict] = []
    for part in parts:
        if not re.match(r"🛡️\s*\d+\.", part.strip()):
            continue
        lower = part.lower()
        if "spd" in lower or "speed" in lower or "conteste" in lower:
            sec = _parse_siege_section(part, "spd")
            if sec:
                sections.append(sec)
        elif "tank" in lower or "anti-cleave" in lower or "cleave" in lower:
            sec = _parse_siege_section(part, "tank")
            if sec:
                sections.append(sec)

    if sections:
        guide["sections"] = sections

    return guide


def _parse_metas_goals(metas: str, defaults: list[dict]) -> list[dict]:
    """Extrai até 3 metas de bullet points do campo Metas."""
    bullets = re.findall(r"[-•*]\s*(.+)", metas)
    if not bullets:
        return defaults

    icons = ["🎯", "⭐", "🌈", "📌", "✅"]
    goals: list[dict] = []
    for i, bullet in enumerate(bullets[:3]):
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", bullet).strip()
        if ":" in clean:
            label, value = clean.split(":", 1)
        else:
            label, value = "Meta", clean
        goals.append(
            {
                "icon": icons[i] if i < len(icons) else "📌",
                "label": label.strip()[:40],
                "value": value.strip(),
            }
        )
    return goals or defaults


def goals_from_config(config: dict) -> list[dict]:
    """Metas gerais da guilda (campo Metas do admin)."""
    metas = config.get("metas", "") or ""
    return _parse_metas_goals(metas, get_siege_guide()["goals"])


def guide_to_json(guide: dict) -> str:
    return json.dumps(guide, ensure_ascii=False)


def guide_from_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def wgb_guide_from_config(config: dict) -> dict:
    cached = guide_from_json(config.get("wgb_guide_json"))
    if cached:
        return cached
    return parse_wgb_markdown(config.get("wgb_rules", "") or "")


def siege_guide_from_config(config: dict) -> dict:
    cached = guide_from_json(config.get("siege_guide_json"))
    if cached:
        return cached
    return parse_siege_markdown(
        config.get("siege_rules", "") or "",
        config.get("metas", "") or "",
    )


def build_guides_payload(wgb_rules: str, siege_rules: str, metas: str = "") -> tuple[str, str]:
    """Gera JSON dos guias a partir do Markdown editado no admin."""
    wgb = parse_wgb_markdown(wgb_rules)
    siege = parse_siege_markdown(siege_rules, metas)
    return guide_to_json(wgb), guide_to_json(siege)
