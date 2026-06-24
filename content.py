"""
Conteúdo oficial da guilda — lido de textos.md e formatado para o app.
Edite textos.md e reinicie o app para propagar as alterações.
"""

import re
from pathlib import Path

TEXTOS_PATH = Path(__file__).parent / "textos.md"
CONTENT_VERSION = 2


def _read_raw() -> str:
    return TEXTOS_PATH.read_text(encoding="utf-8")


def _split_sections() -> list[str]:
    """Divide textos.md pelos separadores de linha tracejada."""
    parts = re.split(r"\n-{10,}\n", _read_raw())
    return [p.strip() for p in parts if p.strip()]


def get_boas_vindas() -> str:
    sections = _split_sections()
    if not sections:
        return ""
    return sections[0].strip()


def get_wgb_rules() -> str:
    sections = _split_sections()
    if len(sections) < 2:
        return ""
    raw = sections[1].strip()
    # Garante título em Markdown se o arquivo não tiver ##
    if not raw.startswith("#"):
        raw = f"## {raw.splitlines()[0]}\n\n" + "\n".join(raw.splitlines()[1:])
    return raw


def get_siege_rules() -> str:
    sections = _split_sections()
    if len(sections) < 3:
        return ""
    # Junta todas as partes restantes (Siege pode ter sub-separadores internos)
    siege_parts = sections[2:]
    raw = "\n\n".join(siege_parts).strip()
    if not raw.startswith("#"):
        raw = "## Batalha de Assalto (Siege) 🏰\n\n" + raw
    return raw


def get_metas() -> str:
    return """**Participação ativa em todos os conteúdos de guilda**

- Montar **2 ou 3 defesas sinérgicas** para o Siege (duas 5⭐ e uma 4⭐)
- Posicionar **5 defesas obrigatórias** na Batalha Mundial (WGB)
- Evitar três monstros do **mesmo elemento** na mesma defesa
- Consultar os canais do Discord para dicas, sugestões e ajuda com composições"""


def get_wgb_guide() -> dict:
    """Conteúdo estruturado da WGB para exibição amigável."""
    return {
        "title": "Batalha Mundial de Guildas",
        "badge": "WGB",
        "icon": "🌍",
        "intro": (
            "Na Batalha Mundial o ritmo é diferente — todo mundo precisa estar alinhado "
            "para garantir vitórias e recompensas para a guilda."
        ),
        "alert": {
            "icon": "🚨",
            "title": "5 defesas obrigatórias",
            "text": (
                "Para atacar na WGB, você **precisa posicionar e salvar 5 defesas**. "
                "É regra do jogo: sem as 5 bases montadas, você fica de fora do ataque. "
                "Configure tudo antes do evento começar!"
            ),
        },
        "strategies": [
            {
                "icon": "⚡",
                "title": "Contestar o primeiro turno",
                "tag": "Speed",
                "variant": "spd",
                "text": (
                    "Jogue primeiro e desestabilize o inimigo. Use líderes de SPD, "
                    "enablers de barra de ataque e monstros com dano ou controle forte."
                ),
            },
            {
                "icon": "🧱",
                "title": "Tankar, cortar ou reviver",
                "tag": "Anti-Cleave",
                "variant": "tank",
                "text": (
                    "Monte uma muralha com líderes de HP, DEF ou RES. Invista em monstros "
                    "parrudos, curas, revives e passivas de redução de dano para absorver "
                    "o combo e punir depois."
                ),
            },
        ],
        "tip": (
            "Evite **3 monstros do mesmo elemento** na mesma defesa — counter fica fácil demais. "
            "Travou nas 5 equipes? Manda print da box no Discord que a galera ajuda!"
        ),
    }


