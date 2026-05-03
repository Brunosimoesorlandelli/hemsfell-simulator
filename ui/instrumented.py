"""
Hemsfell Heroes — GameState Instrumentado
===========================================
Subclasse de GameState que injeta hooks em cada fase para
capturar Snapshots e alimentar o visualizador.
"""

from __future__ import annotations
import random
import sys, os

# Garante que o pacote raiz está no path ao rodar diretamente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.simulator import GameState
from engine.models import Player, CardInst
from engine import logger
from .snapshot import Snapshot


class InstrumentedGameState(GameState):
    """GameState com hooks para capturar snapshots a cada fase/evento."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshots: list[Snapshot] = []
        self._cur_phase   = "Manutenção"
        self._cur_active: Player = self.players[0]
        self._attackers_iids: list[int] = []
        self._blockers_iids:  list[int] = []

    def _snap(self, phase: str, event: str = "", highlights=None):
        s = Snapshot(
            self,
            self._cur_active,
            phase,
            logger.get_lines(),
            event=event,
            attackers=self._attackers_iids,
            blockers=self._blockers_iids,
            highlights=highlights,
        )
        self.snapshots.append(s)

    # ── Override das fases ────────────────────────────────────────────────
    def phase_maintenance(self, player: Player, first_turn: bool):
        self._cur_active = player
        self._cur_phase  = "Manutenção"
        super().phase_maintenance(player, first_turn)
        self._snap("Manutenção", f"Manutenção — {player.hero.name}")

    def phase_main(self, player: Player):
        self._cur_active = player
        self._cur_phase  = "Principal"
        self._snap("Principal", f"Início principal — {player.hero.name}")

        # Hook: captura snapshot a cada criatura invocada
        _orig_place = player.place_creature
        snap_ref    = self

        def _place_and_snap(card, prefer_slot=-1):
            result = _orig_place(card, prefer_slot)
            snap_ref._snap("Principal",
                           f"{player.hero.name} invoca {card.name}",
                           highlights=[card.iid])
            return result

        player.place_creature = _place_and_snap
        super().phase_main(player)
        player.place_creature = _orig_place

        self._snap("Principal", f"Fim principal — {player.hero.name}")

    def phase_combat(self, player: Player):
        self._cur_active      = player
        self._cur_phase       = "Combate"
        self._attackers_iids  = []
        self._blockers_iids   = []
        self._snap("Combate", f"Início combate — {player.hero.name}")
        super().phase_combat(player)
        self._snap("Combate", "Combate concluído")
        self._attackers_iids  = []
        self._blockers_iids   = []

    def phase_end(self, player: Player):
        self._cur_active = player
        self._cur_phase  = "Fim"
        super().phase_end(player)
        self._snap("Fim", f"Fim de turno — {player.hero.name}")

    # ── Override do combate ───────────────────────────────────────────────
    def _resolve_creature_combat(self, atk: CardInst, blk: CardInst,
                                  atk_owner: Player, blk_owner: Player):
        self._attackers_iids = [atk.iid]
        self._blockers_iids  = [blk.iid]
        self._snap(
            "Combate",
            f"{atk.name} ({atk.cur_off()}/{atk.cur_vit()}) vs "
            f"{blk.name} ({blk.cur_off()}/{blk.cur_vit()})",
            highlights=[atk.iid, blk.iid],
        )
        super()._resolve_creature_combat(atk, blk, atk_owner, blk_owner)
        self._snap("Combate", "Resultado do confronto",
                   highlights=[atk.iid, blk.iid])

    def destroy_creature(self, card: CardInst, owner: Player):
        self._snap("Combate", f"{card.name} é destruída!", highlights=[card.iid])
        super().destroy_creature(card, owner)

    def run(self) -> dict:
        result = super().run()
        winner = self.winner
        if winner:
            self._snap("Vitória",
                       f"🏆 {winner.hero.name} VENCE! ({self.turn} turnos)")
        else:
            self._snap("Vitória", "Empate!")
        return result


# ── Função auxiliar ───────────────────────────────────────────────────────

def run_instrumented(
    deck1_hero: str,
    deck2_hero: str,
    data: dict,
    card_pool: dict,
    tags_db: dict,
) -> list[Snapshot]:
    """
    Executa uma partida instrumentada e devolve os snapshots para o viewer.
    """
    from engine.loader import build_deck_for_hero
    from engine import logger as _logger

    _logger.clear()

    h1, d1 = build_deck_for_hero(deck1_hero, data, card_pool, tags_db)
    h2, d2 = build_deck_for_hero(deck2_hero, data, card_pool, tags_db)
    random.shuffle(d1)
    random.shuffle(d2)

    p1 = Player(name=f"J1 — {h1.name}", hero=h1, deck=d1)
    p2 = Player(name=f"J2 — {h2.name}", hero=h2, deck=d2)

    gs = InstrumentedGameState(p1, p2, card_pool, tags_db)
    gs.run()
    return gs.snapshots
