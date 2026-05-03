"""
Análise de estratégia por deck para guiar métricas.
"""

from __future__ import annotations

from dataclasses import dataclass

from .loader import build_deck_for_hero


@dataclass
class DeckStrategy:
    style: str
    creature_ratio: float
    spell_ratio: float
    avg_cost: float
    interaction_density: float
    ramp_density: float
    rationale: str


def analyze_deck_strategy(hero_id: str, data: dict, card_pool: dict, tags_db: dict) -> DeckStrategy:
    _, deck = build_deck_for_hero(hero_id, data, card_pool, tags_db)
    if not deck:
        return DeckStrategy(
            style="midrange",
            creature_ratio=0.0,
            spell_ratio=0.0,
            avg_cost=0.0,
            interaction_density=0.0,
            ramp_density=0.0,
            rationale="Deck vazio.",
        )

    n = len(deck)
    creatures = [c for c in deck if c.card_type in ("creature", "image")]
    spells = [c for c in deck if c.card_type == "spell"]
    avg_cost = sum(c.cost for c in deck) / n

    interaction_actions = {"destroy", "deal_damage", "return_hand", "apply_status", "tap", "force_discard"}
    ramp_actions = {"add_energy", "increase_max_energy", "fill_reserve", "add_reserve"}
    interaction_count = 0
    ramp_count = 0
    combo_count = 0
    for c in deck:
        actions = {t.get("action", "") for t in c.effect_tags}
        if any(a in interaction_actions for a in actions):
            interaction_count += 1
        if any(a in ramp_actions for a in actions):
            ramp_count += 1
        if any(a in actions for a in ("draw", "search", "revive", "discard_hand_draw_same", "element_bonus")):
            combo_count += 1

    creature_ratio = len(creatures) / n
    spell_ratio = len(spells) / n
    interaction_density = interaction_count / n
    ramp_density = ramp_count / n
    combo_density = combo_count / n

    style = "midrange"
    rationale = "Curva e composição equilibradas."
    if spell_ratio >= 0.45 and interaction_density >= 0.18:
        style = "control_spells"
        rationale = "Alta densidade de feitiços e interação."
    elif combo_density >= 0.22 and spell_ratio >= 0.30:
        style = "combo_engine"
        rationale = "Muitas peças de geração de valor/combo."
    elif creature_ratio >= 0.62 and avg_cost <= 3.0:
        style = "aggro_swarm"
        rationale = "Muitas criaturas com curva baixa."
    elif creature_ratio >= 0.55 and avg_cost >= 3.6:
        style = "midrange_big"
        rationale = "Plano de mesa com corpos maiores."
    elif ramp_density >= 0.10:
        style = "ramp_level"
        rationale = "Presença relevante de ramp/recursos."

    return DeckStrategy(
        style=style,
        creature_ratio=creature_ratio,
        spell_ratio=spell_ratio,
        avg_cost=avg_cost,
        interaction_density=interaction_density,
        ramp_density=ramp_density,
        rationale=rationale,
    )