def get_siege_guide() -> dict:
    """Conteúdo estruturado do Siege para exibição amigável."""
    return {
        "title": "Batalha de Assalto",
        "badge": "Siege",
        "icon": "🏰",
        "intro": (
            "Cada membro deve montar **2 ou 3 defesas sinérgicas** — idealmente "
            "**duas 5⭐ e uma 4⭐**. As composições abaixo são bases testadas; "
            "adapte para os monstros que você já tem na box."
        ),
        "goals": [
            {"icon": "🎯", "label": "Meta por membro", "value": "2–3 defesas"},
            {"icon": "⭐", "label": "Distribuição ideal", "value": "2× 5⭐ + 1× 4⭐"},
            {"icon": "🌈", "label": "Evitar", "value": "3 do mesmo elemento"},
        ],
        "sections": [
            {
                "icon": "⚡",
                "title": "Defesa SPD — Conteste de Speed",
                "variant": "spd",
                "description": (
                    "Leader de SPD + Enabler (barra de ataque / ordem de turno) + "
                    "terceiro monstro de dano ou controle."
                ),
                "examples_4": [
                    "Khmun + Vigor + Skogul",
                    "Clara + Vigor + Yen",
                    "Morris + Eshir + Abigail / Trevor / Vritra / Liu Mei",
                    "Morris + Rex + Shumar",
                    "Morris / Solveig / Mimirr + Chilling + Cichlid / Shumar",
                    "Fiona + Eshir + Vritra / Truffle / Liesel",
                ],
                "examples_5": [
                    "Seara + Orion / Jeogun + flex (dano, controle ou LD)",
                    "Chandra + Monte + Zenitsu (Vento)",
                    "Chandra + Nora / Perna / Rakan + Byungchul / Zen / Shahat",
                    "Platy + Irène + Zenitsu (Vento)",
                    "Tarnisha + Savannah + flex (dano, controle ou LD)",
                ],
            },
            {
                "icon": "🧱",
                "title": "Defesa Tank — Anti-Cleave",
                "variant": "tank",
                "description": (
                    "Sobreviva aos cleaves com líder de HP, RES ou DEF e monstros "
                    "que aguentem pancada ou cortem o combo do adversário."
                ),
                "examples_4": [
                    "Harmonia + Kinki / Roid / Skogul + Vigor",
                    "Betta + Kinki + Vritra",
                ],
                "examples_5": [
                    "Lamiella + Byungchul / Shahat + Ashour / 7R1X / Kumar",
                    "Ashour + Brita + Taranys (reviver)",
                ],
            },
        ],
        "tip": (
            "Artefatos de **VEL+** ajudam muito na sincronia quando o time tem buff de "
            "SPD+ (Vigor, Chilling, etc.). Monstros LD costumam fechar bem o 3º slot."
        ),
    }


def get_defesas_seed() -> list[tuple]:
    """
    Retorna tuplas: (nome, tipo, estrelas, monstro1, monstro2, monstro3, notas)
  Baseado nos exemplos de textos.md.
    """
    return [
        # 4⭐ — Conteste de SPD
        ("Khmun + Vigor + Skogul", "Conteste de SPD", "4⭐", "Khmun", "Vigor", "Skogul", "Exemplo 4⭐ SPD — contestar primeiro turno."),
        ("Clara + Vigor + Yen", "Conteste de SPD", "4⭐", "Clara", "Vigor", "Yen", "Exemplo 4⭐ SPD — enabler + dano."),
        ("Morris + Eshir + Abigail", "Conteste de SPD", "4⭐", "Morris", "Eshir", "Abigail", "Alternativas no slot 3: Trevor, Vritra, Liu Mei."),
        ("Morris + Rex + Shumar", "Conteste de SPD", "4⭐", "Morris", "Rex", "Shumar", "Exemplo 4⭐ SPD."),
        ("Morris + Chilling + Cichild", "Conteste de SPD", "4⭐", "Morris", "Chilling", "Cichild", "Lead alternativo: Solveig ou Mimirr. Slot 3: Shumar."),
        ("Fiona + Eshir + Vritra", "Conteste de SPD", "4⭐", "Fiona", "Eshir", "Vritra", "Alternativas no slot 3: Truffle, Liesel."),
        # 5⭐ — Conteste de SPD
        ("Seara + Orion + Flex", "Conteste de SPD", "5⭐", "Seara", "Orion", "Flex LD/Dano", "Jeogun no lugar de Orion. 3º slot: dano, controle ou LD."),
        ("Chandra + Monte + Zenitsu", "Conteste de SPD", "5⭐", "Chandra", "Monte", "Zenitsu", "Zenitsu de Vento (5⭐ SPD)."),
        ("Chandra + Nora + Byoungchu", "Conteste de SPD", "5⭐", "Chandra", "Nora", "Byoungchu", "Slot 2: Perna ou Rakan. Slot 3: Zen ou Shahat."),
        ("Platy + Irene + Zenitsu", "Conteste de SPD", "5⭐", "Platy", "Irène", "Zenitsu", "Zenitsu de Vento (5⭐ SPD)."),
        ("Tarnisha + Savannah + Flex", "Conteste de SPD", "5⭐", "Tarnisha", "Savannah", "Flex LD/Dano", "3º slot: dano, controle ou LD."),
        # 4⭐ — Anti-Cleave
        ("Harmonia + Kinki + Vigor", "Anti-Cleave", "4⭐", "Harmonia", "Kinki", "Vigor", "Alternativa slot 2: Roid ou Skogul."),
        ("Betta + Kinki + Vritra", "Anti-Cleave", "4⭐", "Betta", "Kinki", "Vritra", "Exemplo 4⭐ tank."),
        # 5⭐ — Anti-Cleave
        ("Lamiella + Byungchu + Ashour", "Anti-Cleave", "5⭐", "Lamiella", "Byungchu", "Ashour", "Alternativas: Shahat, 7R1X ou Kumar no slot 3."),
        ("Ashour + Brita + Taranys", "Anti-Cleave", "5⭐", "Ashour", "Brita", "Taranys", "Taranys (Druida de Vento) como reviver."),
    ]
