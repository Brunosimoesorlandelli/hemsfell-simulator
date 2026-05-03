"""
Testes de sanidade para módulo de RL.
"""

import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.loader import load_data, build_card_pool, load_tags, build_deck_for_hero
from engine.models import Player, reset_iid
from engine.rl_agent import DQNPolicy, RLEpisodeRuntime
from engine.simulator import GameState
from engine import logger


def test_policy_save_load():
    pol = DQNPolicy(2)
    feats = {"bias": 1.0, "x": 0.5}
    pol.update("main:hero_x", "creature", feats, reward=2.0)
    reports = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(reports, exist_ok=True)
    path = os.path.join(reports, "rl_test_policy.json")
    pol.save(path)
    loaded = DQNPolicy.load(path, 2)
    s1 = pol.score("main:hero_x", "creature", feats)
    s2 = loaded.score("main:hero_x", "creature", feats)
    assert abs(s1 - s2) < 1e-9


def test_runtime_attached_game_runs():
    random.seed(9)
    reset_iid()
    logger.clear()

    data = load_data()
    card_pool = build_card_pool(data)
    tags = load_tags()
    h1, d1 = build_deck_for_hero("hero_gimble", data, card_pool, tags)
    h2, d2 = build_deck_for_hero("hero_tifon", data, card_pool, tags)
    p1 = Player(name="J1", hero=h1, deck=d1)
    p2 = Player(name="J2", hero=h2, deck=d2)

    gs = GameState(p1, p2, card_pool, tags)
    gs.rl_runtime = RLEpisodeRuntime(policy=DQNPolicy(25), training=True, epsilon=0.2, alpha=0.02)
    r = gs.run()
    assert r["turns"] >= 1
    assert r["winner"] in (r["p1_name"], r["p2_name"], "Empate")


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
