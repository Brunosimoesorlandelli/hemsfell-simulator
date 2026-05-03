"""
Benchmark por deck com métricas estratégicas.
"""

from __future__ import annotations

import os

from engine.deck_strategy import analyze_deck_strategy
from tools.batch_runner import run_matchup


def _new_agg(strategy):
    return {
        "strategy": strategy,
        "games": 0,
        "wins": 0,
        "turns_win_sum": 0.0,
        "turns_win_n": 0,
        "combo_success": 0,
        "lvl3_games": 0,
        "interaction_sum": 0.0,
        "mana_eff_sum": 0.0,
        "mana_eff_n": 0,
        "max_energy_sum": 0.0,
        "resilient_wins": 0,
        "total_damage_dealt": 0.0,
    }


def _consistency_success(style: str, m: dict, dealt_damage: float, won: bool, turns: int) -> bool:
    if style == "combo_engine":
        return m["combo_turns"] >= 1 and m["spells_cast_total"] >= 2
    if style == "control_spells":
        return m["interaction_plays"] >= 2 and m["mana_efficiency"] >= 0.55
    if style == "aggro_swarm":
        return m["creatures_played_total"] >= 3 and (won and turns <= 12 or dealt_damage >= 15)
    if style == "ramp_level":
        return m["level3_reached"] or m["max_energy_reached"] >= 9
    if style == "midrange_big":
        return m["max_energy_reached"] >= 8 and m["creatures_played_total"] >= 2
    return m["cards_played_total"] >= 2 and m["mana_efficiency"] >= 0.6


def build_deck_metrics_report(
    games: int,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    output_path: str | None = None,
    hero_subset: list[str] | None = None,
) -> str:
    heroes = hero_subset if hero_subset else [d["hero_id"] for d in data.get("decks", [])]
    if len(heroes) < 2:
        raise ValueError("É necessário ter ao menos 2 decks.")

    strategies = {
        h: analyze_deck_strategy(h, data, card_pool, tags_db)
        for h in heroes
    }
    agg = {h: _new_agg(strategies[h]) for h in heroes}

    total = len(heroes) * (len(heroes) - 1) // 2
    done = 0
    for i, h1 in enumerate(heroes):
        for h2 in heroes[i + 1:]:
            done += 1
            print(f"[deck-metrics] {done}/{total} {h1} vs {h2}")
            stats = run_matchup(h1, h2, games, data, card_pool, tags_db, verbose=False)
            for r in stats.results:
                for side, hero_id in (("p1", h1), ("p2", h2)):
                    m = r[f"{side}_metrics"]
                    won = r["winner"] == r[f"{side}_name"]
                    dmg = r[f"{side}_damage"]
                    a = agg[hero_id]
                    a["games"] += 1
                    a["wins"] += 1 if won else 0
                    a["total_damage_dealt"] += dmg
                    a["interaction_sum"] += m["interaction_plays"]
                    a["mana_eff_sum"] += m["mana_efficiency"]
                    a["mana_eff_n"] += 1
                    a["max_energy_sum"] += m["max_energy_reached"]
                    a["lvl3_games"] += 1 if m["level3_reached"] else 0
                    if won:
                        a["turns_win_sum"] += r["turns"]
                        a["turns_win_n"] += 1
                        if m["life_min"] <= 8:
                            a["resilient_wins"] += 1

                    if _consistency_success(a["strategy"].style, m, dmg, won, r["turns"]):
                        a["combo_success"] += 1

    lines = []
    lines.append("")
    lines.append("DECK METRICS REPORT")
    lines.append("=" * 96)
    lines.append("Métricas por deck: WR, consistência, velocidade, resiliência/interação e eficiência de recursos.")
    lines.append("")

    ranked = sorted(
        heroes,
        key=lambda h: (agg[h]["wins"] / max(1, agg[h]["games"])),
        reverse=True,
    )
    for h in ranked:
        a = agg[h]
        s = a["strategy"]
        wr = 100.0 * a["wins"] / max(1, a["games"])
        consistency = 100.0 * a["combo_success"] / max(1, a["games"])
        speed = a["turns_win_sum"] / max(1, a["turns_win_n"])
        resilience = 100.0 * a["resilient_wins"] / max(1, a["wins"])
        interaction = a["interaction_sum"] / max(1, a["games"])
        mana_eff = 100.0 * a["mana_eff_sum"] / max(1, a["mana_eff_n"])
        max_energy = a["max_energy_sum"] / max(1, a["games"])
        avg_dmg = a["total_damage_dealt"] / max(1, a["games"])
        lvl3_rate = 100.0 * a["lvl3_games"] / max(1, a["games"])

        lines.append(f"{h}")
        lines.append(
            f"  Estratégia: {s.style} | custo médio {s.avg_cost:.2f} | "
            f"criaturas {100*s.creature_ratio:.1f}% | feitiços {100*s.spell_ratio:.1f}%"
        )
        lines.append(f"  Leitura: {s.rationale}")
        lines.append(f"  WR: {wr:.2f}%")
        lines.append(f"  Consistência ({s.style}): {consistency:.2f}%")
        lines.append(f"  Velocidade (turno médio da vitória): {speed:.2f}")
        lines.append(
            f"  Resiliência/Interação: resiliência em vitórias apertadas {resilience:.2f}% | "
            f"interações por jogo {interaction:.2f}"
        )
        lines.append(
            f"  Eficiência de mana/recursos: {mana_eff:.2f}% | "
            f"energia máxima média {max_energy:.2f} | taxa de nível 3 {lvl3_rate:.2f}%"
        )
        lines.append(f"  Dano médio causado por jogo: {avg_dmg:.2f}")
        lines.append("-" * 96)

    report = "\n".join(lines)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
    return report
