"""
Testes — engine.simulator (integração)
Roda partidas reais entre decks e valida o resultado.
"""

import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.loader import load_data, build_card_pool, load_tags, build_deck_for_hero
from engine.models import Player, reset_iid
from engine.simulator import GameState
from engine import logger


def _run(hero1: str, hero2: str, seed: int = 42) -> dict:
    """Roda uma partida determinística e retorna o resultado."""
    random.seed(seed)
    reset_iid()
    logger.clear()

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()

    h1, d1 = build_deck_for_hero(hero1, data, card_pool, tags_db)
    h2, d2 = build_deck_for_hero(hero2, data, card_pool, tags_db)

    p1 = Player(name=f"J1_{hero1}", hero=h1, deck=d1)
    p2 = Player(name=f"J2_{hero2}", hero=h2, deck=d2)

    gs = GameState(p1, p2, card_pool, tags_db)
    return gs.run()


# ── Testes básicos de sanidade ────────────────────────────────────────────

def test_partida_termina():
    """Uma partida sempre termina (não entra em loop infinito)."""
    r = _run("hero_gimble", "hero_sr_goblin")
    assert r["turns"] >= 1

def test_partida_tem_vencedor_ou_empate():
    r = _run("hero_gimble", "hero_sr_goblin")
    assert r["winner"] in (r["p1_name"], r["p2_name"], "Empate")

def test_vidas_razoaveis():
    """Vida do perdedor deve ser ≤ 0 ao final."""
    r = _run("hero_gimble", "hero_tifon")
    if r["winner"] == r["p1_name"]:
        assert r["p2_life"] <= 0 or r["turns"] >= 40
    elif r["winner"] == r["p2_name"]:
        assert r["p1_life"] <= 0 or r["turns"] >= 40

def test_turnos_dentro_do_limite():
    from engine.config import MAX_TURNS
    r = _run("hero_tesslia", "hero_rasmus")
    assert r["turns"] <= MAX_TURNS

def test_resultado_deterministico():
    """Mesma seed deve gerar mesmo resultado."""
    r1 = _run("hero_gimble", "hero_sr_goblin", seed=7)
    r2 = _run("hero_gimble", "hero_sr_goblin", seed=7)
    assert r1["winner"] == r2["winner"]
    assert r1["turns"]  == r2["turns"]

def test_kills_nao_negativo():
    r = _run("hero_tifon", "hero_quarion")
    assert r["p1_kills"] >= 0
    assert r["p2_kills"] >= 0

def test_dano_nao_negativo():
    r = _run("hero_gimble", "hero_tesslia")
    assert r["p1_damage"] >= 0
    assert r["p2_damage"] >= 0

def test_cartas_jogadas_registradas():
    r = _run("hero_sr_goblin", "hero_tifon")
    # Ao menos alguma carta deve ter sido jogada
    assert len(r["p1_cards"]) > 0 or len(r["p2_cards"]) > 0


# ── Testes de múltiplos matchups ──────────────────────────────────────────

def test_varios_herois():
    """Todos os heróis com deck devem conseguir completar uma partida."""
    pares = [
        ("hero_gimble",    "hero_tifon"),
        ("hero_sr_goblin", "hero_rasmus"),
        ("hero_tesslia",   "hero_quarion"),
        ("hero_ngoro",     "hero_colecionador"),
        ("hero_saymon_primeiro", "hero_uruk"),
    ]
    for h1, h2 in pares:
        r = _run(h1, h2)
        assert r["turns"] >= 1, f"Partida {h1} vs {h2} falhou"


# ── Runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_")]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅  {name}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ❌  {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passou, {failed} falhou.")
