"""
Calculadora de Speed Tuning — simulação de ticks (GW / Siege / Arena).

Combat SPD = Base + Runas + floor(Base × (Líder% + 15%) / 100)
ATB por tick = Combat_SPD × 0,07
"""

from __future__ import annotations

import math

import streamlit as st

TOTEM_PCT = 15
TICK_RATE = 0.07
SPD_BUFF_MULT = 1.3
SAFETY_MARGIN_RUNE = 1
MAX_RUNE_SEARCH = 300

LEADER_PRESETS = [0, 15, 19, 24, 28, 33]


def combat_spd(base: int | float, rune_spd: int | float = 0, leader_pct: float = 0) -> int:
    """Combat SPD usada na simulação de ticks."""
    base_i = int(base)
    rune_i = int(rune_spd)
    bonus = math.floor(base_i * (float(leader_pct) + TOTEM_PCT) / 100.0)
    return base_i + rune_i + bonus


def tick_bracket(combat: int) -> int:
    """Tick em que o monstro atinge naturalmente 100% de ATB."""
    if combat <= 0:
        return 1
    return max(1, math.ceil(100.0 / (combat * TICK_RATE)))


def _attacker_beats_enemy_atb(
    initiator_combat: int,
    attacker_combat: int,
    atb_boost_pct: float,
    has_spd_buff: bool,
) -> tuple[bool, int, float, float]:
    """
    Simula ticks até o iniciador agir, aplica boost/buff, roda +1 tick extra
    e verifica se ATB do atacante > ATB do inimigo (mesma combat SPD do iniciador).
  """
    enemy_combat = initiator_combat
    ini_atb = 0.0
    enemy_atb = 0.0
    att_atb = 0.0
    spd_buff_active = False
    initiator_action_tick = 0

    tick = 0
    while tick < 200:
        tick += 1

        ini_gain = initiator_combat * TICK_RATE
        enemy_gain = enemy_combat * TICK_RATE
        att_gain = attacker_combat * (SPD_BUFF_MULT if spd_buff_active else 1.0) * TICK_RATE

        ini_atb += ini_gain
        enemy_atb += enemy_gain
        att_atb += att_gain

        if initiator_action_tick == 0 and ini_atb >= 100.0:
            initiator_action_tick = tick
            att_atb += atb_boost_pct
            if has_spd_buff:
                spd_buff_active = True

            # +1 tick extra após o turno do iniciador
            tick += 1
            ini_atb += ini_gain
            enemy_atb += enemy_gain
            att_atb += attacker_combat * (SPD_BUFF_MULT if spd_buff_active else 1.0) * TICK_RATE

            return att_atb > enemy_atb, initiator_action_tick, att_atb, enemy_atb

    return False, initiator_action_tick, att_atb, enemy_atb


def find_minimum_rune_spd(
    initiator_combat: int,
    attacker_base: int | float,
    leader_pct: float,
    atb_boost_pct: float,
    has_spd_buff: bool,
    max_search: int = MAX_RUNE_SEARCH,
) -> tuple[int | None, int | None]:
    """
    Busca a menor rune_spd (0..max_search) que passa na simulação.
    Retorna (rune_mínima + margem, rune_bruta_sem_margem) ou (None, None).
    """
    for rune in range(max_search + 1):
        attacker_combat = combat_spd(attacker_base, rune, leader_pct)
        passes, _, _, _ = _attacker_beats_enemy_atb(
            initiator_combat,
            attacker_combat,
            atb_boost_pct,
            has_spd_buff,
        )
        if passes:
            return rune + SAFETY_MARGIN_RUNE, rune
    return None, None


