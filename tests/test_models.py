"""
Testes — engine.models
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import CardInst, Player, reset_iid


def make_creature(name="Teste", off=2, vit=2, cost=2, keywords=None):
    reset_iid()
    return CardInst(
        id=f"crt_{name.lower()}",
        name=name,
        card_type="creature",
        color="Neutro",
        cost=cost,
        offense=off,
        vitality=vit,
        base_off=off,
        base_vit=vit,
        keywords=keywords or [],
    )


def make_hero(hid="hero_test"):
    return CardInst(
        id=hid,
        name="Herói Teste",
        card_type="hero",
        color="Neutro",
    )


def make_player(name="P1", hid="hero_test"):
    hero = make_hero(hid)
    return Player(name=name, hero=hero, deck=[])


# ── CardInst ──────────────────────────────────────────────────────────────

def test_cur_off_normal():
    c = make_creature(off=3)
    assert c.cur_off() == 3

def test_cur_off_congelado():
    c = make_creature(off=3)
    c.status.append("Congelado")
    assert c.cur_off() == 0

def test_cur_off_sufocado():
    c = make_creature(off=3)
    c.status.append("Sufocado")
    assert c.cur_off() == 0

def test_cur_vit_nao_negativo():
    c = make_creature(vit=1)
    c.vitality = -5
    assert c.cur_vit() == 0

def test_has_kw_sufocado():
    c = make_creature(keywords=["Voar"])
    c.status.append("Sufocado")
    assert not c.has_kw("Voar")

def test_has_kw_normal():
    c = make_creature(keywords=["Voar"])
    assert c.has_kw("Voar")

def test_can_attack_sick():
    c = make_creature()
    c.sick = True
    assert not c.can_attack()

def test_can_attack_investida_sick():
    c = make_creature(keywords=["Investida"])
    c.sick = True
    assert c.can_attack()

def test_can_attack_tapped():
    c = make_creature()
    c.sick = False
    c.tapped = True
    assert not c.can_attack()

def test_add_marker_buff():
    c = make_creature(off=1, vit=1)
    c.add_marker("+1/+1", 2)
    assert c.offense == 3
    assert c.vitality == 3
    assert c.base_off == 3


# ── Player ────────────────────────────────────────────────────────────────

def test_place_and_remove_creature():
    p = make_player()
    c = make_creature()
    slot = p.place_creature(c)
    assert slot >= 0
    assert c in p.field_creatures
    p.remove_creature(c)
    assert c not in p.field_creatures

def test_field_size():
    p = make_player()
    assert p.field_size() == 0
    c1 = make_creature("A")
    c2 = make_creature("B")
    p.place_creature(c1)
    p.place_creature(c2)
    assert p.field_size() == 2

def test_spend_energy():
    p = make_player()
    p.energy = 5
    assert p.spend(3)
    assert p.energy == 2

def test_spend_reserve():
    p = make_player()
    p.energy  = 2
    p.reserve = 3
    assert p.spend(4)
    assert p.energy  == 0
    assert p.reserve == 1

def test_spend_insuficiente():
    p = make_player()
    p.energy = 1
    assert not p.spend(3)

def test_draw_card():
    from engine.models import CardInst
    p    = make_player()
    card = make_creature("Carta")
    p.deck.append(card)
    drawn = p.draw_card(1)
    assert len(drawn) == 1
    assert drawn[0] is card
    assert card in p.hand

def test_heal_cap():
    p = make_player()
    p.life = 28
    p.heal(10)
    assert p.life == 30  # cap em STARTING_LIFE

def test_commander_slot():
    p = make_player()
    c1 = make_creature("A")
    c2 = make_creature("B")
    c3 = make_creature("C")
    p.place_creature(c1)
    p.place_creature(c2)
    p.place_creature(c3)
    cmd = p.commander()
    assert cmd is c2  # slot do meio (índice 1 de 3)

def test_reset_turn_flags():
    p = make_player()
    p.spells_cast_this_turn = 5
    p.deaths_this_turn      = 3
    p.reset_turn_flags()
    assert p.spells_cast_this_turn == 0
    assert p.deaths_this_turn      == 0


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
            print(f"  ❌  {name}: {e}")
            failed += 1
    print(f"\n{passed} passou, {failed} falhou.")
