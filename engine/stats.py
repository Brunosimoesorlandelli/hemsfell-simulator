"""
Hemsfell Heroes — Estatísticas
================================
Coleta resultados de múltiplas partidas e gera relatórios.
"""

from __future__ import annotations
import time
from collections import Counter


class Stats:
    def __init__(self, p1_hero: str, p2_hero: str):
        self.p1_hero = p1_hero
        self.p2_hero = p2_hero
        self.results: list[dict] = []

    def add(self, r: dict):
        self.results.append(r)

    def report(self) -> str:
        n = len(self.results)
        if n == 0:
            return "Sem resultados."

        wins_p1 = sum(1 for r in self.results if r["winner"] == r["p1_name"])
        wins_p2 = sum(1 for r in self.results if r["winner"] == r["p2_name"])
        draws   = n - wins_p1 - wins_p2

        avg_turns = sum(r["turns"] for r in self.results) / n
        winner_levels = [r.get("winner_level", 1) for r in self.results
                         if r["winner"] != "Empate"]
        avg_lvl_w = sum(winner_levels) / len(winner_levels) if winner_levels else 1.0
        avg_life_winner = []
        for r in self.results:
            if r["winner"] == r["p1_name"]:
                avg_life_winner.append(r["p1_life"])
            elif r["winner"] == r["p2_name"]:
                avg_life_winner.append(r["p2_life"])
        avg_life_w = sum(avg_life_winner) / len(avg_life_winner) if avg_life_winner else 0

        avg_dmg_p1   = sum(r["p1_damage"] for r in self.results) / n
        avg_dmg_p2   = sum(r["p2_damage"] for r in self.results) / n
        avg_kills_p1 = sum(r["p1_kills"]  for r in self.results) / n
        avg_kills_p2 = sum(r["p2_kills"]  for r in self.results) / n

        all_p1 = Counter()
        all_p2 = Counter()
        for r in self.results:
            all_p1.update(r["p1_cards"])
            all_p2.update(r["p2_cards"])
        top_p1 = all_p1.most_common(5)
        top_p2 = all_p2.most_common(5)

        p1_name = self.results[0]["p1_name"]
        p2_name = self.results[0]["p2_name"]

        lines = [
            "",
            "╔" + "═" * 62 + "╗",
            f"║  RELATÓRIO: {p1_name} vs {p2_name}",
            f"║  ({n} partidas simuladas)",
            "╠" + "═" * 62 + "╣",
            f"║  🏆 Vitórias  {p1_name:<25} {wins_p1:>5} ({100*wins_p1/n:.1f}%)",
            f"║  🏆 Vitórias  {p2_name:<25} {wins_p2:>5} ({100*wins_p2/n:.1f}%)",
            f"║  🤝 Empates                                {draws:>5} ({100*draws/n:.1f}%)",
            "╠" + "═" * 62 + "╣",
            f"║  ⏱️  Turnos médios:                      {avg_turns:.1f}",
            f"║  🌟 Nível médio do vencedor:            {avg_lvl_w:.2f}",
            f"║  ❤️  Vida média do vencedor:            {avg_life_w:.1f}",
            f"║  ⚔️  Dano médio {p1_name:<20} {avg_dmg_p1:.1f}",
            f"║  ⚔️  Dano médio {p2_name:<20} {avg_dmg_p2:.1f}",
            f"║  💀 Abates médios {p1_name:<18} {avg_kills_p1:.1f}",
            f"║  💀 Abates médios {p2_name:<18} {avg_kills_p2:.1f}",
            "╠" + "═" * 62 + "╣",
            f"║  📋 Cartas mais jogadas — {p1_name}:",
        ]
        for name, cnt in top_p1:
            lines.append(f"║     {name:<38} {cnt:>5}x")
        lines.append(f"║  📋 Cartas mais jogadas — {p2_name}:")
        for name, cnt in top_p2:
            lines.append(f"║     {name:<38} {cnt:>5}x")
        lines.append("╚" + "═" * 62 + "╝")
        return "\n".join(lines)


def save_report(reports: list[str], path: str):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("HEMSFELL HEROES — RELATÓRIO DE SIMULAÇÕES\n")
        f.write(f"Gerado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 64 + "\n\n")
        for r in reports:
            f.write(r + "\n\n")
    print(f"\n📄 Relatório salvo em: {path}")
