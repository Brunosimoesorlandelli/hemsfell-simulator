"""
╔══════════════════════════════════════════════════════════╗
║       HEMSFELL HEROES — MOTOR DE IA TÁTICA v2.0         ║
╚══════════════════════════════════════════════════════════╝

Arquitetura:
  - Avaliação por score numérico de estado/carta
  - Decisões com look-ahead de 1 turno
  - Bloqueio por troca favorável
  - Prioridade de ataque por keywords e situação
  - Sinergias por herói para criaturas, feitiços e permanentes
  - Scoring contextual de board state (deficit/surplus)
  - Sequenciamento intra-turno via played_this_turn
  - Filtragem de alvos em feitiços de remoção
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from .config import AI_KW_VALUE, AI_LIFE_VALUE, MAX_ENERGY

if TYPE_CHECKING:
    from .models import CardInst, Player


@dataclass(frozen=True)
class OpponentProfile:
    style: str
    aggro_risk: float
    control_risk: float
    board_risk: float
    removal_density: float
    creature_density: float


def analyze_opponent(opp: "Player") -> OpponentProfile:
    known = list(opp.deck) + list(opp.hand) + list(opp.field_creatures) + \
        list(opp.spells_field) + list(opp.graveyard)
    total = max(1, len(known))

    creatures = [c for c in known if c.card_type in ("creature", "image")]
    spells = [c for c in known if c.card_type == "spell"]
    constants = [c for c in known if c.card_type in ("enchant", "terrain", "artifact")]
    creature_density = len(creatures) / total

    avg_creature_cost = (sum(c.cost for c in creatures) / len(creatures)) if creatures else 0.0
    avg_creature_off = (sum(c.base_off for c in creatures) / len(creatures)) if creatures else 0.0
    low_curve = sum(1 for c in creatures if c.cost <= 2) / max(1, len(creatures))
    big_body = sum(1 for c in creatures if c.base_off + c.base_vit >= 7) / max(1, len(creatures))
    evasive = sum(1 for c in creatures if any(
        kw in c.keywords for kw in ("Furtivo", "Voar", "Atropelar", "Investida")
    )) / max(1, len(creatures))

    removal_tags = 0
    draw_tags = 0
    for c in known:
        for t in getattr(c, "effect_tags", []):
            action = t.get("action", "")
            if action in ("destroy", "deal_damage", "return_hand", "apply_status", "tap"):
                removal_tags += 1
            if action in ("draw", "search", "search_graveyard"):
                draw_tags += 1
    removal_density = removal_tags / total
    spell_density = len(spells) / total

    hero_aggro = 0.0
    hero_control = 0.0
    hid = opp.hero.id
    if hid in ("hero_tifon", "hero_tesslia", "hero_sr_goblin"):
        hero_aggro += 0.8
    if hid in ("hero_ngoro", "hero_colecionador", "hero_uruk"):
        hero_control += 0.8
    if hid in ("hero_rasmus", "hero_quarion", "hero_gimble"):
        hero_control += 0.3
        hero_aggro += 0.2

    aggro = low_curve * 2.0 + evasive * 1.4 + avg_creature_off * 0.25 + hero_aggro
    control = spell_density * 2.1 + removal_density * 2.6 + draw_tags * 0.08 + hero_control
    midrange = creature_density * 1.5 + big_body * 1.7 + avg_creature_cost * 0.28

    # Correção: quando menos de 30% do deck foi revelado, suaviza o perfil
    # em direção ao neutro para evitar decisões baseadas em amostra pequena.
    revealed = (len(opp.hand) + len(opp.graveyard)
                + len(opp.field_creatures) + len(opp.spells_field))
    total_known = revealed + len(opp.deck)
    reveal_ratio = revealed / max(1, total_known)
    if reveal_ratio < 0.3:
        blend    = reveal_ratio / 0.3
        aggro    = aggro    * blend + 1.0 * (1 - blend)
        control  = control  * blend + 1.0 * (1 - blend)
        midrange = midrange * blend + 1.5 * (1 - blend)

    style = "midrange"
    best = max(aggro, control, midrange)
    if best == aggro:
        style = "aggro"
    elif best == control:
        style = "control"

    return OpponentProfile(
        style=style,
        aggro_risk=aggro,
        control_risk=control,
        board_risk=midrange,
        removal_density=removal_density,
        creature_density=creature_density,
    )


# ─────────────────────────────────────────────────────────
#  CACHE DE PERFIL DO OPONENTE
# ─────────────────────────────────────────────────────────

_PROFILE_CACHE: dict = {}
_PROFILE_CACHE_MAX = 4


def _profile_cache_key(opp: "Player") -> tuple:
    return (
        id(opp),
        opp.hero.id,
        len(opp.field_creatures),
        len(opp.hand),
        len(opp.graveyard),
        len(opp.spells_field),
        len(opp.deck),
    )


def get_opponent_profile(opp: "Player") -> OpponentProfile:
    global _PROFILE_CACHE
    key = _profile_cache_key(opp)
    if key in _PROFILE_CACHE:
        return _PROFILE_CACHE[key]
    if len(_PROFILE_CACHE) >= _PROFILE_CACHE_MAX:
        _PROFILE_CACHE = {}
    profile = analyze_opponent(opp)
    _PROFILE_CACHE[key] = profile
    return profile


# ─────────────────────────────────────────────────────────
#  AVALIAÇÃO DE CARTA EM CAMPO
# ─────────────────────────────────────────────────────────

def card_value(card: "CardInst", owner: "Player") -> float:
    """Score numérico de uma criatura no campo. Quanto maior, mais valiosa."""
    if card.card_type not in ("creature", "image"):
        return 0.0
    base = card.cur_off() * 1.2 + card.cur_vit() * 1.0
    kw_bonus = sum(AI_KW_VALUE.get(kw, 0) for kw in card.keywords
                   if "Sufocado" not in card.status)
    effect_bonus  = 1.5 if "Suspiro" in card.effect else 0.0
    effect_bonus += 1.0 if "Primeiro Ato" in card.effect else 0.0
    sick_penalty  = 0.5 if card.sick and not card.has_kw("Investida") else 0.0
    return max(0.0, base + kw_bonus + effect_bonus - sick_penalty)


def hand_card_score(card: "CardInst", owner: "Player",
                    opp: "Player", turn: int,
                    profile: OpponentProfile | None = None,
                    played_this_turn: list | None = None) -> float:
    profile = profile or get_opponent_profile(opp)
    played_this_turn = played_this_turn or []
    played_types = {c.card_type for c in played_this_turn}

    # ── Board state: urgência de popular ou não o campo ──
    board_score = sum(card_value(c, owner) for c in owner.field_creatures)
    opp_board_score = sum(card_value(c, opp) for c in opp.field_creatures)
    board_deficit = opp_board_score - board_score  # positivo = oponente tem vantagem de board

    if card.card_type == "creature":
        # Correção 1: penalty progressiva — cartas acima de custo 4 são
        # descontadas mais fortemente para refletir o custo de oportunidade real.
        cost_penalty = card.cost * 0.6 + max(0, card.cost - 4) * 0.4
        base = card_value(card, owner) - cost_penalty

        # Urgência de popular o board
        if board_deficit > 4.0:
            base += min(2.0, board_deficit * 0.2)

        # Correção 2: bônus de campo vazio inversamente proporcional ao custo.
        # Cartas baratas são mais incentivadas a estabelecer presença cedo.
        if owner.field_size() == 0:
            base += max(0.5, 2.0 - card.cost * 0.2)
        if owner.field_size() >= 4 and not card.has_kw("Investida"):
            base -= 1.5

        if profile.aggro_risk > profile.control_risk:
            base += max(0.0, 3.0 - card.cost) * 0.9
            base += card.base_vit * 0.22
            base -= max(0.0, card.cost - 3.0) * 0.9
            if turn <= 6 and card.cost >= 5:
                base -= 2.5
            if any(kw in card.keywords for kw in ("Robusto", "Defensor", "Roubo de Vida")):
                base += 1.0
        elif profile.control_risk > profile.aggro_risk:
            if any(kw in card.keywords for kw in ("Furtivo", "Voar", "Investida")):
                base += 1.5
            base += card.cost * 0.12

        # Sequenciamento: se já jogou encanto/terreno este turno,
        # criatura ganha bônus pois o campo já foi preparado
        if "enchant" in played_types or "terrain" in played_types:
            base += 0.5

        base += _hero_creature_bonus(card, owner)
        return base

    if card.card_type == "spell":
        if "Acelerado" in card.keywords:
            return -99.0
        score = _spell_score(card, owner, opp, profile)
        score += _hero_spell_bonus(card, owner)
        return score

    if card.card_type in ("enchant", "terrain"):
        ally_count = owner.field_size()
        score = 1.5 + ally_count * 0.4 - card.cost * 0.3
        if profile.control_risk > profile.aggro_risk:
            score += 0.5
        # Se board está em déficit, permanentes de suporte valem menos agora
        if board_deficit > 3.0 and ally_count == 0:
            score -= 1.0
        score += _hero_permanent_bonus(card, owner)
        return score

    if card.card_type == "artifact":
        if owner.field_size() == 0:
            return -1.0
        score = 1.5 - card.cost * 0.2
        if profile.aggro_risk > profile.control_risk:
            score += 0.4
        # Bônus se já jogou criatura este turno — slot garantido
        if "creature" in played_types:
            score += 0.8
        score += _hero_permanent_bonus(card, owner)
        return score

    return 0.0


def _matches_filter(card: "CardInst", filt: str) -> bool:
    """Verifica se uma carta de campo passa por um filtro de efeito."""
    if not filt:
        return True
    if "tapped" in filt:
        return card.tapped
    if "creature" in filt:
        return card.card_type in ("creature", "image")
    if "cost" in filt:
        # ex: "cost<=3"
        try:
            op = "<=" if "<=" in filt else (">=" if ">=" in filt else "==")
            val = int(filt.split(op)[-1])
            if op == "<=":
                return card.cost <= val
            if op == ">=":
                return card.cost >= val
            return card.cost == val
        except (ValueError, IndexError):
            return True
    return True


def _spell_score(card: "CardInst", owner: "Player", opp: "Player",
                 profile: OpponentProfile | None = None) -> float:
    profile = profile or get_opponent_profile(opp)
    tags  = card.effect_tags
    score = 0.5

    for tag in tags:
        action = tag.get("action", "")
        target = tag.get("target", "")
        filt   = tag.get("filter", "")

        if action == "deal_damage":
            val = _resolve_value(tag.get("value", 1), owner)
            if "all_enemy" in target:
                score += val * len(opp.field_creatures) * 0.8
            elif "enemy_hero" in target:
                score += val * 1.5
            elif opp.field_creatures:
                min_vit = min(c.cur_vit() for c in opp.field_creatures)
                score += val * (2.0 if val >= min_vit else 1.0)
            if profile.aggro_risk > profile.control_risk:
                score += 0.8

        elif action == "draw":
            score += _resolve_value(tag.get("value", 1), owner) * 1.2
            if profile.control_risk >= profile.aggro_risk:
                score += 0.6

        elif action == "destroy":
            # Considera o alvo específico no campo do oponente
            targets = [c for c in opp.field_creatures if _matches_filter(c, filt)]
            if targets:
                best_target = max(targets, key=lambda c: card_value(c, opp))
                score += card_value(best_target, opp) * 0.9
                # Bônus extra se remove a maior ameaça de dano
                if best_target.cur_off() >= owner.life * 0.3:
                    score += 2.0
            score += 0.7 * profile.board_risk

        elif action == "buff":
            if owner.field_creatures:
                score += 1.8
                # Buff vale mais se já há criaturas com Investida no campo
                if any(c.has_kw("Investida") for c in owner.field_creatures):
                    score += 0.8

        elif action == "revive":
            creatures = [c for c in owner.graveyard if c.card_type == "creature"]
            if creatures:
                score += max(card_value(c, owner) for c in creatures) * 0.7

        elif action == "heal":
            val = _resolve_value(tag.get("value", 2), owner)
            urgency = max(0.0, (15 - owner.life) / 15)
            score += val * (0.4 + urgency * 0.8)
            if profile.aggro_risk > profile.control_risk:
                score += 0.8

        elif action == "mill":
            score += 0.8
            if profile.control_risk > profile.aggro_risk:
                score += 0.5

        elif action in ("search", "search_graveyard"):
            score += 2.0

        elif action == "return_hand":
            if opp.field_creatures:
                best = max(opp.field_creatures, key=lambda c: card_value(c, opp))
                score += card_value(best, opp) * 0.7

        elif action == "apply_status":
            if opp.field_creatures:
                score += 1.5

    score -= card.cost * 0.3
    return score


def _resolve_value(value, owner: "Player") -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value == "X":
        return float(len(owner.hand))
    return 1.0


# ─────────────────────────────────────────────────────────
#  SINERGIAS POR HERÓI
# ─────────────────────────────────────────────────────────

def _hero_creature_bonus(card: "CardInst", owner: "Player") -> float:
    hid  = owner.hero.id
    race = card.race.lower()
    name = card.name.lower()

    if hid == "hero_gimble":
        if "dragao" in race or "dragon" in race:
            if "verdadeiro" in name:
                has_pseudo = any("pseudo" in c.name.lower()
                                 for c in owner.field_creatures)
                return 4.0 if has_pseudo else -2.0
            return 2.0
        return -0.5

    if hid == "hero_tifon":
        if "Suspiro" in card.effect or "Ultimo Suspiro" in card.effect:
            return 2.0
        if "Investida" in card.keywords:
            return 1.0

    if hid == "hero_saymon_primeiro":
        if "vampiro" in race:
            return 1.5

    if hid == "hero_rasmus":
        if "gato" in race:
            return 1.5

    if hid == "hero_tesslia":
        cmd = owner.commander()
        if cmd is None:
            return card.cur_off() * 0.3
        return 0.5

    if hid == "hero_quarion":
        existing_names = {c.name for c in owner.field_creatures}
        bonus  = 2.0 if "Primeiro Ato" in card.effect and card.name not in existing_names else 0.0
        bonus += 1.0 if card.name not in existing_names else -0.5
        return bonus

    if hid == "hero_sr_goblin":
        if "goblin" in race:
            if "fura-fila" in card.effect.lower() or "fura_fila" in card.effect.lower():
                return 1.5 + owner.fura_fila_count * 0.5
            return 0.8

    if hid == "hero_ngoro":
        if "Furtivo" in card.keywords:
            return 2.0
        if "investig" in card.effect.lower():
            return 1.5

    if hid == "hero_uruk":
        # Uruk valoriza criaturas grandes e com keywords de combate
        if card.base_off + card.base_vit >= 6:
            return 1.0
        if any(kw in card.keywords for kw in ("Atropelar", "Indomavel", "Veloz")):
            return 0.8

    if hid == "hero_lider_revolucionario":
        # Lider valoriza criaturas de baixo custo para inundar o campo
        if card.cost <= 2:
            return 1.2
        if card.cost <= 3 and owner.field_size() >= 3:
            return 0.8

    if hid == "hero_campeao_natureza":
        # Campeão valoriza criaturas com markers ou que ganham counters
        if "+1/+1" in card.effect or "marcador" in card.effect.lower():
            return 1.5

    return 0.0


def _hero_spell_bonus(card: "CardInst", owner: "Player") -> float:
    """Bônus de score para feitiços baseado na sinergia com o herói."""
    hid = owner.hero.id

    if hid == "hero_quarion":
        # Quarion se beneficia de feitiços para copiar — qualquer feitiço tem valor extra
        return 1.5

    if hid == "hero_ngoro":
        if "investig" in card.effect.lower():
            return 2.0
        # Ngoro aprecia compra de cartas para acumular pistas
        for tag in card.effect_tags:
            if tag.get("action") in ("draw", "search"):
                return 1.2

    if hid == "hero_tifon":
        # Tifon não tem sinergia natural com feitiços genéricos
        # mas valoriza feitiços que matam criaturas (triggam Suspiro dos aliados)
        for tag in card.effect_tags:
            if tag.get("action") in ("destroy", "deal_damage"):
                if tag.get("target", "") and "enemy" in tag.get("target", ""):
                    return 1.0
        return -0.2

    if hid == "hero_rasmus":
        # Rasmus valoriza feitiços de café (geram reserva)
        if "cafe" in card.name.lower():
            return 2.0

    if hid == "hero_campeao_natureza":
        # Feitiços que dão buff a criaturas são o core do Campeão
        for tag in card.effect_tags:
            if tag.get("action") == "buff":
                return 2.0

    if hid == "hero_lider_revolucionario":
        # Feitiços que compram cartas para manter o ritmo de recrutas
        for tag in card.effect_tags:
            if tag.get("action") in ("draw", "search"):
                return 1.0

    return 0.0


def _hero_permanent_bonus(card: "CardInst", owner: "Player") -> float:
    """Bônus de score para encantos, terrenos e artefatos baseado no herói."""
    hid = owner.hero.id

    if hid == "hero_ngoro":
        # Base de Investigação e similares são centrais para o Ngoro
        if "investig" in card.name.lower() or "investig" in card.effect.lower():
            return 2.5

    if hid == "hero_gimble":
        # Artefatos e encantos que buffam dragões
        if "dragao" in card.effect.lower() or "dragon" in card.effect.lower():
            return 2.0

    if hid == "hero_colecionador":
        # Colecionador se beneficia de qualquer permanente que gere card advantage
        for tag in card.effect_tags:
            if tag.get("action") in ("draw", "search"):
                return 1.5

    if hid == "hero_campeao_natureza":
        # Terrenos e encantos que colocam marcadores
        if "marcador" in card.effect.lower() or "+1/+1" in card.effect:
            return 2.0

    if hid == "hero_rasmus":
        # Artefatos e encantos de café
        if "cafe" in card.name.lower():
            return 2.5

    if hid == "hero_uruk":
        # Artefatos de combate têm valor extra para Uruk
        if card.card_type == "artifact":
            for tag in card.effect_tags:
                if tag.get("action") in ("buff", "deal_damage"):
                    return 1.2

    return 0.0


# ─────────────────────────────────────────────────────────
#  DECISÃO DE MANUTENÇÃO
# ─────────────────────────────────────────────────────────

def _choose_maintenance_action(player: "Player", opp: "Player") -> str:
    if player.max_energy == 0:
        return "energy"
    if player.max_energy >= MAX_ENERGY:
        return "draw"

    next_energy = player.max_energy + 1
    hand_size   = len(player.hand)

    has_key_card = any(
        c.cost == next_energy
        for c in player.hand
        if "Acelerado" not in c.keywords
    )

    if hand_size <= 2 and player.max_energy >= 4:
        return "draw"

    if player.field_size() == 0 and hand_size <= 3 and player.max_energy >= 5:
        return "draw"

    if player.max_energy < 7:
        return "energy"

    return "energy" if has_key_card else "draw"


# ─────────────────────────────────────────────────────────
#  HELPER DEFENSOR X
# ─────────────────────────────────────────────────────────

def _get_defensor_x(card: "CardInst") -> int:
    for kw in card.keywords:
        if kw == "Defensor" or kw.startswith("Defensor "):
            parts = kw.split()
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[1])
            return 1
    return 0


# ─────────────────────────────────────────────────────────
#  DECISÃO DE JOGAR NA FASE PRINCIPAL
# ─────────────────────────────────────────────────────────

def choose_card_to_play(player: "Player", opp: "Player",
                        turn: int,
                        excluded_iids: set[int] | None = None,
                        played_this_turn: list | None = None) -> Optional["CardInst"]:
    excluded_iids    = excluded_iids or set()
    played_this_turn = played_this_turn or []
    profile = get_opponent_profile(opp)
    cost_red = getattr(player, "_cost_reduction_next", 0)
    playable = []

    for card in player.hand:
        if card.iid in excluded_iids:
            continue
        cost = max(0, card.cost - cost_red)
        avail = player.total_energy() if card.card_type == "spell" else player.energy
        if cost > avail:
            continue
        if "Acelerado" in card.keywords:
            continue
        if card.card_type == "creature" and player.field_size() >= 5:
            continue
        if card.card_type == "artifact":
            has_slot = any(
                player.creature_at(i) is not None and player.support_at(i) is None
                for i in range(5)
            )
            if not has_slot:
                continue

        score = hand_card_score(card, player, opp, turn, profile, played_this_turn)
        playable.append((score, card))

    if not playable:
        return None

    best_score, best_card = max(playable,
                                key=lambda x: (x[0], -_play_order_priority(x[1], player)))
    if best_score < -0.5:
        return None
    return best_card


def choose_artifact_slot(player: "Player") -> Optional[int]:
    slots = [
        i for i in range(5)
        if player.creature_at(i) is not None and player.support_at(i) is None
    ]
    if not slots:
        return None
    return max(slots, key=lambda i: card_value(player.creature_at(i), player))


def _play_order_priority(card: "CardInst", player: "Player") -> int:
    """
    Retorna prioridade de jogo (menor = jogar primeiro).
    Garante sequenciamento correto: terrenos → encantos → feitiços de remoção
    → feitiços de buff → criaturas normais → criaturas com Investida → artefatos.
    """
    if card.card_type == "terrain":
        return 0
    if card.card_type == "enchant":
        return 1
    if card.card_type == "spell":
        for tag in card.effect_tags:
            action = tag.get("action", "")
            if action == "buff":
                return 3
        return 2
    if card.card_type == "creature":
        if card.has_kw("Investida"):
            return 5
        return 4
    if card.card_type == "artifact":
        return 6
    return 4


# ─────────────────────────────────────────────────────────
#  DECISÃO DE ATAQUE
# ─────────────────────────────────────────────────────────

def _attacker_priority(atk: "CardInst", opp: "Player") -> float:
    score = 0.0
    if atk.has_kw("Furtivo"):
        score += 5.0
    if atk.has_kw("Atropelar"):
        score += 2.5
    if atk.has_kw("Voar") and not any(b.has_kw("Voar") for b in opp.field_creatures):
        score += 3.0
    if atk.cur_vit() <= 1:
        score += 2.0
    if atk.has_kw("Indomavel"):
        score += 1.5
    if atk.has_kw("Roubo de Vida"):
        score += 1.5
    score -= atk.cost * 0.1
    return score


def can_deal_lethal(player: "Player", opp: "Player") -> bool:
    """Retorna True se atacar com todas as criaturas disponíveis pode matar o oponente."""
    can_attack = [c for c in player.field_creatures if c.can_attack()]
    if not can_attack:
        return False

    guaranteed_dmg = sum(c.cur_off() for c in can_attack if c.has_kw("Furtivo"))
    non_furtivo = [c for c in can_attack if not c.has_kw("Furtivo")]

    if not non_furtivo:
        return guaranteed_dmg >= opp.life

    opp_blockers = [b for b in opp.field_creatures if b.cur_vit() > 0]
    used_blockers: set[int] = set()

    for atk in sorted(non_furtivo, key=lambda c: c.cur_off(), reverse=True):
        if atk.has_kw("Voar"):
            valid = [b for b in opp_blockers
                     if b.iid not in used_blockers and b.has_kw("Voar")]
        else:
            valid = [b for b in opp_blockers if b.iid not in used_blockers]

        if not valid:
            guaranteed_dmg += atk.cur_off()
            continue

        def blocker_score(b, a=atk):
            outcome = _combat_outcome(a, b)
            s = 0.0
            if not outcome["blk_dies"]:
                s += 10.0
            if outcome["atk_dies"]:
                s += 5.0
            return s

        best_blk = max(valid, key=blocker_score)
        used_blockers.add(best_blk.iid)
        outcome = _combat_outcome(atk, best_blk)
        guaranteed_dmg += outcome.get("excess", 0)

    return guaranteed_dmg >= opp.life


def _expected_attack_value(attacker: "CardInst", opp: "Player",
                            player: "Player") -> float:
    """Estima o valor líquido de enviar este atacante. Positivo = bom atacar."""
    if attacker.has_kw("Furtivo") or not opp.field_creatures:
        return attacker.cur_off() * AI_LIFE_VALUE + 0.3

    if attacker.has_kw("Voar"):
        if not any(b.has_kw("Voar") for b in opp.field_creatures):
            return attacker.cur_off() * AI_LIFE_VALUE + 0.3

    valid_blockers = [b for b in opp.field_creatures
                      if not attacker.has_kw("Voar") or b.has_kw("Voar")]

    if not valid_blockers:
        return attacker.cur_off() * AI_LIFE_VALUE + 0.2

    worst_net = float('inf')
    worst_outcome = None
    for blk in valid_blockers:
        outcome = _combat_outcome(attacker, blk)
        net = 0.0
        if outcome["atk_dies"]:
            net -= card_value(attacker, player) * 1.5
        if outcome["blk_dies"]:
            net += card_value(blk, opp) * 1.2
        net += outcome.get("excess", 0) * AI_LIFE_VALUE
        if net < worst_net:
            worst_net = net
            worst_outcome = outcome

    if worst_outcome and not worst_outcome["atk_dies"]:
        worst_net += attacker.cur_off() * AI_LIFE_VALUE * 0.25

    return worst_net


def choose_attackers(player: "Player", opp: "Player") -> list["CardInst"]:
    profile = get_opponent_profile(opp)
    can_attack = [c for c in player.field_creatures if c.can_attack()]
    if not can_attack:
        return []

    if can_deal_lethal(player, opp):
        return can_attack

    chosen = []
    defenders_needed = _how_many_defenders_needed(player, opp, profile)
    ranked = sorted(can_attack, key=lambda c: _attacker_priority(c, opp), reverse=True)

    possible_defenders = [c for c in ranked
                          if not c.has_kw("Furtivo") and not c.has_kw("Indomavel")]
    possible_defenders.sort(key=lambda c: c.cur_vit(), reverse=True)

    reserved = set()
    if defenders_needed > 0:
        for c in possible_defenders[:defenders_needed]:
            reserved.add(c.iid)

    for c in ranked:
        if c.iid in reserved:
            continue
        if c.has_kw("Indomavel"):
            chosen.append(c)
            continue

        priority = _attacker_priority(c, opp)
        expected = _expected_attack_value(c, opp, player)

        if priority >= 3.0 or expected > -0.2:
            chosen.append(c)

    if not chosen and can_attack:
        best = max(can_attack,
                   key=lambda c: (_expected_attack_value(c, opp, player), c.cur_off()))
        if best.cur_off() > 0 and _expected_attack_value(best, opp, player) > -1.0:
            chosen.append(best)

    return chosen


def _how_many_defenders_needed(player: "Player", opp: "Player",
                               profile: OpponentProfile | None = None) -> int:
    profile = profile or get_opponent_profile(opp)
    opp_potential = [c for c in opp.field_creatures
                     if (not c.tapped or c.has_kw("Alerta"))
                     and (not c.sick or c.has_kw("Investida"))]
    if not opp_potential:
        return 0

    player_has_flyers = any(c.has_kw("Voar") for c in player.field_creatures)

    unblockable_dmg = sum(c.cur_off() for c in opp_potential
                          if c.has_kw("Furtivo"))
    if not player_has_flyers:
        unblockable_dmg += sum(c.cur_off() for c in opp_potential
                               if c.has_kw("Voar") and not c.has_kw("Furtivo"))

    blockable = [c for c in opp_potential
                 if not c.has_kw("Furtivo")
                 and (not c.has_kw("Voar") or player_has_flyers)]
    total_blockable_dmg = sum(c.cur_off() for c in blockable)
    total_dmg = unblockable_dmg + total_blockable_dmg

    safety_margin = 6 if profile.aggro_risk <= profile.control_risk else 9

    if player.life - unblockable_dmg <= 3:
        return 0

    if player.life > total_dmg + safety_margin:
        return 0

    dangerous = sorted(blockable, key=lambda c: c.cur_off(), reverse=True)
    reserve = 3 if profile.aggro_risk > profile.control_risk else 2
    return min(len(dangerous), reserve)


# ─────────────────────────────────────────────────────────
#  DECISÃO DE BLOQUEIO
# ─────────────────────────────────────────────────────────

def _combat_outcome(atk: "CardInst", blk: "CardInst") -> dict:
    a_dmg = atk.cur_off()
    b_dmg = blk.cur_off()

    if blk.has_kw("Robusto"):
        a_dmg = max(0, a_dmg - 1)
    if atk.has_kw("Robusto"):
        b_dmg = max(0, b_dmg - 1)

    if atk.has_kw("Veloz") and not blk.has_kw("Veloz"):
        blk_dies = blk.cur_vit() - a_dmg <= 0
        atk_dies = False if blk_dies else (atk.cur_vit() - b_dmg <= 0)
    else:
        atk_dies = atk.cur_vit() - b_dmg <= 0
        blk_dies = blk.cur_vit() - a_dmg <= 0

    if atk.has_kw("Toque da Morte") and a_dmg > 0:
        blk_dies = True
    if blk.has_kw("Toque da Morte") and b_dmg > 0:
        atk_dies = True
    if blk.has_kw("Indestrutivel"):
        blk_dies = False
    if atk.has_kw("Indestrutivel"):
        atk_dies = False

    excess = 0
    if blk_dies and atk.has_kw("Atropelar"):
        excess = max(0, a_dmg - blk.cur_vit())

    return {"atk_dies": atk_dies, "blk_dies": blk_dies, "excess": excess}


def _block_trade_score(atk: "CardInst", blk: "CardInst",
                       owner: "Player", opp: "Player",
                       profile: OpponentProfile | None = None) -> float:
    profile = profile or get_opponent_profile(opp)
    outcome  = _combat_outcome(atk, blk)
    score    = 0.0
    atk_val  = card_value(atk, opp)
    blk_val  = card_value(blk, owner)

    if outcome["blk_dies"] and not outcome["atk_dies"]:
        score -= blk_val * 2.0
        direct_dmg = atk.cur_off() + outcome["excess"]
        if owner.life - direct_dmg <= 0:
            score += 50.0
    elif not outcome["blk_dies"] and outcome["atk_dies"]:
        score += atk_val * 2.0
    elif outcome["blk_dies"] and outcome["atk_dies"]:
        score += (atk_val - blk_val) * 1.2
        if atk_val > blk_val * 1.1:
            score += 1.0
    else:
        dmg_prevented = atk.cur_off()
        life_weight = 0.7 + (0.25 if profile.aggro_risk > profile.control_risk else 0.0)
        score += dmg_prevented * AI_LIFE_VALUE * life_weight
        score -= blk_val * 0.3

    if owner.life <= 8:
        score += 3.0
    elif owner.life >= 20:
        score -= 1.0

    return score


def choose_blockers(attackers: list["CardInst"],
                    defender: "Player",
                    attacker_player: "Player") -> dict[int, list["CardInst"]]:
    profile = get_opponent_profile(attacker_player)
    blocks: dict[int, list] = {}

    for atk in attackers:
        if atk.has_kw("Furtivo"):
            blocks[atk.iid] = []

    block_slots: dict[int, int] = {}
    for c in defender.field_creatures:
        if c.can_block():
            dx = _get_defensor_x(c)
            block_slots[c.iid] = dx if dx > 0 else 1

    def avail_blockers(atk):
        return [
            c for c in defender.field_creatures
            if c.can_block()
            and block_slots.get(c.iid, 0) > 0
            and (not atk.has_kw("Voar") or c.has_kw("Voar"))
        ]

    need_block = [a for a in attackers if a.iid not in blocks]
    need_block.sort(key=lambda a: _attacker_threat(a, defender), reverse=True)

    for atk in need_block:
        candidates = avail_blockers(atk)
        if not candidates:
            blocks[atk.iid] = []
            continue

        scored = [(c, _block_trade_score(atk, c, defender, attacker_player, profile))
                  for c in candidates]
        best_blocker, best_score = max(scored, key=lambda x: x[1])

        if best_score > 0.5:
            blocks[atk.iid] = [best_blocker]
            block_slots[best_blocker.iid] -= 1
        else:
            total_unblocked = sum(
                a.cur_off() for a in need_block
                if a.iid not in blocks or not blocks.get(a.iid)
            )
            if defender.life - total_unblocked <= 0:
                emerg = max(candidates,
                            key=lambda c: _block_trade_score(
                                atk, c, defender, attacker_player, profile))
                blocks[atk.iid] = [emerg]
                block_slots[emerg.iid] -= 1
            else:
                blocks[atk.iid] = []

    return blocks


def _attacker_threat(atk: "CardInst", defender: "Player") -> float:
    dmg = atk.cur_off()
    if atk.has_kw("Atropelar"):
        dmg *= 1.3
    if atk.has_kw("Toque da Morte"):
        dmg += 3.0
    if atk.has_kw("Furtivo"):
        return 0.0
    return dmg


# ─────────────────────────────────────────────────────────
#  DECISÃO DE FEITIÇO ACELERADO
# ─────────────────────────────────────────────────────────

def choose_accelerated_response(responder: "Player",
                                attacker_p: "Player",
                                context: str = "combat") -> Optional["CardInst"]:
    accels = [c for c in responder.hand
              if c.card_type == "spell"
              and "Acelerado" in c.keywords
              and c.cost <= responder.total_energy()]
    if not accels:
        return None

    scored = [(s, sp) for sp in accels
              if (s := _accel_score(sp, responder, attacker_p, context)) > 1.0]
    if not scored:
        return None
    return max(scored, key=lambda x: x[0])[1]


def _accel_score(spell: "CardInst", owner: "Player",
                 opp: "Player", context: str) -> float:
    score = 0.0
    for tag in spell.effect_tags:
        action = tag.get("action", "")
        target = tag.get("target", "")

        if action == "deal_damage":
            val = _resolve_value(tag.get("value", 1), owner)
            if "enemy_hero" in target or "any" in target:
                if context == "combat" and opp.field_creatures:
                    min_vit = min(c.cur_vit() for c in opp.field_creatures)
                    score += val * (2.5 if val >= min_vit else 1.0)
                else:
                    score += val * 1.0
            if "all_enemy" in target:
                score += val * len(opp.field_creatures) * 0.8

        elif action == "destroy":
            filt = tag.get("filter", "")
            if opp.field_creatures:
                if "tapped" in filt and context == "combat":
                    tapped_val = [card_value(c, opp) for c in opp.field_creatures if c.tapped]
                    if tapped_val:
                        score += max(tapped_val) * 1.5
                else:
                    score += max(card_value(c, opp) for c in opp.field_creatures) * 1.0

        elif action == "buff":
            if owner.field_creatures and context == "combat":
                score += 2.0

        elif action == "return_hand":
            if opp.field_creatures:
                score += max(card_value(c, opp) for c in opp.field_creatures) * 0.7

        elif action == "apply_status":
            status = tag.get("status", "")
            if status in ("Congelado", "Atordoado") and opp.field_creatures:
                score += 3.0 if context == "combat" else 1.5

        elif action == "heal":
            val = _resolve_value(tag.get("value", 2), owner)
            urgency = max(0.0, (12 - owner.life) / 12)
            score += val * urgency * 1.2

        elif action == "counter":
            score += 2.5

        elif action == "negate_next_damage":
            if context == "combat":
                score += 2.0

        elif action == "draw":
            score += _resolve_value(tag.get("value", 1), owner) * 0.8

    score -= spell.cost * 0.4
    return score


# ─────────────────────────────────────────────────────────
#  AVALIAÇÃO DE ESTADO (look-ahead)
# ─────────────────────────────────────────────────────────

def evaluate_state(player: "Player", opp: "Player") -> float:
    ally_field = sum(card_value(c, player) for c in player.field_creatures)
    opp_field  = sum(card_value(c, opp)    for c in opp.field_creatures)
    life_adv   = (player.life - opp.life) * AI_LIFE_VALUE
    hand_adv   = (len(player.hand) - len(opp.hand)) * 0.5
    energy_adv = (player.total_energy() - opp.total_energy()) * 0.3
    level_adv  = (player.hero_level - opp.hero_level) * 2.0
    levelup_adv = player.levelup_counter * 0.08 - opp.levelup_counter * 0.08

    deck_adv = 0.0
    if len(opp.deck) < 5:
        deck_adv += (5 - len(opp.deck)) * 1.5
    if len(player.deck) < 5:
        deck_adv -= (5 - len(player.deck)) * 1.5

    perm_adv = (len(player.spells_field) - len(opp.spells_field)) * 0.8
    pistas_adv = (player.pistas - opp.pistas) * 0.3

    return ((ally_field - opp_field) + life_adv + hand_adv +
            energy_adv + level_adv + levelup_adv + deck_adv +
            perm_adv + pistas_adv)


def should_play_card_now(card: "CardInst", player: "Player",
                         opp: "Player", turn: int) -> bool:
    profile = get_opponent_profile(opp)
    if card.has_kw("Investida") and opp.field_creatures:
        return True
    if player.life <= 8:
        return True
    if profile.aggro_risk > profile.control_risk and card.card_type in ("creature", "spell"):
        return True
    if card.card_type in ("enchant", "terrain") and not player.field_creatures:
        return False
    if card.cost >= 6:
        return True
    score_now    = hand_card_score(card, player, opp, turn, profile)
    score_future = hand_card_score(card, player, opp, turn + 1, profile) * 0.9
    return score_now >= score_future * 0.85