def _inject_tuning_css() -> None:
    st.markdown(
        """
        <style>
        .tuning-section-title {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #6e7681;
            margin: 1.25rem 0 0.65rem 0;
        }
        .tuning-metric-row {
            margin: 0.5rem 0 1.25rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _resolve_leader_pct(preset: str, custom: float) -> float:
    if preset == "Outro":
        return float(custom)
    return float(preset)


def render_speed_calculator() -> None:
    """Calculadora de speed tuning por simulação de ticks."""
    _inject_tuning_css()

    st.title("⚡ Calculadora de Speed Tuning")
    st.caption(
        "Simulação tick a tick (ATB 7% / tick). Inimigo espelho: mesma combat SPD do seu iniciador."
    )

    st.markdown('<p class="tuning-section-title">Configurações</p>', unsafe_allow_html=True)
    cfg1, cfg2, cfg3 = st.columns(3)
    with cfg1:
        leader_preset = st.selectbox("Líder de SPD (%)", [str(x) for x in LEADER_PRESETS] + ["Outro"])
        leader_custom = st.number_input(
            "Líder custom (%)",
            min_value=0.0,
            max_value=50.0,
            step=1.0,
            value=33.0,
            disabled=leader_preset != "Outro",
        )
        leader_pct = _resolve_leader_pct(leader_preset, leader_custom)
    with cfg2:
        atb_boost = st.number_input(
            "Push de barra (ATB %)",
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            value=30.0,
            help="Bernard S1 = 30%.",
        )
    with cfg3:
        has_spd_buff = st.checkbox(
            "Buff de velocidade (+30%)",
            help="A partir do tick após o boost, combat SPD do atacante × 1,3 no ganho de ATB.",
        )

    st.markdown('<p class="tuning-section-title">Iniciador</p>', unsafe_allow_html=True)
    ini1, ini2, ini3 = st.columns([2, 1, 1])
    with ini1:
        ini_nome = st.text_input("Nome (opcional)", placeholder="Bernard", key="tune_ini_nome")
    with ini2:
        ini_base = st.number_input("Base SPD", min_value=1, value=111, step=1, key="tune_ini_base")
    with ini3:
        ini_rune = st.number_input("+SPD runas", min_value=0, value=0, step=1, key="tune_ini_rune")

    st.markdown('<p class="tuning-section-title">Atacante (slot 2)</p>', unsafe_allow_html=True)
    att1, att2 = st.columns([2, 1])
    with att1:
        att_nome = st.text_input("Nome (opcional)", placeholder="Galleon", key="tune_att_nome")
    with att2:
        att_base = st.number_input("Base SPD", min_value=1, value=108, step=1, key="tune_att_base")

    calcular = st.button("Calcular Tuning", type="primary", use_container_width=True)

    if not calcular:
        return

    if atb_boost <= 0 and not has_spd_buff:
        st.warning(
            "Sem push de barra (ATB) nem buff de velocidade, um inimigo com a mesma combat SPD "
            "do iniciador tende a **cortar** o atacante — não há tuning seguro só com velocidade."
        )

    initiator_combat = combat_spd(ini_base, ini_rune, leader_pct)
    ini_tick = tick_bracket(initiator_combat)
    ini_label = ini_nome.strip() or "Iniciador"
    att_label = att_nome.strip() or "Atacante"

    st.markdown('<div class="tuning-metric-row">', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Combat SPD — {ini_label}", initiator_combat)
    m2.metric(f"Tick bracket — {ini_label}", f"Tick {ini_tick}")
    m3.metric("Combat SPD inimigo (espelho)", initiator_combat)
    st.markdown("</div>", unsafe_allow_html=True)

    min_rune, raw_rune = find_minimum_rune_spd(
        initiator_combat,
        att_base,
        leader_pct,
        atb_boost,
        has_spd_buff,
    )

    if min_rune is None:
        st.error(
            f"Não foi possível encontrar tuning até +{MAX_RUNE_SEARCH} SPD nas runas. "
            "Aumente o push de barra, ative buff de SPD ou revise os stats."
        )
        return

    att_combat_target = combat_spd(att_base, min_rune, leader_pct)
    att_combat_raw = combat_spd(att_base, raw_rune, leader_pct)
    pct_ini = (att_combat_target / initiator_combat * 100) if initiator_combat else 0

    st.success(
        f"**{att_label}** precisa de no mínimo **+{min_rune} SPD** nas runas "
        f"(simulação: +{raw_rune} + margem de {SAFETY_MARGIN_RUNE})."
    )

    r1, r2, r3 = st.columns(3)
    r1.metric("+SPD runas (com margem)", min_rune)
    r2.metric("Combat SPD alvo do atacante", att_combat_target)
    r3.metric("% da combat do iniciador", f"{pct_ini:.1f}%")

    with st.expander("ℹ️ Detalhamento da simulação"):
        passes, action_tick, att_atb, enemy_atb = _attacker_beats_enemy_atb(
            initiator_combat,
            att_combat_raw,
            atb_boost,
            has_spd_buff,
        )
        st.markdown(
            f"""
**Combat SPD** = `Base + Runas + floor(Base × (Líder% + 15%) / 100)`

**Tick bracket** = `ceil(100 / (Combat_SPD × 0,07))` → **Tick {ini_tick}**

**Motor:**
1. Avança ticks até o iniciador atingir ≥ 100% ATB (tick **{action_tick or ini_tick}** na simulação).
2. Aplica **+{atb_boost:.1f}%** de ATB no atacante.
3. Se buff ativo, ganho de ATB do atacante passa a usar **Combat × 1,3** nos ticks seguintes.
4. Roda **+1 tick** extra após o turno do iniciador.
5. Exige **ATB atacante > ATB inimigo** (inimigo = mesma combat SPD do iniciador).

**Resultado bruto (+{raw_rune} runas):** combat {att_combat_raw} — ATB final atacante **{att_atb:.2f}%** vs inimigo **{enemy_atb:.2f}%** ({'OK' if passes else 'falhou'}).

**Margem:** +{SAFETY_MARGIN_RUNE} SPD nas runas no valor final exibido.
            """
        )
