"""
Testes de sanidade para rl-eval.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.loader import load_data, build_card_pool, load_tags
from engine.rl_agent import DQNPolicy
from tools.rl_eval import evaluate_policy


def test_rl_eval_smoke():
    data = load_data()
    card_pool = build_card_pool(data)
    tags_db = load_tags()

    reports = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(reports, exist_ok=True)
    policy_path = os.path.join(reports, "rl_eval_test_policy.json")
    out_path = os.path.join(reports, "rl_eval_test_report.txt")

    DQNPolicy(25).save(policy_path)
    report = evaluate_policy(
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        policy_path=policy_path,
        games=2,
        deck1="hero_gimble",
        deck2="hero_tifon",
        all_matchups=False,
        output_path=out_path,
    )
    assert "RL EVAL" in report
    assert "hero_gimble vs hero_tifon" in report
    assert os.path.exists(out_path)


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
