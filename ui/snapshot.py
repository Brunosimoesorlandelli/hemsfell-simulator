"""
Hemsfell Heroes — Snapshot
============================
Captura imutável do estado do jogo em um determinado instante.
Usado pelo visualizador para navegar pela partida passo a passo.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.models import CardInst, Player
    from engine.simulator import GameState


class Snapshot:
    __slots__ = [
        "turn", "active_player", "phase", "phase_color",
        "p1", "p2",
        "log_lines",
        "attackers", "blockers",
        "highlight_iids",
        "event",
    ]

    # Mapeamento fase → cor RGB
    PHASE_COLORS = {
        "Manutenção": (80,  160, 220),
        "Principal":  (60,  210, 100),
        "Combate":    (220, 100,  40),
        "Fim":        (180, 100, 220),
        "Vitória":    (255, 220,  60),
    }

    def __init__(
        self,
        gs: "GameState",
        active: "Player",
        phase: str,
        log_lines: list[str],
        event: str = "",
        attackers=None,
        blockers=None,
        highlights=None,
    ):
        self.turn           = gs.turn
        self.active_player  = 0 if active is gs.players[0] else 1
        self.phase          = phase
        self.phase_color    = self.PHASE_COLORS.get(phase, (170, 170, 170))
        self.log_lines      = list(log_lines[-12:])
        self.event          = event
        self.attackers      = set(attackers or [])
        self.blockers       = set(blockers  or [])
        self.highlight_iids = set(highlights or [])
        self.p1             = self._snap_player(gs.players[0])
        self.p2             = self._snap_player(gs.players[1])

    def _snap_player(self, p: "Player") -> dict:
        return {
            "name":       p.name,
            "hero_name":  p.hero.name,
            "hero_level": p.hero_level,
            "life":       p.life,
            "energy":     p.energy,
            "max_energy": p.max_energy,
            "reserve":    p.reserve,
            "hand_count": len(p.hand),
            "deck_count": len(p.deck),
            "gy_count":   len(p.graveyard),
            "field":      [self._snap_card(c) for c in p.field_creatures],
            "support":    [self._snap_card(p.support_at(i)) for i in range(5)],
            "hand":       [self._snap_card(c) for c in p.hand],
        }

    def _snap_card(self, c) -> dict | None:
        if c is None:
            return None
        return {
            "iid":      c.iid,
            "name":     c.name,
            "off":      c.cur_off(),
            "vit":      c.cur_vit(),
            "base_off": c.base_off,
            "base_vit": c.base_vit,
            "cost":     c.cost,
            "keywords": list(c.keywords),
            "status":   list(c.status),
            "tapped":   c.tapped,
            "sick":     c.sick,
            "slot":     c.slot,
            "race":     c.race,
            "type":     c.card_type,
            "markers":  dict(c.markers),
        }
