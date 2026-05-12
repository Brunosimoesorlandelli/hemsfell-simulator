"""
Hemsfell Heroes — Modelos de dados
====================================
CardInst  : instância de uma carta em jogo
Player    : estado completo de um jogador
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .config import (
    MAX_HAND, MAX_CREATURES, MAX_ENERGY, MAX_RESERVE, STARTING_LIFE
)

# ─────────────────────────────────────────────
#  GERADOR DE IID
# ─────────────────────────────────────────────
_iid = 0

def new_iid() -> int:
    global _iid
    _iid += 1
    return _iid

def reset_iid():
    global _iid
    _iid = 0


# ─────────────────────────────────────────────
#  CARD INSTANCE
# ─────────────────────────────────────────────
@dataclass
class CardInst:
    id: str
    name: str
    card_type: str          # creature / spell / artifact / enchant / terrain / image
    color: str
    cost: int = 0
    offense: int = 0
    vitality: int = 0
    base_off: int = 0
    base_vit: int = 0
    keywords: list = field(default_factory=list)
    effect: str = ""
    effect_tags: list = field(default_factory=list)
    race: str = ""
    abilities: dict = field(default_factory=dict)
    subtype: str = ""

    # estado em jogo
    iid: int = field(default_factory=new_iid)
    tapped: bool = False
    sick: bool = True       # summoning sickness
    temp_off: int = 0
    temp_vit: int = 0
    status: list = field(default_factory=list)   # Congelado, Atordoado, Sufocado, Imobilizado
    markers: dict = field(default_factory=dict)  # {tipo: qtd}
    linked_to: int = 0
    banned_until_leave: int = 0
    no_untap_next: bool = False
    slot: Optional[int] = None

    def cur_off(self) -> int:
        if "Congelado" in self.status or "Sufocado" in self.status:
            return 0
        return max(0, self.offense + self.temp_off)

    def cur_vit(self) -> int:
        return max(0, self.vitality + self.temp_vit)

    def has_kw(self, kw: str) -> bool:
        if "Sufocado" in self.status:
            return False
        return kw in self.keywords

    def can_attack(self) -> bool:
        if self.sick and not self.has_kw("Investida"):
            return False
        if self.tapped:
            return False
        if "Atordoado" in self.status:
            return False
        return True

    def can_block(self) -> bool:
        return not self.tapped and "Atordoado" not in self.status

    def marker_count(self, typ: str = "+1/+1") -> int:
        return self.markers.get(typ, 0)

    def add_marker(self, typ: str, n: int = 1):
        self.markers[typ] = self.markers.get(typ, 0) + n
        if typ == "+1/+1":
            self.offense  += n
            self.vitality += n
            self.base_off += n
            self.base_vit += n

    def __str__(self):
        kw = f" ({','.join(self.keywords)})" if self.keywords else ""
        st = f" [{','.join(self.status)}]" if self.status else ""
        tp = " [V]" if self.tapped else ""
        sk = " [en]" if self.sick else ""
        return f"{self.name} {self.cur_off()}/{self.cur_vit()}{kw}{st}{tp}{sk}"


# ─────────────────────────────────────────────
#  PLAYER
# ─────────────────────────────────────────────
@dataclass
class Player:
    name: str
    hero: CardInst
    deck: list
    hand: list = field(default_factory=list)
    _slots: list = field(default_factory=lambda: [None] * MAX_CREATURES)
    _support_slots: list = field(default_factory=lambda: [None] * MAX_CREATURES)
    spells_field: list = field(default_factory=list)
    graveyard: list = field(default_factory=list)
    obscure: list = field(default_factory=list)
    energy: int = 0
    max_energy: int = 0
    reserve: int = 0
    life: int = STARTING_LIFE
    hero_level: int = 1
    leveled_up_this_turn: bool = False
    levelup_counter: int = 0
    kills: int = 0
    pistas: int = 0

    # flags de turno
    spells_cast_this_turn: int = 0
    cards_played_this_turn: int = 0
    fura_fila_count: int = 0
    cafes_played: int = 0
    deaths_this_turn: int = 0
    life_lost_this_turn: int = 0
    life_lost_times_this_turn: int = 0
    extra_draws_this_turn: int = 0
    milled_this_turn: int = 0
    first_acts_triggered: int = 0

    # estatísticas acumuladas
    stats_cards_played: dict = field(default_factory=dict)
    stats_cards_drawn: dict = field(default_factory=dict)
    stats_damage_dealt: int = 0
    stats_life_gained: int = 0
    mana_spent_total: int = 0
    mana_budget_total: int = 0
    max_energy_reached: int = 0
    cards_played_total: int = 0
    spells_cast_total: int = 0
    creatures_played_total: int = 0
    combo_turns: int = 0
    interaction_plays: int = 0
    turns_played: int = 0
    life_min: int = STARTING_LIFE
    level3_reached: bool = False

    # ── Campo posicionado ─────────────────────────────────────────────────
    @property
    def field_creatures(self) -> list:
        return [c for c in self._slots if c is not None]

    def creature_at(self, slot: int) -> Optional[CardInst]:
        return self._slots[slot] if 0 <= slot < MAX_CREATURES else None

    def support_at(self, slot: int) -> Optional[CardInst]:
        return self._support_slots[slot] if 0 <= slot < MAX_CREATURES else None

    def slot_of(self, card: CardInst) -> int:
        for i, c in enumerate(self._slots):
            if c is card:
                return i
        return -1

    def adjacent_creatures(self, card: CardInst) -> list:
        idx = self.slot_of(card)
        res = []
        for di in (-1, 1):
            ni = idx + di
            if 0 <= ni < MAX_CREATURES and self._slots[ni] is not None:
                res.append(self._slots[ni])
        return res

    def place_creature(self, card: CardInst, prefer_slot: int = -1) -> int:
        if 0 <= prefer_slot < MAX_CREATURES and self._slots[prefer_slot] is None:
            self._slots[prefer_slot] = card
            card.slot = prefer_slot
            return prefer_slot
        for i in range(MAX_CREATURES):
            if self._slots[i] is None:
                self._slots[i] = card
                card.slot = i
                return i
        return -1

    def remove_creature(self, card: CardInst):
        for i in range(MAX_CREATURES):
            if self._slots[i] is card:
                self._slots[i] = None
                card.slot = None
                if self._support_slots[i] is not None:
                    sup = self._support_slots[i]
                    self._support_slots[i] = None
                    self.graveyard.append(sup)
                return

    def place_support(self, card: CardInst, slot: int) -> bool:
        if 0 <= slot < MAX_CREATURES and self._support_slots[slot] is None:
            self._support_slots[slot] = card
            card.slot = slot
            card.linked_to = self._slots[slot].iid if self._slots[slot] else 0
            return True
        return False

    def commander_slot(self) -> int:
        occupied = [i for i in range(MAX_CREATURES) if self._slots[i] is not None]
        if not occupied:
            return -1
        return occupied[len(occupied) // 2]

    def commander(self) -> Optional[CardInst]:
        idx = self.commander_slot()
        return self._slots[idx] if idx >= 0 else None

    def field_size(self) -> int:
        return sum(1 for c in self._slots if c is not None)

    def total_energy(self) -> int:
        return self.energy + self.reserve

    def spend(self, amt: int, allow_reserve: bool = True) -> bool:
        """
        Gasta energia. allow_reserve=False impede o uso de energia de reserva.
        Regra: reserva só pode ser usada para conjurar feitiços e efeitos de cartas,
        NÃO para invocar criaturas nem baixar permanentes (encantos/terrenos/artefatos).
        """
        original_amt = amt
        if allow_reserve:
            if self.total_energy() < amt:
                return False
            if self.energy >= amt:
                self.energy -= amt
            else:
                amt -= self.energy
                self.energy = 0
                self.reserve -= amt
        else:
            if self.energy < amt:
                return False
            self.energy -= amt
        self.mana_spent_total += original_amt
        return True

    def draw_card(self, n: int = 1) -> list:
        drawn = []
        for _ in range(n):
            if not self.deck:
                break
            c = self.deck.pop(0)
            self.hand.append(c)
            drawn.append(c)
            self.stats_cards_drawn[c.name] = self.stats_cards_drawn.get(c.name, 0) + 1
        return drawn

    def mill(self, n: int, label: str = ""):
        from .logger import log
        for _ in range(n):
            if not self.deck:
                break
            c = self.deck.pop(0)
            self.graveyard.append(c)
            self.milled_this_turn += 1
            log(f"💀 [{self.name}] tritura '{c.name}'{label}", 3)

    def heal(self, n: int):
        old = self.life
        self.life = min(STARTING_LIFE, self.life + n)
        self.stats_life_gained += self.life - old

    def take_damage(self, n: int, source: str = ""):
        self.life -= n
        self.life_min = min(self.life_min, self.life)

    def lose_life(self, n: int):
        self.life -= n
        self.life_lost_this_turn += n
        self.life_lost_times_this_turn += 1
        self.life_min = min(self.life_min, self.life)

    def hand_limit(self):
        from .logger import log
        while len(self.hand) > MAX_HAND:
            c = self.hand.pop()
            # Regra: excesso de mão é BANIDO (vai ao obscuro), não descartado
            self.obscure.append(c)
            log(f"🚫 [{self.name}] bane '{c.name}' (limite de mão → obscuro)", 2)

    def all_constants(self) -> list:
        return self.field_creatures + self.spells_field

    def reset_turn_flags(self):
        self.spells_cast_this_turn = 0
        self.cards_played_this_turn = 0
        self.fura_fila_count = 0
        self.cafes_played = 0
        self.deaths_this_turn = 0
        self.life_lost_this_turn = 0
        self.life_lost_times_this_turn = 0
        self.extra_draws_this_turn = 0
        self.milled_this_turn = 0
        self.first_acts_triggered = 0
        self.leveled_up_this_turn = False
        self._cost_reduction_next = 0   # reset desconto de custo entre turnos
        self.life_min = min(self.life_min, self.life)
