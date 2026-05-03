"""
Sanidade de métricas estratégicas por deck.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.loader import load_data, build_card_pool, load_tags
from engine.deck_strategy import analyze_deck_strategy
from tools.deck_metrics import build_deck_metrics_report


def test_deck_strategy_classification_smoke():
    data = load_data()
    card_pool = build_card_pool(data)
    tags = load_tags()
    s = analyze_deck_strategy("hero_gimble", data, card_pool, tags)
    assert s.style in {
        "control_spells", "combo_engine", "aggro_swarm",
        "midrange_big", "ramp_level", "midrange"
    }


def test_deck_metrics_report_smoke():
    data = load_data()
    card_pool = build_card_pool(data)
    tags = load_tags()
    report = build_deck_metrics_report(
        games=2,
        data=data,
        card_pool=card_pool,
        tags_db=tags,
        output_path=None,
        hero_subset=["hero_gimble", "hero_tifon"],
    )
    assert "DECK METRICS REPORT" in report
    assert "hero_gimble" in report
    assert "hero_tifon" in report


if __name__ == "__main__":
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_")]
    ok = fail = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅  {name}")
            ok += 1
        except Exception as e:
            print(f"  ❌  {name}: {e}")
            fail += 1
    print(f"\n{ok} passou, {fail} falhou.")

