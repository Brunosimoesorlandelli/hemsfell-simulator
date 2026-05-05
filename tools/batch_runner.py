"""
Hemsfell Heroes — Batch Runner
================================
Executa múltiplas partidas em sequência e acumula estatísticas.

Uso via main.py:
  python main.py sim --deck1 hero_gimble --deck2 hero_tifon --games 100
  python main.py sim --all-matchups --games 200
"""

from __future__ import annotations
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import Player
from engine.simulator import GameState
from engine.rl_agent import DQNPolicy, RLEpisodeRuntime
from engine.loader import load_data, build_card_pool, load_tags, build_deck_for_hero, hero_list
from engine.stats import Stats, save_report
from engine import logger


def run_matchup(
    hero1_id: str,
    hero2_id: str,
    n_games: int,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    verbose: bool = False,
    rl_policy_path: str | None = None,
    seed_base: int | None = None,
) -> Stats:
    """Simula n_games entre dois heróis e retorna Stats."""
    logger.set_verbose(verbose)

    names = {h["id"]: h["name"] for h in data.get("heroes", [])}
    p1_name = f"J1 ({names.get(hero1_id, hero1_id)})"
    p2_name = f"J2 ({names.get(hero2_id, hero2_id)})"
    stats   = Stats(hero1_id, hero2_id)
    policy = DQNPolicy.load(rl_policy_path) if rl_policy_path else None

    for g in range(n_games):
        logger.clear()
        if seed_base is None:
            random.seed()
        else:
            random.seed(seed_base + g * 997)

        from engine.models import reset_iid
        reset_iid()

        h1, d1 = build_deck_for_hero(hero1_id, data, card_pool, tags_db)
        h2, d2 = build_deck_for_hero(hero2_id, data, card_pool, tags_db)
        p1 = Player(name=p1_name, hero=h1, deck=d1)
        p2 = Player(name=p2_name, hero=h2, deck=d2)

        gs     = GameState(p1, p2, card_pool, tags_db)
        if policy is not None:
            gs.rl_runtime = RLEpisodeRuntime(
                policy=policy,
                training=False,
                epsilon=0.0,
                alpha=0.0,
            )
        result = gs.run()
        stats.add(result)

        if verbose and g == 0:
            print("\n".join(logger.get_lines()))

        if not verbose and n_games > 1:
            pct = (g+1)/n_games*100
            bar = "#" * int(pct/5) + "-" * (20-int(pct/5))
            print(f"\r  [{bar}] {pct:5.1f}%  {g+1}/{n_games}", end="", flush=True)

    if not verbose and n_games > 1:
        print()

    return stats


def run_all_matchups(
    n_games: int,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    output_path: str,
    rl_policy_path: str | None = None,
) -> list[str]:
    """Simula todos os confrontos 1v1 e retorna lista de relatórios."""
    heroes   = [h["id"] for h in data.get("heroes", [])]
    matchups = [(h1, h2)
                for i, h1 in enumerate(heroes)
                for h2 in heroes[i+1:]]

    print(f"\n🎮 Simulando {len(matchups)} confrontos × {n_games} partidas…\n")

    reports = []
    for h1, h2 in matchups:
        print(f"  {h1} vs {h2} …", end="", flush=True)
        stats = run_matchup(
            h1, h2, n_games, data, card_pool, tags_db,
            verbose=False, rl_policy_path=rl_policy_path
        )
        rep   = stats.report()
        reports.append(rep)

        r  = stats.results
        n  = len(r)
        w1 = sum(1 for x in r if x["winner"] == x["p1_name"])
        print(f" {100*w1/n:.0f}% vs {100*(n-w1)/n:.0f}%")

    save_report(reports, output_path)
    return reports
