"""
Deck Lab: variantes de deck, benchmark e relatorios de impacto por carta.
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
from collections import Counter

from engine import logger
from engine.config import REPORTS_DIR
from engine.loader import build_deck_for_hero, make_card
from engine.models import Player, reset_iid
from engine.simulator import GameState

DECKLAB_DIR = os.path.join(REPORTS_DIR, "decklab")
VARIANTS_DIR = os.path.join(DECKLAB_DIR, "variants")
RUNS_DIR = os.path.join(DECKLAB_DIR, "runs")
REPORTS_DECKLAB_DIR = os.path.join(DECKLAB_DIR, "reports")


def _ensure_dirs():
    os.makedirs(VARIANTS_DIR, exist_ok=True)
    os.makedirs(RUNS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DECKLAB_DIR, exist_ok=True)


def _deck_entry_for_hero(hero_id: str, data: dict) -> dict:
    entry = next((d for d in data.get("decks", []) if d.get("hero_id") == hero_id), None)
    if entry is None:
        raise ValueError(f"Deck nao encontrado para hero_id='{hero_id}'.")
    return entry


def _hero_ids_with_decks(data: dict) -> list[str]:
    hero_ids = {h.get("id") for h in data.get("heroes", [])}
    deck_hero_ids = []
    for d in data.get("decks", []):
        hid = d.get("hero_id")
        if hid in hero_ids:
            deck_hero_ids.append(hid)
    return deck_hero_ids


def _hero_exists(hero_id: str, data: dict) -> bool:
    return any(h.get("id") == hero_id for h in data.get("heroes", []))


def _variant_path(variant_id: str) -> str:
    return os.path.join(VARIANTS_DIR, f"{variant_id}.json")


def _parse_card_specs(specs: list[str]) -> Counter:
    out = Counter()
    for raw in specs:
        raw = raw.strip()
        if not raw:
            continue
        if ":" in raw:
            card_id, qty_str = raw.split(":", 1)
            qty = int(qty_str)
        else:
            card_id, qty = raw, 1
        card_id = card_id.strip()
        if not card_id:
            raise ValueError("card_id vazio em --add/--remove.")
        if qty <= 0:
            raise ValueError(f"Quantidade invalida para '{raw}'. Use inteiro > 0.")
        out[card_id] += qty
    return out


def _validate_variant_data(variant: dict, data: dict, card_pool: dict):
    variant_id = variant.get("variant_id")
    hero_id = variant.get("base_hero_id")
    cards = variant.get("cards", [])
    if not variant_id:
        raise ValueError("variant_id ausente na variante.")
    if not hero_id:
        raise ValueError("base_hero_id ausente na variante.")
    if not _hero_exists(hero_id, data):
        raise ValueError(f"Heroi base '{hero_id}' nao existe.")
    if not isinstance(cards, list):
        raise ValueError("Campo 'cards' deve ser lista de card IDs.")

    missing = [cid for cid in cards if cid not in card_pool]
    if missing:
        raise ValueError(f"Variante contem card IDs invalidos: {missing[:5]}")

    base_deck = _deck_entry_for_hero(hero_id, data)
    if len(cards) != len(base_deck.get("cards", [])):
        raise ValueError(
            f"Deck final da variante deve manter tamanho {len(base_deck.get('cards', []))}. "
            f"Recebido: {len(cards)}"
        )


def load_variant(variant_id: str, data: dict, card_pool: dict) -> dict:
    path = _variant_path(variant_id)
    if not os.path.exists(path):
        raise ValueError(f"Variante '{variant_id}' nao encontrada em: {path}")
    with open(path, "r", encoding="utf-8") as f:
        variant = json.load(f)
    _validate_variant_data(variant, data, card_pool)
    return variant


def create_variant(variant_id: str, hero_id: str, name: str, data: dict, card_pool: dict) -> dict:
    _ensure_dirs()
    if not _hero_exists(hero_id, data):
        raise ValueError(f"Heroi '{hero_id}' nao encontrado.")

    path = _variant_path(variant_id)
    if os.path.exists(path):
        raise ValueError(f"Ja existe variante com id '{variant_id}'.")

    base = _deck_entry_for_hero(hero_id, data)
    variant = {
        "variant_id": variant_id,
        "base_hero_id": hero_id,
        "name": name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cards": list(base.get("cards", [])),
        "changes": {"adds": [], "removes": []},
    }
    _validate_variant_data(variant, data, card_pool)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(variant, f, ensure_ascii=False, indent=2)
    return variant


def edit_variant(
    variant_id: str,
    add_specs: list[str],
    remove_specs: list[str],
    data: dict,
    card_pool: dict,
) -> dict:
    _ensure_dirs()
    variant = load_variant(variant_id, data, card_pool)

    adds = _parse_card_specs(add_specs)
    removes = _parse_card_specs(remove_specs)
    if not adds and not removes:
        raise ValueError("Nenhuma alteracao informada. Use --add e/ou --remove.")

    cards_counter = Counter(variant["cards"])
    for card_id, qty in removes.items():
        if cards_counter[card_id] < qty:
            raise ValueError(
                f"Nao ha copias suficientes para remover '{card_id}:{qty}'. "
                f"Disponivel: {cards_counter[card_id]}"
            )
        cards_counter[card_id] -= qty

    for card_id, qty in adds.items():
        if card_id not in card_pool:
            raise ValueError(f"Card ID invalido em --add: '{card_id}'")
        cards_counter[card_id] += qty

    new_cards = []
    for cid, qty in cards_counter.items():
        if qty < 0:
            raise ValueError(f"Contagem negativa detectada para '{cid}'.")
        new_cards.extend([cid] * qty)

    variant["cards"] = new_cards
    variant["changes"]["adds"].extend(
        [f"{cid}:{qty}" for cid, qty in sorted(adds.items())]
    )
    variant["changes"]["removes"].extend(
        [f"{cid}:{qty}" for cid, qty in sorted(removes.items())]
    )
    _validate_variant_data(variant, data, card_pool)

    path = _variant_path(variant_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(variant, f, ensure_ascii=False, indent=2)
    return variant


def _build_deck_from_ids(card_ids: list[str], card_pool: dict, tags_db: dict) -> list:
    deck = [make_card(card_pool[cid], tags_db) for cid in card_ids]
    random.shuffle(deck)
    return deck


def _play_game(
    p1_hero_id: str,
    p2_hero_id: str,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    p1_cards_override: list[str] | None = None,
    seed: int | None = None,
) -> dict:
    if seed is not None:
        random.seed(seed)
    reset_iid()
    logger.clear()
    logger.set_verbose(False)

    names = {h["id"]: h["name"] for h in data.get("heroes", [])}
    p1_name = f"J1 ({names.get(p1_hero_id, p1_hero_id)})"
    p2_name = f"J2 ({names.get(p2_hero_id, p2_hero_id)})"

    if p1_cards_override is None:
        hero1, deck1 = build_deck_for_hero(p1_hero_id, data, card_pool, tags_db)
    else:
        hero1 = make_card(card_pool[p1_hero_id], tags_db)
        deck1 = _build_deck_from_ids(p1_cards_override, card_pool, tags_db)
    hero2, deck2 = build_deck_for_hero(p2_hero_id, data, card_pool, tags_db)

    p1 = Player(name=p1_name, hero=hero1, deck=deck1)
    p2 = Player(name=p2_name, hero=hero2, deck=deck2)
    gs = GameState(p1, p2, card_pool, tags_db)
    return gs.run()


def _matchups_for_run(base_hero_id: str, vs_hero: str | None, all_matchups: bool, data: dict) -> list[str]:
    hero_ids = _hero_ids_with_decks(data)
    if all_matchups:
        return [hid for hid in hero_ids if hid != base_hero_id]
    if vs_hero:
        if vs_hero not in hero_ids:
            raise ValueError(f"Heroi adversario '{vs_hero}' nao encontrado.")
        if vs_hero == base_hero_id:
            raise ValueError("Use um adversario diferente do heroi base.")
        return [vs_hero]
    raise ValueError("Informe --vs <hero_id> ou --all-matchups.")


def run_variant(
    variant_id: str,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    games: int,
    vs_hero: str | None = None,
    all_matchups: bool = False,
    seed: int | None = None,
) -> dict:
    _ensure_dirs()
    if games <= 0:
        raise ValueError("--games deve ser > 0.")

    variant = load_variant(variant_id, data, card_pool)
    base_hero_id = variant["base_hero_id"]
    opponents = _matchups_for_run(base_hero_id, vs_hero, all_matchups, data)
    run_id = f"{variant_id}_{time.strftime('%Y%m%d_%H%M%S')}"
    run_path = os.path.join(RUNS_DIR, f"{run_id}.jsonl")

    total_pairs = len(opponents) * games
    done = 0
    with open(run_path, "w", encoding="utf-8") as f:
        for opp in opponents:
            for game_index in range(games):
                done += 1
                game_seed = None if seed is None else seed + done * 17
                print(f"[deck-lab] {done}/{total_pairs} {base_hero_id} vs {opp} (seed={game_seed})")

                res_base = _play_game(
                    p1_hero_id=base_hero_id,
                    p2_hero_id=opp,
                    data=data,
                    card_pool=card_pool,
                    tags_db=tags_db,
                    p1_cards_override=None,
                    seed=game_seed,
                )
                line_base = {
                    "run_id": run_id,
                    "variant_id": variant_id,
                    "base_hero_id": base_hero_id,
                    "opponent_hero_id": opp,
                    "arm": "baseline",
                    "game_index": game_index,
                    "seed": game_seed,
                    "result": res_base,
                }
                f.write(json.dumps(line_base, ensure_ascii=False) + "\n")

                res_variant = _play_game(
                    p1_hero_id=base_hero_id,
                    p2_hero_id=opp,
                    data=data,
                    card_pool=card_pool,
                    tags_db=tags_db,
                    p1_cards_override=variant["cards"],
                    seed=game_seed,
                )
                line_variant = {
                    "run_id": run_id,
                    "variant_id": variant_id,
                    "base_hero_id": base_hero_id,
                    "opponent_hero_id": opp,
                    "arm": "variant",
                    "game_index": game_index,
                    "seed": game_seed,
                    "result": res_variant,
                }
                f.write(json.dumps(line_variant, ensure_ascii=False) + "\n")

    return {
        "run_id": run_id,
        "run_path": run_path,
        "variant_id": variant_id,
        "base_hero_id": base_hero_id,
        "opponents": opponents,
        "games_per_matchup": games,
    }


def _load_run_lines(run_id: str, variant_id: str) -> list[dict]:
    run_path = os.path.join(RUNS_DIR, f"{run_id}.jsonl")
    if not os.path.exists(run_path):
        raise ValueError(f"Run '{run_id}' nao encontrado em {run_path}.")
    lines = []
    with open(run_path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            line = json.loads(raw)
            if line.get("variant_id") == variant_id:
                lines.append(line)
    if not lines:
        raise ValueError(f"Nenhum registro para variante '{variant_id}' no run '{run_id}'.")
    return lines


def _wr(entries: list[dict]) -> float:
    if not entries:
        return 0.0
    wins = 0
    for e in entries:
        r = e["result"]
        if r["winner"] == r["p1_name"]:
            wins += 1
    return wins / len(entries)


def _avg_turns(entries: list[dict]) -> float:
    if not entries:
        return 0.0
    return sum(e["result"]["turns"] for e in entries) / len(entries)


def _confidence_band(sample: int) -> str:
    if sample >= 100:
        return "high"
    if sample >= 30:
        return "medium"
    return "low"


def _impact_rows(variant_entries: list[dict], variant_cards: list[str], card_pool: dict) -> list[dict]:
    total_games = len(variant_entries)
    if total_games == 0:
        return []

    total_wins = sum(1 for e in variant_entries if e["result"]["winner"] == e["result"]["p1_name"])
    base_wr = total_wins / total_games

    unique_variant_ids = list(dict.fromkeys(variant_cards))
    id_to_name = {cid: card_pool[cid]["name"] for cid in unique_variant_ids}
    name_to_id = {}
    for cid in unique_variant_ids:
        name_to_id.setdefault(id_to_name[cid], cid)

    rows = []
    for card_id in unique_variant_ids:
        card_name = id_to_name[card_id]
        drawn_games = 0
        wins_when_drawn = 0
        played_games = 0
        wins_when_played = 0

        for e in variant_entries:
            r = e["result"]
            won = r["winner"] == r["p1_name"]
            drawn_map = r.get("p1_cards_drawn", {})
            played_map = r.get("p1_cards", {})
            drawn = drawn_map.get(card_name, 0) > 0
            played = played_map.get(card_name, 0) > 0
            if drawn:
                drawn_games += 1
                if won:
                    wins_when_drawn += 1
            if played:
                played_games += 1
                if won:
                    wins_when_played += 1

        not_drawn_games = total_games - drawn_games
        wins_not_drawn = total_wins - wins_when_drawn

        wr_when_drawn = (wins_when_drawn / drawn_games) if drawn_games else 0.0
        wr_when_not_drawn = (wins_not_drawn / not_drawn_games) if not_drawn_games else 0.0
        drawn_win_lift = wr_when_drawn - wr_when_not_drawn
        wr_when_played = (wins_when_played / played_games) if played_games else 0.0
        played_win_lift = wr_when_played - base_wr
        impact_score = 0.6 * played_win_lift + 0.4 * drawn_win_lift

        draw_rate = drawn_games / total_games
        play_rate_when_drawn = (played_games / drawn_games) if drawn_games else 0.0
        confidence_sample = min(drawn_games, played_games)

        rows.append(
            {
                "card_id": name_to_id.get(card_name, card_id),
                "card_name": card_name,
                "draw_rate": draw_rate,
                "play_rate_when_drawn": play_rate_when_drawn,
                "wr_when_drawn": wr_when_drawn,
                "wr_when_played": wr_when_played,
                "drawn_win_lift": drawn_win_lift,
                "played_win_lift": played_win_lift,
                "impact_score": impact_score,
                "sample_drawn": drawn_games,
                "sample_played": played_games,
                "confidence_band": _confidence_band(confidence_sample),
                "_base_wr": base_wr,
            }
        )
    rows.sort(key=lambda x: x["impact_score"], reverse=True)
    return rows


def report_variant_run(variant_id: str, run_id: str, data: dict, card_pool: dict) -> dict:
    _ensure_dirs()
    variant = load_variant(variant_id, data, card_pool)
    lines = _load_run_lines(run_id, variant_id)

    grouped: dict[tuple[str, str], list[dict]] = {}
    for line in lines:
        key = (line["opponent_hero_id"], line["arm"])
        grouped.setdefault(key, []).append(line)

    opponents = sorted({line["opponent_hero_id"] for line in lines})
    matchup_rows = []
    all_baseline = []
    all_variant = []
    for opp in opponents:
        baseline_entries = grouped.get((opp, "baseline"), [])
        variant_entries = grouped.get((opp, "variant"), [])
        all_baseline.extend(baseline_entries)
        all_variant.extend(variant_entries)

        b_wr = _wr(baseline_entries)
        v_wr = _wr(variant_entries)
        b_turns = _avg_turns(baseline_entries)
        v_turns = _avg_turns(variant_entries)
        matchup_rows.append(
            {
                "opponent_hero_id": opp,
                "baseline_wr": b_wr,
                "variant_wr": v_wr,
                "delta_wr_pp": (v_wr - b_wr) * 100.0,
                "baseline_avg_turns": b_turns,
                "variant_avg_turns": v_turns,
                "delta_turns": v_turns - b_turns,
            }
        )

    impact_rows = _impact_rows(all_variant, variant["cards"], card_pool)
    top_pos = impact_rows[:5]
    top_neg = list(reversed(impact_rows[-5:])) if impact_rows else []

    report_dir = os.path.join(REPORTS_DECKLAB_DIR, run_id)
    os.makedirs(report_dir, exist_ok=True)
    summary_path = os.path.join(report_dir, "summary.txt")
    impact_path = os.path.join(report_dir, "impact_cards.csv")
    matchups_path = os.path.join(report_dir, "matchups.csv")

    with open(matchups_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "opponent_hero_id",
                "baseline_wr",
                "variant_wr",
                "delta_wr_pp",
                "baseline_avg_turns",
                "variant_avg_turns",
                "delta_turns",
            ],
        )
        writer.writeheader()
        for row in matchup_rows:
            writer.writerow(row)

    with open(impact_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "card_id",
                "card_name",
                "draw_rate",
                "play_rate_when_drawn",
                "wr_when_drawn",
                "wr_when_played",
                "drawn_win_lift",
                "played_win_lift",
                "impact_score",
                "sample_drawn",
                "sample_played",
                "confidence_band",
            ],
        )
        writer.writeheader()
        for row in impact_rows:
            payload = {k: row[k] for k in writer.fieldnames}
            writer.writerow(payload)

    overall_base_wr = _wr(all_baseline)
    overall_variant_wr = _wr(all_variant)
    overall_delta_pp = (overall_variant_wr - overall_base_wr) * 100.0
    overall_base_turns = _avg_turns(all_baseline)
    overall_variant_turns = _avg_turns(all_variant)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("DECK LAB SUMMARY\n")
        f.write("=" * 72 + "\n")
        f.write(f"variant_id: {variant_id}\n")
        f.write(f"run_id: {run_id}\n")
        f.write(f"base_hero_id: {variant['base_hero_id']}\n")
        f.write(f"games_total_baseline: {len(all_baseline)}\n")
        f.write(f"games_total_variant: {len(all_variant)}\n")
        f.write(f"baseline_wr: {overall_base_wr * 100.0:.2f}%\n")
        f.write(f"variant_wr: {overall_variant_wr * 100.0:.2f}%\n")
        f.write(f"delta_wr_pp: {overall_delta_pp:+.2f}\n")
        f.write(f"baseline_avg_turns: {overall_base_turns:.2f}\n")
        f.write(f"variant_avg_turns: {overall_variant_turns:.2f}\n")
        f.write(f"delta_turns: {overall_variant_turns - overall_base_turns:+.2f}\n")
        f.write("\nTop impacto positivo:\n")
        for row in top_pos:
            f.write(
                f"  {row['card_name']}: impact={row['impact_score']:+.4f} "
                f"(played_lift={row['played_win_lift']:+.4f}, drawn_lift={row['drawn_win_lift']:+.4f})\n"
            )
        f.write("\nTop impacto negativo:\n")
        for row in top_neg:
            f.write(
                f"  {row['card_name']}: impact={row['impact_score']:+.4f} "
                f"(played_lift={row['played_win_lift']:+.4f}, drawn_lift={row['drawn_win_lift']:+.4f})\n"
            )

    return {
        "summary_path": summary_path,
        "impact_cards_path": impact_path,
        "matchups_path": matchups_path,
        "report_dir": report_dir,
        "baseline_wr": overall_base_wr,
        "variant_wr": overall_variant_wr,
        "delta_wr_pp": overall_delta_pp,
        "baseline_avg_turns": overall_base_turns,
        "variant_avg_turns": overall_variant_turns,
        "delta_turns": overall_variant_turns - overall_base_turns,
    }


def _pick_replacement_card_id(base_cards: list[str], card_pool: dict) -> str:
    base_set = set(base_cards)
    for cid, raw in card_pool.items():
        ctype = raw.get("type", "")
        if cid in base_set:
            continue
        if ctype == "hero":
            continue
        return cid
    raise ValueError("Nao foi possivel encontrar carta de reposicao para variante automatica.")


def _resolve_vs_for_hero(hero_id: str, requested_vs: str | None, data: dict) -> str:
    hero_ids = _hero_ids_with_decks(data)
    if requested_vs and requested_vs != hero_id:
        return requested_vs
    for hid in hero_ids:
        if hid != hero_id:
            return hid
    raise ValueError("Nao ha herois suficientes para selecionar adversario.")


def auto_create_and_benchmark_all_variants(
    data: dict,
    card_pool: dict,
    tags_db: dict,
    games: int,
    vs_hero: str | None = None,
    all_matchups: bool = False,
    seed: int | None = None,
    hero_subset: list[str] | None = None,
) -> dict:
    _ensure_dirs()
    hero_ids = hero_subset if hero_subset else _hero_ids_with_decks(data)
    if not hero_ids:
        raise ValueError("Nenhum heroi com deck encontrado para auto-all.")
    if games <= 0:
        raise ValueError("--games deve ser > 0.")
    if (not all_matchups) and (vs_hero is None):
        raise ValueError("No auto-all, informe --vs ou use --all-matchups.")

    run_tag = f"{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"
    aggregate_dir = os.path.join(REPORTS_DECKLAB_DIR, f"auto_{run_tag}")
    os.makedirs(aggregate_dir, exist_ok=True)
    aggregate_csv = os.path.join(aggregate_dir, "heroes_report.csv")
    aggregate_summary = os.path.join(aggregate_dir, "summary.txt")

    rows = []
    for idx, hero_id in enumerate(hero_ids):
        print(f"[deck-lab auto-all] {idx+1}/{len(hero_ids)} hero={hero_id}")
        variant_id = f"auto_{hero_id}_{run_tag}_{idx}"
        variant = create_variant(
            variant_id=variant_id,
            hero_id=hero_id,
            name=f"Auto Variant {hero_id}",
            data=data,
            card_pool=card_pool,
        )
        remove_id = variant["cards"][0]
        add_id = _pick_replacement_card_id(variant["cards"], card_pool)
        edit_variant(
            variant_id=variant_id,
            add_specs=[add_id],
            remove_specs=[remove_id],
            data=data,
            card_pool=card_pool,
        )

        hero_seed = None if seed is None else seed + idx * 1000
        resolved_vs = None
        if not all_matchups:
            resolved_vs = _resolve_vs_for_hero(hero_id, vs_hero, data)
        run = run_variant(
            variant_id=variant_id,
            data=data,
            card_pool=card_pool,
            tags_db=tags_db,
            games=games,
            vs_hero=resolved_vs,
            all_matchups=all_matchups,
            seed=hero_seed,
        )
        report = report_variant_run(
            variant_id=variant_id,
            run_id=run["run_id"],
            data=data,
            card_pool=card_pool,
        )
        rows.append(
            {
                "hero_id": hero_id,
                "variant_id": variant_id,
                "run_id": run["run_id"],
                "baseline_wr": report["baseline_wr"],
                "variant_wr": report["variant_wr"],
                "delta_wr_pp": report["delta_wr_pp"],
                "baseline_avg_turns": report["baseline_avg_turns"],
                "variant_avg_turns": report["variant_avg_turns"],
                "delta_turns": report["delta_turns"],
                "summary_path": report["summary_path"],
                "impact_cards_path": report["impact_cards_path"],
                "matchups_path": report["matchups_path"],
            }
        )

    with open(aggregate_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "hero_id",
                "variant_id",
                "run_id",
                "baseline_wr",
                "variant_wr",
                "delta_wr_pp",
                "baseline_avg_turns",
                "variant_avg_turns",
                "delta_turns",
                "summary_path",
                "impact_cards_path",
                "matchups_path",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    rows_sorted = sorted(rows, key=lambda x: x["delta_wr_pp"], reverse=True)
    with open(aggregate_summary, "w", encoding="utf-8") as f:
        f.write("DECK LAB AUTO-ALL SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"heroes: {len(rows)}\n")
        f.write(f"games_per_matchup: {games}\n")
        f.write(f"all_matchups: {all_matchups}\n")
        f.write(f"vs_hero: {vs_hero}\n")
        f.write("\nRanking por delta WR (pp):\n")
        for i, row in enumerate(rows_sorted, 1):
            f.write(
                f"  {i:>2}. {row['hero_id']:<28} {row['delta_wr_pp']:+7.2f} pp "
                f"(base={row['baseline_wr']*100:.2f}% var={row['variant_wr']*100:.2f}%)\n"
            )

    return {
        "aggregate_dir": aggregate_dir,
        "aggregate_summary_path": aggregate_summary,
        "aggregate_csv_path": aggregate_csv,
        "rows": rows,
    }
