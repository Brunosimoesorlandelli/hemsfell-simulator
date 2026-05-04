"""
Treino de IA com aprendizado por reforco.
"""

from __future__ import annotations

import os
import random
import time
from collections import defaultdict

from engine import logger
from engine.loader import build_deck_for_hero
from engine.models import Player, reset_iid
from engine.rl_agent import MLPPolicy, RLEpisodeRuntime
from engine.simulator import GameState


def _build_pairs(deck_heroes: list[str], deck1: str | None, deck2: str | None, all_matchups: bool) -> list[tuple[str, str]]:
    if deck1 and deck2:
        return [(deck1, deck2)]
    if all_matchups:
        pairs = []
        for i, h1 in enumerate(deck_heroes):
            for h2 in deck_heroes[i + 1:]:
                pairs.append((h1, h2))
        return pairs
    if len(deck_heroes) < 2:
        return [(deck_heroes[0], deck_heroes[0])]
    return [(deck_heroes[0], deck_heroes[1])]


def _pick_pair_for_episode(
    ep: int,
    episodes: int,
    deck_heroes: list[str],
    fixed_pair: tuple[str, str] | None,
    all_pairs: list[tuple[str, str]],
    curriculum: str,
) -> tuple[str, str]:
    if fixed_pair is not None:
        return fixed_pair
    if not all_pairs:
        h1 = random.choice(deck_heroes)
        h2 = random.choice(deck_heroes)
        while h2 == h1 and len(deck_heroes) > 1:
            h2 = random.choice(deck_heroes)
        return (h1, h2)

    if curriculum == "light":
        phase_boundary = int(episodes * 0.6)
        top_k = min(3, len(all_pairs))
        frequent = all_pairs[:top_k]
        if ep < phase_boundary and random.random() < 0.7:
            return frequent[ep % top_k]
        return random.choice(all_pairs)

    return random.choice(all_pairs)


def _run_single_game(
    hero1_id: str,
    hero2_id: str,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    policy: MLPPolicy | None,
    training: bool,
    epsilon: float,
    seed: int | None,
):
    if seed is not None:
        random.seed(seed)
    reset_iid()
    logger.clear()

    hero1, d1 = build_deck_for_hero(hero1_id, data, card_pool, tags_db)
    hero2, d2 = build_deck_for_hero(hero2_id, data, card_pool, tags_db)
    p1 = Player(name=f"J1_{hero1_id}", hero=hero1, deck=d1)
    p2 = Player(name=f"J2_{hero2_id}", hero=hero2, deck=d2)
    gs = GameState(p1, p2, card_pool, tags_db)
    runtime = None
    if policy is not None:
        runtime = RLEpisodeRuntime(
            policy=policy,
            training=training,
            epsilon=epsilon if training else 0.0,
            alpha=0.03,
            # reward_profile removido: v3 unifica o perfil de reward no próprio
            # on_turn_end (board_delta + damage). Não há seleção por string.
        )
        gs.rl_runtime = runtime
    result = gs.run()
    return result, runtime


def _evaluate_policy_snapshot(
    policy: MLPPolicy,
    pairs: list[tuple[str, str]],
    data: dict,
    card_pool: dict,
    tags_db: dict,
    seeds: list[int],
    games_per_seed: int,
) -> dict:
    per_pair = {}
    total_base_wins = 0
    total_rl_wins = 0
    total_games = 0

    for h1, h2 in pairs:
        base_wins = 0
        rl_wins = 0
        pair_games = 0
        for sd in seeds:
            for g in range(games_per_seed):
                game_seed = sd + g * 131
                base_res, _ = _run_single_game(
                    h1, h2, data, card_pool, tags_db,
                    policy=None, training=False, epsilon=0.0,
                    seed=game_seed,
                )
                rl_res, _ = _run_single_game(
                    h1, h2, data, card_pool, tags_db,
                    policy=policy, training=False, epsilon=0.0,
                    seed=game_seed,
                )
                pair_games += 1
                total_games += 1
                if base_res["winner"] == base_res["p1_name"]:
                    base_wins += 1
                    total_base_wins += 1
                if rl_res["winner"] == rl_res["p1_name"]:
                    rl_wins += 1
                    total_rl_wins += 1
        base_wr = (base_wins / pair_games) * 100.0 if pair_games else 0.0
        rl_wr = (rl_wins / pair_games) * 100.0 if pair_games else 0.0
        per_pair[(h1, h2)] = {
            "base_wr": base_wr,
            "rl_wr": rl_wr,
            "delta_pp": rl_wr - base_wr,
        }

    global_base_wr = (total_base_wins / max(1, total_games)) * 100.0
    global_rl_wr = (total_rl_wins / max(1, total_games)) * 100.0
    return {
        "global_base_wr": global_base_wr,
        "global_rl_wr": global_rl_wr,
        "global_delta_pp": global_rl_wr - global_base_wr,
        "per_pair": per_pair,
    }


