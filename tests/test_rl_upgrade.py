"""
Testes das evolucoes do RL: mascara, reward profile e pipeline.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.loader import build_card_pool, load_data, load_tags
from engine.models import CardInst, Player, reset_iid
from engine.rl_agent import DQNPolicy, RLEpisodeRuntime
from engine.simulator import GameState
from tools.rl_eval import evaluate_policy
from tools.rl_trainer import train_policy


def _hero_card(hero_id: str = "hero_gimble"):
    return CardInst(id=hero_id, name="Hero", card_type="hero", color="Neutro")


def _creature(name: str, cost: int):
    return CardInst(
        id=f"crt_{name}",
        name=name,
        card_type="creature",
        color="Neutro",
        cost=cost,
        offense=2,
        vitality=2,
        base_off=2,
        base_vit=2,
    )


class _DummyRuntime:
    def __init__(self):
        self.actions_seen = []

    def decide_main_action(self, gs, player, opp, actions):
        self.actions_seen = list(actions)
        return "pass"

    def record_invalid_action(self, player, action):
        return


def test_main_action_mask_only_valid_actions():
    reset_iid()
    p1 = Player(name="P1", hero=_hero_card("hero_gimble"), deck=[])
    p2 = Player(name="P2", hero=_hero_card("hero_tifon"), deck=[])
    p1.energy = 0
    p1.max_energy = 0
    p1.reserve = 0
    p1.hand = [_creature("cara", cost=7)]

    gs = GameState(p1, p2, card_pool={}, tags_db={})
    rt = _DummyRuntime()
    gs.rl_runtime = rt
    gs.phase_main(p1)
    assert rt.actions_seen == ["pass"]


def test_reward_profile_v2_differs_from_v1():
    reset_iid()
    p1 = Player(name="P1", hero=_hero_card("hero_gimble"), deck=[])
    p2 = Player(name="P2", hero=_hero_card("hero_tifon"), deck=[])
    gs = GameState(p1, p2, card_pool={}, tags_db={})
    pol = DQNPolicy(25)

    rt_v1 = RLEpisodeRuntime(policy=pol, training=False, reward_profile="v1")
    rt_v1.on_turn_start(gs, p1, p2)
    p2.life -= 5
    rt_v1.on_turn_end(gs, p1, p2)
    r1 = rt_v1.last_reward[id(p1)]

    p1.life = 30
    p2.life = 30
    rt_v2 = RLEpisodeRuntime(policy=pol, training=False, reward_profile="v2_winrate")
    rt_v2.on_turn_start(gs, p1, p2)
    p2.life -= 5
    rt_v2.on_turn_end(gs, p1, p2)
    r2 = rt_v2.last_reward[id(p1)]

    assert r1 != r2
    assert r2 > 0


def test_policy_metadata_save_and_load():
    pol = DQNPolicy(2)
    pol.update("main:hero_x", "play_best_creature", {"bias": 1.0, "x": 0.5}, reward=1.0)
    reports = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(reports, exist_ok=True)
    path = os.path.join(reports, f"rl_meta_test_{int(time.time() * 1000)}.pt")
    pol.save(path, metadata={"training_config": {"reward_profile": "v2_winrate"}}, checkpoint_tag="ep10")
    loaded = DQNPolicy.load(path, 2)
    assert loaded.metadata.get("training_config", {}).get("reward_profile") == "v2_winrate"
    assert loaded.metadata.get("checkpoint_tag") == "ep10"


def test_train_save_best_and_eval_with_seeds_ci():
    data = load_data()
    card_pool = build_card_pool(data)
    tags_db = load_tags()
    reports = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(reports, exist_ok=True)
    policy_path = os.path.join(reports, f"rl_upgrade_policy_{int(time.time() * 1000)}.pt")

    result = train_policy(
        episodes=6,
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        policy_path=policy_path,
        deck1="hero_gimble",
        deck2="hero_tifon",
        all_matchups=False,
        seed=7,
        reward_profile="v2_winrate",
        eval_every=2,
        curriculum="off",
        save_best=True,
    )
    assert os.path.exists(result["policy_path"])
    assert os.path.exists(result["best_policy_path"])

    report = evaluate_policy(
        data=data,
        card_pool=card_pool,
        tags_db=tags_db,
        policy_path=result["best_policy_path"],
        games=1,
        deck1="hero_gimble",
        deck2="hero_tifon",
        all_matchups=False,
        seeds="3,5",
        with_ci=True,
    )
    assert "Seeds: [3, 5]" in report
    assert "CI95" in report


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
