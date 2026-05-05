"""
╔══════════════════════════════════════════════════════════════════════╗
║        HEMSFELL HEROES — PONTO DE ENTRADA UNIFICADO                 ║
╚══════════════════════════════════════════════════════════════════════╝

Comandos disponíveis:

  sim          Simula partidas entre dois heróis
  rl-train     Treina política de RL em várias partidas
  rl-eval      Avalia base vs política RL treinada
  deck-metrics Gera métricas estratégicas por deck
  deck-lab     Ferramenta de tuning e benchmark de variantes de deck
  matrix       Tabela de matchups todos-vs-todos
  inspect      Inspeciona o deck de um herói
  heroes       Lista todos os heróis disponíveis

Exemplos:
  python main.py sim --deck1 hero_gimble --deck2 hero_tifon
  python main.py sim --deck1 hero_gimble --deck2 hero_tifon --rl-policy reports/rl_policy.json
  python main.py sim --deck1 hero_tesslia --deck2 hero_rasmus --games 500
  python main.py sim --all-matchups --games 200
  python main.py rl-train --episodes 1000 --all-matchups
  python main.py rl-eval --all-matchups --games 100 --policy-path reports/rl_policy.json
  python main.py deck-metrics --games 50
  python main.py matrix --games 100
  python main.py inspect --deck hero_gimble
  python main.py heroes
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.loader import load_data, build_card_pool, load_tags, hero_list
from engine.config import CARDS_PATH, REPORTS_DIR


def cmd_sim(args):
    from tools.batch_runner import run_matchup, run_all_matchups
    from engine.stats import save_report
    import os

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    output    = os.path.join(REPORTS_DIR, "stats_report.log")

    if args.all_matchups:
        run_all_matchups(
            args.games, data, card_pool, tags_db, output,
            rl_policy_path=args.rl_policy,
        )
        return

    verbose = args.verbose or args.games == 1
    print(f"\n🎮 {args.deck1} vs {args.deck2} — {args.games} partida(s)\n")
    stats = run_matchup(
        args.deck1, args.deck2,
        args.games, data, card_pool, tags_db,
        verbose=verbose,
        rl_policy_path=args.rl_policy,
    )
    rep = stats.report()
    print(rep)
    save_report([rep], output)


def cmd_rl_train(args):
    from tools.rl_trainer import train_policy
    import os

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()

    policy_path = args.policy_path
    if not os.path.isabs(policy_path):
        policy_path = os.path.join(os.path.dirname(__file__), policy_path)

    print(f"\n🧠 Treinando RL por {args.episodes} episódio(s)")
    print(f"📁 Política: {policy_path}")

    result = train_policy(
        episodes=args.episodes,
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        policy_path=policy_path,
        deck1=args.deck1,
        deck2=args.deck2,
        all_matchups=args.all_matchups,
        epsilon_start=args.epsilon_start,
        epsilon_end=args.epsilon_end,
        alpha=args.alpha,
        seed=args.seed,
        eval_every=args.eval_every,
        curriculum=args.curriculum,
        save_best=args.save_best,
    )

    print("\n✅ Treino concluído")
    print(f"Episódios: {result['episodes']}")
    print(f"Política salva em: {result['policy_path']}")
    if result.get("best_checkpoint_tag"):
        print(f"Best checkpoint: {result['best_checkpoint_tag']}")
    if result.get("best_policy_path"):
        print(f"Best policy path: {result['best_policy_path']}")
    print("Vitórias registradas:")
    for k, v in sorted(result["wins"].items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {k}: {v}")


def cmd_rl_eval(args):
    from tools.rl_eval import evaluate_policy
    import os

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()

    policy_path = args.policy_path
    if not os.path.isabs(policy_path):
        policy_path = os.path.join(os.path.dirname(__file__), policy_path)

    output_path = args.output
    if output_path and (not os.path.isabs(output_path)):
        output_path = os.path.join(os.path.dirname(__file__), output_path)

    print("\n📈 Executando RL eval (base vs política)...")
    report = evaluate_policy(
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        policy_path=policy_path,
        games=args.games,
        deck1=args.deck1,
        deck2=args.deck2,
        all_matchups=args.all_matchups,
        output_path=output_path,
        seeds=args.seeds,
        critical_matchups=args.critical_matchups,
        with_ci=args.with_ci,
    )
    print(report)
    if output_path:
        print(f"\n📄 Relatório salvo em: {output_path}")


def cmd_deck_metrics(args):
    from tools.deck_metrics import build_deck_metrics_report
    import os

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()

    out = args.output
    if out and (not os.path.isabs(out)):
        out = os.path.join(os.path.dirname(__file__), out)

    print("\n📊 Gerando métricas detalhadas por deck...")
    report = build_deck_metrics_report(
        games=args.games,
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        output_path=out,
    )
    print(report)
    if out:
        print(f"\n📄 Relatório salvo em: {out}")


def cmd_matrix(args):
    from tools.matchup_matrix import build_matrix
    import os

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()
    result    = build_matrix(args.games, data, card_pool, tags_db)
    print(result)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, "matchup_matrix.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\n📄 Matriz salva em: {path}")


def cmd_inspect(args):
    from tools.deck_inspector import inspect_deck

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()
    print(inspect_deck(args.deck, data, card_pool, tags_db))


def cmd_heroes(args):
    data   = load_data()
    heroes = hero_list(data)
    print("\n🦸 Heróis disponíveis:\n")
    for h in heroes:
        print(f"  {h['id']:<32}  {h['name']}")
    print()


def cmd_deck_lab(args):
    from tools.deck_lab import (
        auto_create_and_benchmark_all_variants,
        create_variant,
        edit_variant,
        report_variant_run,
        run_variant,
    )

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()

    if args.decklab_cmd == "create":
        variant = create_variant(
            variant_id=args.variant_id,
            hero_id=args.hero,
            name=args.name,
            data=data,
            card_pool=card_pool,
        )
        print(f"\n[ok] Variante criada: {variant['variant_id']}")
        print(f"Herói base: {variant['base_hero_id']}")
        print(f"Cartas: {len(variant['cards'])}")
        return

    if args.decklab_cmd == "edit":
        variant = edit_variant(
            variant_id=args.variant_id,
            add_specs=args.add or [],
            remove_specs=args.remove or [],
            data=data,
            card_pool=card_pool,
        )
        print(f"\n[ok] Variante atualizada: {variant['variant_id']}")
        print(f"Cartas: {len(variant['cards'])}")
        return

    if args.decklab_cmd == "run":
        result = run_variant(
            variant_id=args.variant_id,
            data=data,
            card_pool=card_pool,
            tags_db=tags_db,
            games=args.games,
            vs_hero=args.vs,
            all_matchups=args.all_matchups,
            seed=args.seed,
        )
        print("\n[ok] Execução concluída")
        print(f"run_id: {result['run_id']}")
        print(f"arquivo: {result['run_path']}")
        return

    if args.decklab_cmd == "report":
        result = report_variant_run(
            variant_id=args.variant_id,
            run_id=args.run_id,
            data=data,
            card_pool=card_pool,
        )
        print("\n[ok] Relatório gerado")
        print(f"summary: {result['summary_path']}")
        print(f"impact_cards: {result['impact_cards_path']}")
        print(f"matchups: {result['matchups_path']}")
        return

    if args.decklab_cmd == "auto-all":
        result = auto_create_and_benchmark_all_variants(
            data=data,
            card_pool=card_pool,
            tags_db=tags_db,
            games=args.games,
            vs_hero=args.vs,
            all_matchups=args.all_matchups,
            seed=args.seed,
        )
        print("\n[ok] Auto-all concluido")
        print(f"summary: {result['aggregate_summary_path']}")
        print(f"csv: {result['aggregate_csv_path']}")
        print(f"dir: {result['aggregate_dir']}")
        return

    raise ValueError("Subcomando deck-lab inválido.")


# ── Parser ────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hemsfell",
        description="Hemsfell Heroes — Simulador & Ferramentas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="<comando>")

    # sim
    p_sim = sub.add_parser("sim", help="Simula partidas entre dois heróis")
    p_sim.add_argument("--deck1",        default="hero_gimble")
    p_sim.add_argument("--deck2",        default="hero_sr_goblin")
    p_sim.add_argument("--games",        type=int, default=1)
    p_sim.add_argument("--all-matchups", action="store_true",
                       help="Simula todos os confrontos")
    p_sim.add_argument("--verbose",      action="store_true",
                       help="Log detalhado (1 partida)")
    p_sim.add_argument("--rl-policy",    default=None,
                       help="Caminho para política RL (.json) para guiar a IA")

    # rl-train
    p_rl = sub.add_parser("rl-train", help="Treina política de RL em várias partidas")
    p_rl.add_argument("--episodes", type=int, default=1000)
    p_rl.add_argument("--deck1", default=None)
    p_rl.add_argument("--deck2", default=None)
    p_rl.add_argument("--all-matchups", action="store_true",
                      help="Alterna os confrontos durante o treino")
    p_rl.add_argument("--policy-path", default="reports/rl_policy.json")
    p_rl.add_argument("--epsilon-start", type=float, default=0.25)
    p_rl.add_argument("--epsilon-end", type=float, default=0.02)
    p_rl.add_argument("--alpha", type=float, default=0.03)
    p_rl.add_argument("--seed", type=int, default=None)
    p_rl.add_argument("--eval-every", type=int, default=0,
                      help="Executa avaliação curta a cada N episódios")
    p_rl.add_argument("--curriculum", choices=["light", "off"], default="light")
    p_rl.add_argument("--save-best", action="store_true",
                      help="Salva checkpoint promovido por critério de WR")

    # rl-eval
    p_rle = sub.add_parser("rl-eval", help="Avalia base vs política RL treinada")
    p_rle.add_argument("--games", type=int, default=100)
    p_rle.add_argument("--deck1", default=None)
    p_rle.add_argument("--deck2", default=None)
    p_rle.add_argument("--all-matchups", action="store_true")
    p_rle.add_argument("--policy-path", default="reports/rl_policy.json")
    p_rle.add_argument("--output", default="reports/rl_eval.txt")
    p_rle.add_argument("--seeds", default=None,
                       help="Lista separada por vírgula, ex: 11,29,47")
    p_rle.add_argument("--critical-matchups", default=None,
                       help="Lista hero1:hero2 separada por vírgula ou caminho de arquivo")
    p_rle.add_argument("--with-ci", action="store_true")

    # deck-metrics
    p_dm = sub.add_parser("deck-metrics", help="Gera métricas estratégicas por deck")
    p_dm.add_argument("--games", type=int, default=50)
    p_dm.add_argument("--output", default="reports/deck_metrics.txt")

    # matrix
    p_mat = sub.add_parser("matrix", help="Tabela de matchups todos-vs-todos")
    p_mat.add_argument("--games", type=int, default=50)

    # inspect
    p_ins = sub.add_parser("inspect", help="Inspeciona o deck de um herói")
    p_ins.add_argument("--deck", default="hero_gimble")

    # heroes
    sub.add_parser("heroes", help="Lista todos os heróis disponíveis")

    # deck-lab
    p_dlab = sub.add_parser("deck-lab", help="Ferramenta de tuning e benchmark de variantes de deck")
    dsub = p_dlab.add_subparsers(dest="decklab_cmd", metavar="<acao>")

    p_dcreate = dsub.add_parser("create", help="Cria variante baseada no deck de um herói")
    p_dcreate.add_argument("--hero", required=True)
    p_dcreate.add_argument("--variant-id", required=True)
    p_dcreate.add_argument("--name", required=True)

    p_dedit = dsub.add_parser("edit", help="Edita uma variante existente")
    p_dedit.add_argument("--variant-id", required=True)
    p_dedit.add_argument("--add", action="append", default=[],
                         help="Formato: card_id ou card_id:qtd (flag repetível)")
    p_dedit.add_argument("--remove", action="append", default=[],
                         help="Formato: card_id ou card_id:qtd (flag repetível)")

    p_drun = dsub.add_parser("run", help="Executa benchmark baseline vs variante")
    p_drun.add_argument("--variant-id", required=True)
    p_drun.add_argument("--vs", default=None, help="Herói adversário")
    p_drun.add_argument("--all-matchups", action="store_true")
    p_drun.add_argument("--games", type=int, default=50)
    p_drun.add_argument("--seed", type=int, default=None)

    p_dreport = dsub.add_parser("report", help="Gera relatórios consolidados de um run")
    p_dreport.add_argument("--variant-id", required=True)
    p_dreport.add_argument("--run-id", required=True)

    p_dauto = dsub.add_parser("auto-all", help="Cria variantes para todos os herois, testa e consolida relatorios")
    p_dauto.add_argument("--games", type=int, default=10)
    p_dauto.add_argument("--vs", default=None, help="Heroi adversario unico (opcional com --all-matchups)")
    p_dauto.add_argument("--all-matchups", action="store_true")
    p_dauto.add_argument("--seed", type=int, default=None)

    return parser


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    dispatch = {
        "sim":          cmd_sim,
        "rl-train":     cmd_rl_train,
        "rl-eval":      cmd_rl_eval,
        "deck-metrics": cmd_deck_metrics,
        "matrix":       cmd_matrix,
        "inspect":      cmd_inspect,
        "heroes":       cmd_heroes,
        "deck-lab":     cmd_deck_lab,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
