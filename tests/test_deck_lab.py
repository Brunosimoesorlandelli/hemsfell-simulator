"""
Testes do Deck Lab: variantes, run/report e impacto por carta.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.loader import build_card_pool, load_data, load_tags
from tools.deck_lab import (
    RUNS_DIR,
    auto_create_and_benchmark_all_variants,
    _impact_rows,
    create_variant,
    edit_variant,
    report_variant_run,
    run_variant,
)


def _unique_variant_id(prefix: str = "test_variant") -> str:
    return f"{prefix}_{int(time.time() * 1000)}"


def _pick_replacement_card_id(base_cards: list[str], card_pool: dict) -> str:
    base_set = set(base_cards)
    for cid in card_pool.keys():
        if cid not in base_set and cid.startswith("hero_") is False:
            return cid
    raise RuntimeError("Nao foi possivel encontrar carta de reposicao para teste.")


def test_variant_create_and_edit_validation():
    data = load_data()
    card_pool = build_card_pool(data)
    variant_id = _unique_variant_id("variant_unit")

    created = create_variant(
        variant_id=variant_id,
        hero_id="hero_gimble",
        name="Unit Variant",
        data=data,
        card_pool=card_pool,
    )
    assert created["variant_id"] == variant_id
    assert created["base_hero_id"] == "hero_gimble"

    original_cards = list(created["cards"])
    remove_id = original_cards[0]
    add_id = _pick_replacement_card_id(original_cards, card_pool)

    edited = edit_variant(
        variant_id=variant_id,
        add_specs=[f"{add_id}:1"],
        remove_specs=[f"{remove_id}:1"],
        data=data,
        card_pool=card_pool,
    )
    assert len(edited["cards"]) == len(original_cards)
    assert add_id in edited["cards"]

    try:
        edit_variant(
            variant_id=variant_id,
            add_specs=[],
            remove_specs=[f"{remove_id}:999"],
            data=data,
            card_pool=card_pool,
        )
        assert False, "Era esperado erro ao remover mais cartas do que existem."
    except ValueError:
        pass


def test_deck_lab_run_and_report_smoke():
    data = load_data()
    card_pool = build_card_pool(data)
    tags_db = load_tags()
    variant_id = _unique_variant_id("variant_integration")

    created = create_variant(
        variant_id=variant_id,
        hero_id="hero_gimble",
        name="Integration Variant",
        data=data,
        card_pool=card_pool,
    )
    remove_id = created["cards"][0]
    add_id = _pick_replacement_card_id(created["cards"], card_pool)
    edit_variant(
        variant_id=variant_id,
        add_specs=[add_id],
        remove_specs=[remove_id],
        data=data,
        card_pool=card_pool,
    )

    run = run_variant(
        variant_id=variant_id,
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        games=1,
        vs_hero="hero_tifon",
        all_matchups=False,
        seed=123,
    )
    run_file = os.path.join(RUNS_DIR, f"{run['run_id']}.jsonl")
    assert os.path.exists(run_file)

    report = report_variant_run(
        variant_id=variant_id,
        run_id=run["run_id"],
        data=data,
        card_pool=card_pool,
    )
    assert os.path.exists(report["summary_path"])
    assert os.path.exists(report["impact_cards_path"])
    assert os.path.exists(report["matchups_path"])


def test_impact_rows_edge_cases():
    data = load_data()
    card_pool = build_card_pool(data)
    variant_cards = list(next(d for d in data["decks"] if d["hero_id"] == "hero_gimble")["cards"])
    card_id = variant_cards[0]
    card_name = card_pool[card_id]["name"]

    variant_entries = [
        {
            "result": {
                "winner": "J1",
                "p1_name": "J1",
                "p1_cards_drawn": {card_name: 1},
                "p1_cards": {card_name: 1},
            }
        },
        {
            "result": {
                "winner": "J2",
                "p1_name": "J1",
                "p1_cards_drawn": {},
                "p1_cards": {},
            }
        },
    ]

    rows = _impact_rows(variant_entries, [card_id], card_pool)
    assert len(rows) == 1
    row = rows[0]
    assert row["card_id"] == card_id
    assert row["sample_drawn"] == 1
    assert row["sample_played"] == 1
    assert row["confidence_band"] == "low"


def test_auto_all_variants_smoke():
    data = load_data()
    card_pool = build_card_pool(data)
    tags_db = load_tags()
    result = auto_create_and_benchmark_all_variants(
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        games=1,
        vs_hero="hero_tifon",
        all_matchups=False,
        seed=77,
        hero_subset=["hero_gimble", "hero_tifon"],
    )
    assert os.path.exists(result["aggregate_summary_path"])
    assert os.path.exists(result["aggregate_csv_path"])
    assert len(result["rows"]) == 2


if __name__ == "__main__":
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_")]
    ok = fail = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [ok]  {name}")
            ok += 1
        except Exception as e:
            print(f"  [fail]  {name}: {e}")
            fail += 1
    print(f"\n{ok} passou, {fail} falhou.")
