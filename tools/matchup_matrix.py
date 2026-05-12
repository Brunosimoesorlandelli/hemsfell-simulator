"""
Hemsfell Heroes — Matchup Matrix
==================================
Gera uma tabela ASCII mostrando a taxa de vitória de cada herói contra todos.

Uso:
  python main.py matrix --games 100
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.batch_runner import run_matchup
from engine.loader import load_data, build_card_pool, load_tags


def build_matrix(n_games: int, data: dict, card_pool: dict, tags_db: dict) -> str:
    heroes = [h["id"] for h in data.get("heroes", [])]
    names  = {h["id"]: h["name"][:10] for h in data.get("heroes", [])}

    win_rate: dict[str, dict[str, float]] = {h: {} for h in heroes}

    total = len(heroes) * (len(heroes) - 1) // 2
    done  = 0
    for i, h1 in enumerate(heroes):
        for h2 in heroes[i + 1:]:
            done += 1
            print(f"\r  [{done}/{total}] {names[h1]} vs {names[h2]}…", end="", flush=True)
            stats = run_matchup(h1, h2, n_games, data, card_pool, tags_db)
            r     = stats.results
            n     = len(r)
            w1    = sum(1 for x in r if x["winner"] == x["p1_name"])
            win_rate[h1][h2] = 100 * w1 / n
            win_rate[h2][h1] = 100 * (n - w1) / n
    print()

    col_w  = 11
    header = " " * 12 + "".join(names[h].ljust(col_w) for h in heroes)
    lines  = [
        "",
        "MATCHUP MATRIX (% vitória da linha contra a coluna)",
        "─" * len(header),
        header,
    ]
    for h1 in heroes:
        row = names[h1].ljust(12)
        for h2 in heroes:
            if h1 == h2:
                row += "   —  ".ljust(col_w)
            else:
                v = win_rate[h1].get(h2, 0)
                row += f"{v:5.1f}%".ljust(col_w)
        lines.append(row)

    avg    = {}
    for h in heroes:
        vals   = [v for h2, v in win_rate[h].items() if h2 != h]
        avg[h] = sum(vals) / len(vals) if vals else 0
    ranked = sorted(avg.items(), key=lambda x: x[1], reverse=True)
    lines.append("")
    lines.append("RANKING POR WIN-RATE MÉDIA:")
    for i, (h, wr) in enumerate(ranked, 1):
        lines.append(f"  {i:>2}. {names[h]:<12} {wr:.1f}%")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=50)
    args = parser.parse_args()

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()
    result    = build_matrix(args.games, data, card_pool, tags_db)
    print(result)
