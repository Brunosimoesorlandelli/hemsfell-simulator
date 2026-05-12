"""
Hemsfell Heroes — Batch Runner
================================
Executa múltiplas partidas em sequência e acumula estatísticas.

Uso via main.py:
  python main.py sim --deck1 hero_gimble --deck2 hero_tifon --games 100
  python main.py sim --all-matchups --games 200
"""

from __future__ import annotations
import sys, os, random, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import Player, reset_iid
from engine.simulator import GameState
from engine.loader import load_data, build_card_pool, load_tags, build_deck_for_hero, hero_list
from engine.stats import Stats, save_report
from engine import logger


def _fmt_time(seconds: float) -> str:
    """Formata segundos em mm:ss ou hh:mm:ss."""
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def run_matchup(
    hero1_id: str,
    hero2_id: str,
    n_games: int,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    verbose: bool = False,
    seed_base: int | None = None,
    _progress_prefix: str = "",
    output_path: str | None = None,
) -> Stats:
    """Simula n_games entre dois heróis e retorna Stats."""
    logger.set_verbose(verbose)

    names   = {h["id"]: h["name"] for h in data.get("heroes", [])}
    p1_name = f"J1 ({names.get(hero1_id, hero1_id)})"
    p2_name = f"J2 ({names.get(hero2_id, hero2_id)})"
    stats   = Stats(hero1_id, hero2_id)

    # Escreve cabeçalho do arquivo uma única vez antes de iniciar as partidas
    if output_path:
        logger.write_header(output_path, p1_name, p2_name, n_games)

    t_start = time.perf_counter()

    for g in range(n_games):
        logger.clear()
        if seed_base is None:
            random.seed()
        else:
            random.seed(seed_base + g * 997)

        reset_iid()

        h1, d1 = build_deck_for_hero(hero1_id, data, card_pool, tags_db)
        h2, d2 = build_deck_for_hero(hero2_id, data, card_pool, tags_db)
        p1 = Player(name=p1_name, hero=h1, deck=d1)
        p2 = Player(name=p2_name, hero=h2, deck=d2)

        gs     = GameState(p1, p2, card_pool, tags_db)
        result = gs.run()
        stats.add(result)

        # Sempre despeja o log completo da partida no arquivo
        if output_path:
            logger.dump_to_file(output_path, g + 1, result["winner"])

        if verbose and g == 0:
            print("\n".join(logger.get_lines()))

        if not verbose and n_games > 1:
            elapsed   = time.perf_counter() - t_start
            avg_time  = elapsed / (g + 1)
            remaining = avg_time * (n_games - g - 1)
            pct       = (g + 1) / n_games * 100
            bar       = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            prefix    = f"  {_progress_prefix} " if _progress_prefix else "  "
            print(
                f"\r{prefix}[{bar}] {pct:5.1f}%  "
                f"{g+1}/{n_games} partidas  "
                f"~{_fmt_time(remaining)} restante",
                end="", flush=True,
            )

    if not verbose and n_games > 1:
        elapsed = time.perf_counter() - t_start
        r   = stats.results
        n   = len(r)
        w1  = sum(1 for x in r if x["winner"] == x["p1_name"])
        wr_p1 = 100 * w1 / n
        print(
            f"\r  {_progress_prefix}  ✓  "
            f"{names.get(hero1_id, hero1_id)[:10]} {wr_p1:.0f}% "
            f"× {100 - wr_p1:.0f}% "
            f"{names.get(hero2_id, hero2_id)[:10]}"
            f"  ({_fmt_time(elapsed)})"
            + " " * 20
        )

    return stats


def run_all_matchups(
    n_games: int,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    output_path: str,
) -> list[str]:
    """Simula todos os confrontos 1v1 e retorna lista de relatórios."""
    heroes   = [h["id"] for h in data.get("heroes", [])]
    matchups = [(h1, h2)
                for i, h1 in enumerate(heroes)
                for h2 in heroes[i + 1:]]

    total_matchups = len(matchups)
    total_games    = total_matchups * n_games

    print(f"\n🎮 {total_matchups} confrontos × {n_games} partidas = {total_games} jogos\n")

    reports  = []
    t_global = time.perf_counter()

    for idx, (h1, h2) in enumerate(matchups, 1):
        elapsed_global  = time.perf_counter() - t_global
        avg_per_matchup = elapsed_global / (idx - 1) if idx > 1 else 0
        eta_global      = avg_per_matchup * (total_matchups - idx + 1)
        eta_str         = f"  ETA global: {_fmt_time(eta_global)}" if idx > 1 else ""

        names = {h["id"]: h["name"][:10] for h in data.get("heroes", [])}
        print(
            f"  [{idx:>2}/{total_matchups}] "
            f"{names.get(h1, h1)} vs {names.get(h2, h2)}"
            f"{eta_str}"
        )

        stats = run_matchup(
            h1, h2, n_games, data, card_pool, tags_db,
            verbose=False,
            _progress_prefix=f"[{idx}/{total_matchups}]",
            output_path=output_path,
        )
        rep = stats.report()
        reports.append(rep)

    total_elapsed = time.perf_counter() - t_global
    print(f"\n✅ Concluído em {_fmt_time(total_elapsed)}  ({total_games} partidas simuladas)")

    save_report(reports, output_path, append=True)
    return reports
