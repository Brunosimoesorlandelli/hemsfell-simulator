"""
Avaliacao da evolucao da IA com politica RL.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from tools.batch_runner import run_matchup


@dataclass
class EvalMetrics:
    p1_wr: float
    p2_wr: float
    draws: float
    avg_turns: float
    avg_winner_level: float
    avg_dmg_p1: float
    avg_dmg_p2: float
    n_games: int
    p1_wins: int


def _metrics(stats) -> EvalMetrics:
    r = stats.results
    n = len(r) if r else 1
    wins_p1 = sum(1 for x in r if x["winner"] == x["p1_name"])
    wins_p2 = sum(1 for x in r if x["winner"] == x["p2_name"])
    draws = n - wins_p1 - wins_p2
    winner_lvls = [x.get("winner_level", 1) for x in r if x["winner"] != "Empate"]
    avg_lvl = (sum(winner_lvls) / len(winner_lvls)) if winner_lvls else 1.0
    return EvalMetrics(
        p1_wr=100.0 * wins_p1 / n,
        p2_wr=100.0 * wins_p2 / n,
        draws=100.0 * draws / n,
        avg_turns=sum(x["turns"] for x in r) / n,
        avg_winner_level=avg_lvl,
        avg_dmg_p1=sum(x["p1_damage"] for x in r) / n,
        avg_dmg_p2=sum(x["p2_damage"] for x in r) / n,
        n_games=n,
        p1_wins=wins_p1,
    )


def _parse_seeds(seeds: str | None) -> list[int]:
    if not seeds:
        return [11, 29, 47]
    out = []
    for tok in seeds.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(int(tok))
    if not out:
        return [11, 29, 47]
    return out


def _parse_critical_matchups(critical_matchups: str | None) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not critical_matchups:
        return out
    if os.path.exists(critical_matchups):
        with open(critical_matchups, "r", encoding="utf-8") as f:
            raw = ",".join(line.strip() for line in f if line.strip())
    else:
        raw = critical_matchups
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            h1, h2 = token.split(":", 1)
        elif ">" in token:
            h1, h2 = token.split(">", 1)
        else:
            continue
        out.add((h1.strip(), h2.strip()))
    return out


def _pair_list(data: dict, deck1: str | None, deck2: str | None, all_matchups: bool) -> list[tuple[str, str]]:
    heroes = [d["hero_id"] for d in data.get("decks", [])]
    if deck1 and deck2:
        return [(deck1, deck2)]
    if all_matchups:
        pairs = []
        for i, h1 in enumerate(heroes):
            for h2 in heroes[i + 1:]:
                pairs.append((h1, h2))
        return pairs
    if len(heroes) < 2:
        raise ValueError("E necessario ao menos 2 decks para rl-eval.")
    return [(heroes[0], heroes[1])]


def _ci95_for_wr_percent(wins: int, n: int) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = wins / n
    se = math.sqrt((p * (1 - p)) / n)
    delta = 1.96 * se
    lo = max(0.0, (p - delta) * 100.0)
    hi = min(100.0, (p + delta) * 100.0)
    return (lo, hi)


def _ci95_for_delta_pp(wins_a: int, n_a: int, wins_b: int, n_b: int) -> tuple[float, float]:
    if n_a <= 0 or n_b <= 0:
        return (0.0, 0.0)
    pa = wins_a / n_a
    pb = wins_b / n_b
    se = math.sqrt((pa * (1 - pa) / n_a) + (pb * (1 - pb) / n_b))
    delta = 1.96 * se
    d = (pa - pb) * 100.0
    return (d - delta * 100.0, d + delta * 100.0)


def evaluate_policy(
    data: dict,
    card_pool: dict,
    tags_db: dict,
    policy_path: str,
    games: int,
    deck1: str | None = None,
    deck2: str | None = None,
    all_matchups: bool = False,
    output_path: str | None = None,
    seeds: str | None = None,
    critical_matchups: str | None = None,
    with_ci: bool = False,
) -> str:
    if not policy_path:
        raise ValueError("policy_path e obrigatorio para rl-eval.")

    seed_list = _parse_seeds(seeds)
    critical_pairs = _parse_critical_matchups(critical_matchups)
    pairs = _pair_list(data, deck1, deck2, all_matchups)

    lines: list[str] = []
    lines.append("")
    lines.append("RL EVAL - BASE VS RL POLICY")
    lines.append("=" * 88)
    lines.append(f"Politica: {policy_path}")
    lines.append(f"Partidas por confronto por seed: {games}")
    lines.append(f"Seeds: {seed_list}")
    lines.append("")

    global_base_wins = 0
    global_rl_wins = 0
    global_total_games = 0
    critical_ok = True

    for i, (h1, h2) in enumerate(pairs, start=1):
        print(f"[rl-eval] {i}/{len(pairs)} {h1} vs {h2} ...")
        pair_base_wins = 0
        pair_rl_wins = 0
        pair_games = 0
        base_turns = []
        rl_turns = []
        base_winner_levels = []
        rl_winner_levels = []
        base_dmg_p1 = []
        rl_dmg_p1 = []
        base_dmg_p2 = []
        rl_dmg_p2 = []

        for s_idx, seed_base in enumerate(seed_list):
            print(f"  seed {seed_base} ({s_idx+1}/{len(seed_list)}) base...", end="", flush=True)
            base = run_matchup(
                h1, h2, games, data, card_pool, tags_db,
                verbose=False, rl_policy_path=None, seed_base=seed_base,
            )
            print(" rl...", end="", flush=True)
            rl = run_matchup(
                h1, h2, games, data, card_pool, tags_db,
                verbose=False, rl_policy_path=policy_path, seed_base=seed_base,
            )
            print(" ok")
            mb = _metrics(base)
            mr = _metrics(rl)
            pair_base_wins += mb.p1_wins
            pair_rl_wins += mr.p1_wins
            pair_games += mb.n_games
            base_turns.append(mb.avg_turns)
            rl_turns.append(mr.avg_turns)
            base_winner_levels.append(mb.avg_winner_level)
            rl_winner_levels.append(mr.avg_winner_level)
            base_dmg_p1.append(mb.avg_dmg_p1)
            rl_dmg_p1.append(mr.avg_dmg_p1)
            base_dmg_p2.append(mb.avg_dmg_p2)
            rl_dmg_p2.append(mr.avg_dmg_p2)

        pair_base_wr = (pair_base_wins / max(1, pair_games)) * 100.0
        pair_rl_wr = (pair_rl_wins / max(1, pair_games)) * 100.0
        delta_pp = pair_rl_wr - pair_base_wr

        global_base_wins += pair_base_wins
        global_rl_wins += pair_rl_wins
        global_total_games += pair_games

        is_critical = (h1, h2) in critical_pairs
        if is_critical and delta_pp < -3.0:
            critical_ok = False

        avg_base_turns = sum(base_turns) / max(1, len(base_turns))
        avg_rl_turns = sum(rl_turns) / max(1, len(rl_turns))
        avg_base_lvl = sum(base_winner_levels) / max(1, len(base_winner_levels))
        avg_rl_lvl = sum(rl_winner_levels) / max(1, len(rl_winner_levels))
        avg_base_dmg_p1 = sum(base_dmg_p1) / max(1, len(base_dmg_p1))
        avg_rl_dmg_p1 = sum(rl_dmg_p1) / max(1, len(rl_dmg_p1))
        avg_base_dmg_p2 = sum(base_dmg_p2) / max(1, len(base_dmg_p2))
        avg_rl_dmg_p2 = sum(rl_dmg_p2) / max(1, len(rl_dmg_p2))

        lines.append(f"{h1} vs {h2}{' [CRITICAL]' if is_critical else ''}")
        lines.append(
            f"  Base P1 WR {pair_base_wr:5.1f}% | RL P1 WR {pair_rl_wr:5.1f}% | Delta {delta_pp:+5.1f} pp"
        )
        if with_ci:
            bci = _ci95_for_wr_percent(pair_base_wins, pair_games)
            rci = _ci95_for_wr_percent(pair_rl_wins, pair_games)
            dci = _ci95_for_delta_pp(pair_rl_wins, pair_games, pair_base_wins, pair_games)
            lines.append(f"  CI95 base [{bci[0]:.1f}, {bci[1]:.1f}] | rl [{rci[0]:.1f}, {rci[1]:.1f}] | delta [{dci[0]:+.1f}, {dci[1]:+.1f}]")
        lines.append(
            f"  Turnos base {avg_base_turns:5.1f} | rl {avg_rl_turns:5.1f} | "
            f"Lvl vencedor base {avg_base_lvl:.2f} | rl {avg_rl_lvl:.2f}"
        )
        lines.append(
            f"  Dano medio P1 base {avg_base_dmg_p1:5.1f} | rl {avg_rl_dmg_p1:5.1f} ; "
            f"P2 base {avg_base_dmg_p2:5.1f} | rl {avg_rl_dmg_p2:5.1f}"
        )
        lines.append("")

    avg_base = (global_base_wins / max(1, global_total_games)) * 100.0
    avg_rl = (global_rl_wins / max(1, global_total_games)) * 100.0
    delta = avg_rl - avg_base
    promote = (delta > 2.0) and critical_ok

    lines.append("-" * 88)
    lines.append(f"Media WR P1 (base): {avg_base:.2f}%")
    lines.append(f"Media WR P1 (rl)  : {avg_rl:.2f}%")
    lines.append(f"Ganho medio (pp)  : {delta:+.2f}")
    if with_ci:
        g_bci = _ci95_for_wr_percent(global_base_wins, global_total_games)
        g_rci = _ci95_for_wr_percent(global_rl_wins, global_total_games)
        g_dci = _ci95_for_delta_pp(global_rl_wins, global_total_games, global_base_wins, global_total_games)
        lines.append(f"CI95 global base [{g_bci[0]:.2f}, {g_bci[1]:.2f}]")
        lines.append(f"CI95 global rl   [{g_rci[0]:.2f}, {g_rci[1]:.2f}]")
        lines.append(f"CI95 delta (pp)  [{g_dci[0]:+.2f}, {g_dci[1]:+.2f}]")
    lines.append(f"Criterio de promocao: {'PASSOU' if promote else 'NAO PASSOU'}")
    lines.append("-" * 88)

    report = "\n".join(lines)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
    return report