def _passes_promotion(eval_summary: dict, critical_pairs: list[tuple[str, str]]) -> bool:
    if eval_summary["global_delta_pp"] <= 2.0:
        return False
    per_pair = eval_summary["per_pair"]
    for pair in critical_pairs:
        pair_metrics = per_pair.get(pair)
        if pair_metrics is None:
            continue
        if pair_metrics["delta_pp"] < -3.0:
            return False
    return True


def train_policy(
    episodes: int,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    policy_path: str,
    deck1: str | None = None,
    deck2: str | None = None,
    all_matchups: bool = False,
    epsilon_start: float = 0.25,
    epsilon_end: float = 0.02,
    alpha: float = 0.03,
    seed: int | None = None,
    eval_every: int = 0,
    curriculum: str = "light",
    save_best: bool = False,
) -> dict:
    if seed is not None:
        random.seed(seed)

    logger.set_verbose(False)
    policy = MLPPolicy.load(policy_path)
    deck_heroes = [d["hero_id"] for d in data.get("decks", [])]
    if not deck_heroes:
        raise ValueError("Nenhum deck encontrado para treino RL.")

    all_pairs = _build_pairs(deck_heroes, None, None, True)
    fixed_pair = (deck1, deck2) if deck1 and deck2 else None
    eval_pairs = _build_pairs(deck_heroes, deck1, deck2, all_matchups)
    critical_pairs = eval_pairs[: min(2, len(eval_pairs))]
    eval_seed_set = [11, 29, 47]
    eval_games_per_seed = 1

    wins = {}
    reward_window = []
    inv_window = []
    pass_window = []
    action_window = defaultdict(int)
    best_eval = None
    best_checkpoint_tag = None

    for ep in range(episodes):
        epsilon = epsilon_start + (epsilon_end - epsilon_start) * (ep / max(1, episodes - 1))
        h1, h2 = _pick_pair_for_episode(
            ep=ep,
            episodes=episodes,
            deck_heroes=deck_heroes,
            fixed_pair=fixed_pair,
            all_pairs=all_pairs if all_matchups or fixed_pair is None else [],
            curriculum=curriculum,
        )

        ep_seed = None if seed is None else seed + ep * 13
        result, runtime = _run_single_game(
            hero1_id=h1,
            hero2_id=h2,
            data=data,
            card_pool=card_pool,
            tags_db=tags_db,
            policy=policy,
            training=True,
            epsilon=epsilon,
            seed=ep_seed,
        )
        wins[result["winner"]] = wins.get(result["winner"], 0) + 1

        if runtime is not None:
            summary = runtime.summarize()
            reward_window.append(summary["reward_avg"])
            inv_window.append(summary["invalid_action_rate"])
            pass_window.append(summary["pass_rate"])
            for scope, dist in summary["action_distribution"].items():
                for action, cnt in dist.items():
                    action_window[f"{scope}:{action}"] += cnt

        if (ep + 1) % max(1, episodes // 10) == 0:
            avg_reward = sum(reward_window) / max(1, len(reward_window))
            avg_inv = sum(inv_window) / max(1, len(inv_window))
            avg_pass = sum(pass_window) / max(1, len(pass_window))
            dominant_action = None
            if action_window:
                dominant_action = max(action_window.items(), key=lambda kv: kv[1])[0]
            collapse_warn = avg_pass > 0.75
            print(
                f"[RL] {ep+1}/{episodes} eps={epsilon:.3f} match={h1} vs {h2} "
                f"winner={result['winner']} reward_avg={avg_reward:+.3f} "
                f"invalid_rate={avg_inv:.3f} pass_rate={avg_pass:.3f}"
            )
            if dominant_action:
                print(f"[RL] action_dominance={dominant_action}")
            if collapse_warn:
                print("[RL][warn] policy may be collapsing to pass-heavy behavior.")
            reward_window.clear()
            inv_window.clear()
            pass_window.clear()
            action_window.clear()

        if eval_every > 0 and (ep + 1) % eval_every == 0:
            snapshot = _evaluate_policy_snapshot(
                policy=policy,
                pairs=eval_pairs,
                data=data,
                card_pool=card_pool,
                tags_db=tags_db,
                seeds=eval_seed_set,
                games_per_seed=eval_games_per_seed,
            )
            promoted = _passes_promotion(snapshot, critical_pairs)
            print(
                f"[RL-EVAL] ep={ep+1} base={snapshot['global_base_wr']:.2f}% "
                f"rl={snapshot['global_rl_wr']:.2f}% delta={snapshot['global_delta_pp']:+.2f}pp "
                f"promoted={'yes' if promoted else 'no'}"
            )
            if save_best and promoted:
                if best_eval is None or snapshot["global_delta_pp"] > best_eval["global_delta_pp"]:
                    best_eval = snapshot
                    best_checkpoint_tag = f"ep{ep+1}_{int(time.time())}"
                    best_path = os.path.splitext(policy_path)[0] + "_best.pt"
                    policy.save(
                        best_path,
                        metadata={
                            "best_checkpoint_tag": best_checkpoint_tag,
                            "eval_summary": best_eval,
                            "training_config": {
                                "episodes": episodes,
                                "eval_every": eval_every,
                                "curriculum": curriculum,
                                "save_best": save_best,
                            },
                        },
                        checkpoint_tag=best_checkpoint_tag,
                    )
                    print(f"[RL-EVAL] new best checkpoint saved at {best_path}")

    os.makedirs(os.path.dirname(policy_path), exist_ok=True)
    final_metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "training_config": {
            "episodes": episodes,
            "deck1": deck1,
            "deck2": deck2,
            "all_matchups": all_matchups,
            "epsilon_start": epsilon_start,
            "epsilon_end": epsilon_end,
            "alpha": alpha,
            "seed": seed,
            "eval_every": eval_every,
            "curriculum": curriculum,
            "save_best": save_best,
            "seed_set": eval_seed_set,
        },
        "eval_summary": best_eval if best_eval is not None else {},
        "best_checkpoint_tag": best_checkpoint_tag,
    }
    policy.save(policy_path, metadata=final_metadata, checkpoint_tag=best_checkpoint_tag)

    result = {
        "episodes": episodes,
        "policy_path": policy_path,
        "wins": wins,
        "training_config": final_metadata["training_config"],
        "eval_summary": final_metadata["eval_summary"],
        "best_checkpoint_tag": best_checkpoint_tag,
    }
    if save_best:
        best_path = os.path.splitext(policy_path)[0] + "_best.pt"
        if not os.path.exists(best_path):
            fallback_tag = best_checkpoint_tag or "fallback_final"
            policy.save(
                best_path,
                metadata={
                    "training_config": final_metadata["training_config"],
                    "eval_summary": final_metadata["eval_summary"],
                    "best_checkpoint_tag": fallback_tag,
                    "promotion_status": "fallback_not_promoted",
                },
                checkpoint_tag=fallback_tag,
            )
        result["best_policy_path"] = best_path
    return result
