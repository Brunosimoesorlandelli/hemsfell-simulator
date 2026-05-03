"""
Hemsfell Heroes — Deck Inspector
==================================
Inspeciona o deck de um herói: lista cartas, contagem por tipo e custo médio.

Uso:
  python main.py inspect --deck hero_gimble
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter
from engine.loader import load_data, build_card_pool, load_tags, build_deck_for_hero


def inspect_deck(hero_id: str, data: dict, card_pool: dict, tags_db: dict) -> str:
    hero, deck = build_deck_for_hero(hero_id, data, card_pool, tags_db)
    lines = [
        f"\n╔══════════════════════════════════════╗",
        f"║  Deck: {hero.name[:32]:<32} ║",
        f"╚══════════════════════════════════════╝",
        f"  Total de cartas: {len(deck)}",
        "",
    ]

    by_type: dict[str, list] = {}
    for c in deck:
        by_type.setdefault(c.card_type, []).append(c)

    type_labels = {
        "creature": "Criaturas", "spell": "Feitiços",
        "artifact": "Artefatos", "enchant": "Encantos",
        "terrain":  "Terrenos",  "image":  "Imagens",
    }
    for ctype, cards in sorted(by_type.items()):
        lines.append(f"  ── {type_labels.get(ctype, ctype)} ({len(cards)}) ──")
        counts = Counter(c.name for c in cards)
        for name, n in sorted(counts.items()):
            c = next(x for x in cards if x.name == name)
            kw = ", ".join(c.keywords) if c.keywords else "—"
            if ctype == "creature":
                lines.append(f"    {n}x {name:<32} {c.cost}◆  "
                              f"{c.offense}/{c.vitality}  [{kw}]")
            else:
                lines.append(f"    {n}x {name:<32} {c.cost}◆")
        lines.append("")

    costs  = [c.cost for c in deck]
    avg    = sum(costs) / len(costs) if costs else 0
    curve  = Counter(costs)
    lines.append(f"  Custo médio: {avg:.2f}◆")
    lines.append("  Curva de custo:")
    for cost in sorted(curve):
        bar = "█" * curve[cost]
        lines.append(f"    {cost}◆  {bar} ({curve[cost]})")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", default="hero_gimble")
    args = parser.parse_args()

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()
    print(inspect_deck(args.deck, data, card_pool, tags_db))
