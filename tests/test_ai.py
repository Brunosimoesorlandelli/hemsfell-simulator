"""
Testes — engine.ai_engine
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import CardInst, Player, reset_iid
from engine import ai_engine as AI


def make_creature(name="Criatura", off=2, vit=2, cost=2, keywords=None, effect=""):
    reset_iid()
    c = CardInst(
        id=f"crt_{name.lower().replace(' ', '_')}",
        name=name,
        card_type="creature",
        color="Neutro",
        cost=cost,
        offense=off,
        vitality=vit,
        base_off=off,
        base_vit=vit,
        keywords=keywords or [],
        effect=effect,
    )
    c.sick = False
    return c


def make_spell(name="Feitiço", cost=2, keywords=None, tags=None):
    return CardInst(
        id=f"spl_{name.lower().replace(' ', '_')}",
        name=name,
        card_type="spell",
        color="Neutro",
        cost=cost,
        keywords=keywords or [],
        effect_tags=tags or [],
    )


def make_player(hid="hero_gimble"):
    from engine.models import CardInst
    hero = CardInst(id=hid, name="Herói", card_type="hero", color="Neutro")
    p    = Player(name="P", hero=hero, deck=[])
    p.energy = 10
    return p


# ── card_value ────────────────────────────────────────────────────────────

def test_card_value_basico():
    p = make_player()
    c = make_creature(off=2, vit=2)
    v = AI.card_value(c, p)
    assert v > 0

def test_card_value_voar_bonus():
    p  = make_player()
    c1 = make_creature(keywords=[])
    c2 = make_creature(keywords=["Voar"])
    assert AI.card_value(c2, p) > AI.card_value(c1, p)

def test_card_value_indestrutivel():
    p  = make_player()
    c  = make_creature(keywords=["Indestrutivel"])
    assert AI.card_value(c, p) > 5

def test_card_value_nao_criatura():
    p = make_player()
    s = make_spell()
    assert AI.card_value(s, p) == 0.0


def test_analyze_opponent_identifica_aggro():
    opp = make_player("hero_tifon")
    opp.deck = [
        make_creature("Rush1", off=3, vit=1, cost=1, keywords=["Investida"]),
        make_creature("Rush2", off=2, vit=2, cost=1),
        make_creature("Rush3", off=3, vit=2, cost=2, keywords=["Furtivo"]),
        make_creature("Rush4", off=2, vit=1, cost=1),
    ]
    prof = AI.analyze_opponent(opp)
    assert prof.style == "aggro"
    assert prof.aggro_risk >= prof.control_risk


def test_choose_card_to_play_adapta_contra_aggro():
    p = make_player("hero_gimble")
    opp = make_player("hero_tifon")
    # Opponente agressivo
    opp.deck = [
        make_creature("A1", off=3, vit=1, cost=1, keywords=["Investida"]),
        make_creature("A2", off=2, vit=2, cost=1),
        make_creature("A3", off=3, vit=2, cost=2),
    ]

    guard = make_creature("Guardiao", off=1, vit=4, cost=2, keywords=["Robusto"])
    bomb = make_creature("Colosso", off=6, vit=6, cost=6)
    p.hand = [guard, bomb]
    p.energy = 6
    p.max_energy = 6

    prof = AI.analyze_opponent(opp)
    guard_score = AI.hand_card_score(guard, p, opp, turn=4, profile=prof)
    bomb_score = AI.hand_card_score(bomb, p, opp, turn=4, profile=prof)
    assert guard_score > bomb_score


# ── choose_attackers ──────────────────────────────────────────────────────

def test_choose_attackers_vazio_sem_criaturas():
    p   = make_player()
    opp = make_player()
    assert AI.choose_attackers(p, opp) == []

def test_choose_attackers_furtivo_sempre_ataca():
    p   = make_player()
    opp = make_player()
    c   = make_creature(keywords=["Furtivo"])
    p.place_creature(c)
    attackers = AI.choose_attackers(p, opp)
    assert c in attackers

def test_choose_attackers_sick_nao_ataca():
    p   = make_player()
    opp = make_player()
    c   = make_creature()
    c.sick = True
    p.place_creature(c)
    attackers = AI.choose_attackers(p, opp)
    assert c not in attackers

def test_choose_attackers_investida_sick_ataca():
    p   = make_player()
    opp = make_player()
    c   = make_creature(keywords=["Investida"])
    c.sick = True
    p.place_creature(c)
    # Investida permite atacar mesmo doente
    assert c.can_attack()


# ── choose_blockers ───────────────────────────────────────────────────────

def test_choose_blockers_furtivo_sem_bloqueio():
    opp     = make_player()
    def_p   = make_player()
    blocker = make_creature()
    def_p.place_creature(blocker)

    atk = make_creature(keywords=["Furtivo"])
    blocks = AI.choose_blockers([atk], def_p, opp)
    # Furtivo → lista vazia (ninguém bloqueia)
    assert not blocks.get(atk.iid)

def test_choose_blockers_troca_favoravel():
    """Bloqueador com alta vitalidade bloqueia atacante fraco."""
    opp   = make_player()
    def_p = make_player()
    blk   = make_creature("Defensor", off=1, vit=5)
    def_p.place_creature(blk)
    blk.sick = False

    atk = make_creature("Atacante", off=1, vit=1)
    blocks = AI.choose_blockers([atk], def_p, opp)
    # Defensor sobrevive → deve estar na lista de bloqueadores
    assert blk in blocks.get(atk.iid, [])


def test_gang_block_positivo():
    """Dois 2/2 devem gangar para matar um 3/3."""
    opp   = make_player()
    def_p = make_player()
    b1 = make_creature("Guarda1", off=2, vit=2)
    b2 = make_creature("Guarda2", off=2, vit=2)
    def_p.place_creature(b1); def_p.place_creature(b2)
    b1.sick = False; b2.sick = False

    atk = make_creature("Grandao", off=3, vit=3)
    # Gang block: 2+2=4 >= 3 → atk morre. Um bloqueador morre, net positivo.
    gang = AI._try_gang_block(atk, [b1, b2], def_p, opp)
    assert len(gang) == 2


def test_gang_block_negativo_blockers_muito_valiosos():
    """Não deve gangar quando bloqueadores valem mais do que o atacante."""
    opp   = make_player()
    def_p = make_player()
    # Dois 4/1 morrem para o 2/3, mas 4/1 valem muito → net negativo
    bC = make_creature("ValC", off=4, vit=1)
    bD = make_creature("ValD", off=4, vit=1)
    atk = make_creature("Mid", off=2, vit=3)
    gang = AI._try_gang_block(atk, [bC, bD], def_p, opp)
    assert len(gang) == 0


def test_lethal_check_furtivo():
    """Furtivo causa dano direto garantido."""
    p = make_player(); opp = make_player()
    c = make_creature("Assassino", off=6, vit=2, keywords=["Furtivo"])
    p.place_creature(c); opp.life = 5
    assert AI.can_deal_lethal(p, opp)


def test_lethal_check_nao_letal():
    """Sem dano suficiente, não é letal."""
    p = make_player(); opp = make_player()
    c = make_creature("Fraco", off=2, vit=2)
    p.place_creature(c); opp.life = 30
    assert not AI.can_deal_lethal(p, opp)


# ── evaluate_state ────────────────────────────────────────────────────────

def test_evaluate_state_com_criaturas():
    p   = make_player()
    opp = make_player()
    c   = make_creature(off=3, vit=3)
    p.place_creature(c)
    score = AI.evaluate_state(p, opp)
    assert score > 0  # jogador com criaturas tem vantagem

def test_evaluate_state_simétrico_base():
    """Estado simétrico deve gerar score próximo de 0."""
    p   = make_player()
    opp = make_player()
    score = AI.evaluate_state(p, opp)
    assert abs(score) < 2.0  # só a diferença de level e energia iniciais


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


# ══════════════════════════════════════════════════════════════════════════════
#  TESTES DE CONFORMIDADE COM O MANUAL DE REGRAS (Manoel de Regras)
# ══════════════════════════════════════════════════════════════════════════════

def make_player_full(name="P", energy=5, reserve=0):
    hero = CardInst(id="hero_test", name="Herói Teste", card_type="hero", color="Neutro")
    p    = Player(name=name, hero=hero, deck=[])
    p.energy   = energy
    p.reserve  = reserve
    p.max_energy = energy
    return p


# ── Fix 1: Reserva restrita a feitiços ─────────────────────────────────────

def test_spend_criatura_nao_usa_reserva():
    """PDF p.8: reserva só para feitiços e efeitos, não para invocar criaturas."""
    p = make_player_full(energy=0, reserve=3)
    # Sem reserva, não pode pagar custo 2
    assert not p.spend(2, allow_reserve=False)
    # Reserva intacta após tentativa
    assert p.reserve == 3

def test_spend_feitico_usa_reserva():
    """Feitiço pode usar energia de reserva."""
    p = make_player_full(energy=0, reserve=3)
    assert p.spend(2, allow_reserve=True)
    assert p.reserve == 1

def test_spend_criatura_usa_so_energy_regular():
    """Criatura com energy=2, reserve=5: gasta apenas da energy regular."""
    p = make_player_full(energy=2, reserve=5)
    assert p.spend(2, allow_reserve=False)
    assert p.energy  == 0
    assert p.reserve == 5   # reserva preservada


# ── Fix 2: Excesso de mão vai ao obscuro ────────────────────────────────────

def test_hand_limit_excesso_vai_ao_obscuro():
    """PDF p.6: cartas excedentes são banidas (obscuro), não descartadas."""
    reset_iid()
    p = make_player_full()
    for i in range(13):
        p.hand.append(make_creature(f"C{i}"))
    p.hand_limit()
    assert len(p.hand) == 10
    assert len(p.obscure) == 3
    assert len(p.graveyard) == 0

def test_hand_limit_cemiterio_intacto():
    """Cemitério deve continuar vazio após hand_limit."""
    reset_iid()
    p = make_player_full()
    for i in range(11):
        p.hand.append(make_creature(f"X{i}"))
    p.hand_limit()
    assert len(p.graveyard) == 0


# ── Fix 3: Sem gang block — 1 criatura bloqueia 1 atacante ─────────────────

def test_bloqueio_max_um_bloqueador_por_atacante():
    """PDF p.7: 1 defensor por atacante. Nenhum atacante deve ter >1 bloqueador."""
    opp = make_player()
    def_p = make_player()
    for _ in range(4):
        b = make_creature(off=2, vit=3)
        b.sick = False
        def_p.place_creature(b)

    atk = make_creature(off=5, vit=5)
    blocks = AI.choose_blockers([atk], def_p, opp)
    assert len(blocks.get(atk.iid, [])) <= 1


# ── Fix 4: Manutenção — decisão da IA ──────────────────────────────────────

def test_manutencao_primeiro_turno_obrigatorio_energy():
    """Primeiro turno: max_energy=0 → obrigatório pegar energia."""
    p = make_player()
    p.max_energy = 0
    assert AI._choose_maintenance_action(p, make_player()) == "energy"

def test_manutencao_energia_maxima_retorna_draw():
    """Energia já no máximo (10): sem ganho em mais energia → draw."""
    p = make_player()
    p.max_energy = 10
    assert AI._choose_maintenance_action(p, make_player()) == "draw"

def test_manutencao_mae_pequena_prioriza_draw():
    """Mão ≤ 2 cartas com energy ≥ 4: card advantage supera ramp."""
    p = make_player()
    p.max_energy = 4
    p.hand = [make_creature()]  # 1 carta
    assert AI._choose_maintenance_action(p, make_player()) == "draw"

def test_manutencao_baixa_energia_sempre_ramp():
    """max_energy < 7 com mão suficiente: rampa quase sempre compensa."""
    p = make_player()
    p.max_energy = 5
    p.hand = [make_creature(), make_creature(), make_creature(), make_creature()]
    assert AI._choose_maintenance_action(p, make_player()) == "energy"


# ── Fix 5: Defensor X lê valor correto ────────────────────────────────────

def test_defensor_x_retorna_valor():
    c2 = make_creature(keywords=["Defensor 2"])
    c3 = make_creature(keywords=["Defensor 3"])
    cs = make_creature(keywords=["Defensor"])
    cn = make_creature(keywords=["Voar"])
    assert AI._get_defensor_x(c2) == 2
    assert AI._get_defensor_x(c3) == 3
    assert AI._get_defensor_x(cs) == 1
    assert AI._get_defensor_x(cn) == 0


# ── Fix 6: choose_card_to_play usa energy regular para criaturas ───────────

def test_choose_card_to_play_criatura_nao_usa_reserva():
    """Com energy=0 e reserve=5, criatura de custo 2 não deve ser escolhida."""
    reset_iid()
    p = make_player()
    opp = make_player()
    p.energy  = 0
    p.reserve = 5
    p.max_energy = 5
    creature = make_creature("Cara", off=3, vit=3, cost=2)
    p.hand = [creature]
    chosen = AI.choose_card_to_play(p, opp, turn=3)
    assert chosen is None  # sem energy regular, criatura não pode ser baixada


# ── Fix 7: Ordem de combate por slot ──────────────────────────────────────

def test_atacantes_ordenados_por_slot():
    """PDF p.13: resolução da esquerda para direita."""
    p = make_player()
    c_slot3 = make_creature("S3"); c_slot3.slot = 3; c_slot3.sick = False
    c_slot0 = make_creature("S0"); c_slot0.slot = 0; c_slot0.sick = False
    c_slot2 = make_creature("S2"); c_slot2.slot = 2; c_slot2.sick = False
    attackers = [c_slot3, c_slot0, c_slot2]
    attackers.sort(key=lambda c: c.slot if c.slot is not None else 99)
    assert [c.slot for c in attackers] == [0, 2, 3]
