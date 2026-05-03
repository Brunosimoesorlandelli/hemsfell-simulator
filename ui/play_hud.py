"""
Modo jogavel com HUD visual (Pygame).

Fluxo:
- Fase principal: escolher cartas por botoes
- Combate humano: escolher atacantes
- Combate IA: escolher bloqueadores
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import pygame

from engine import ai_engine as AI
from engine import logger
from engine.config import MAX_CREATURES, MAX_TURNS
from engine.level_system import try_levelup_phase
from engine.loader import build_deck_for_hero
from engine.models import CardInst, Player, reset_iid
from engine.simulator import GameState
from .card_art import CardArtLibrary


class QuitRequested(Exception):
    pass


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    value: object
    color: tuple[int, int, int]


class PlayHUD:
    W = 1280
    H = 820

    BG = (15, 18, 28)
    PANEL = (27, 32, 48)
    PANEL_ALT = (35, 42, 62)
    BORDER = (95, 110, 150)
    TEXT = (236, 240, 255)
    SUBTEXT = (178, 190, 220)
    ACCENT = (80, 220, 160)
    WARN = (230, 180, 70)
    DANGER = (220, 90, 90)
    BTN = (55, 80, 130)
    BTN_ALT = (65, 120, 90)

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Hemsfell Heroes - Play HUD")
        self.screen = pygame.display.set_mode((self.W, self.H))
        self.clock = pygame.time.Clock()
        self.art = CardArtLibrary()
        self.font_title = pygame.font.SysFont("segoeui", 24, bold=True)
        self.font = pygame.font.SysFont("segoeui", 18)
        self.font_small = pygame.font.SysFont("segoeui", 15)
        self._buttons: list[Button] = []

    def close(self):
        pygame.quit()

    def _draw_text(self, text: str, x: int, y: int, color=None, small=False):
        f = self.font_small if small else self.font
        surf = f.render(text, True, color or self.TEXT)
        self.screen.blit(surf, (x, y))

    def _draw_panel(self, x: int, y: int, w: int, h: int, alt=False):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, self.PANEL_ALT if alt else self.PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, self.BORDER, rect, width=1, border_radius=8)

    def _draw_button(self, x: int, y: int, w: int, h: int, label: str, value, color=None):
        rect = pygame.Rect(x, y, w, h)
        c = color or self.BTN
        pygame.draw.rect(self.screen, c, rect, border_radius=8)
        pygame.draw.rect(self.screen, self.BORDER, rect, width=1, border_radius=8)
        txt = self.font.render(label, True, self.TEXT)
        txt_rect = txt.get_rect(center=rect.center)
        self.screen.blit(txt, txt_rect)
        self._buttons.append(Button(rect=rect, label=label, value=value, color=c))

    def _draw_board(self, gs: "HUDPlayableGameState", active: Player, phase: str, event: str):
        p_h = gs.human
        p_ai = gs.opponent(p_h)

        self.screen.fill(self.BG)

        pygame.draw.rect(self.screen, self.PANEL, (0, 0, self.W, 76))
        pygame.draw.line(self.screen, self.BORDER, (0, 76), (self.W, 76), 1)
        title = self.font_title.render(f"Turno {gs.turn} - {phase}", True, self.TEXT)
        self.screen.blit(title, (18, 18))
        self._draw_text(event, 18, 48, self.SUBTEXT, small=True)

        self._draw_panel(14, 90, 408, 300)
        self._draw_text("Voce", 24, 102, self.ACCENT)
        self._draw_text(
            f"{p_h.hero.name} | Vida {p_h.life} | Energia {p_h.energy}/{p_h.max_energy} +{p_h.reserve}R",
            24,
            130,
            self.TEXT,
            small=True,
        )
        self._draw_text(f"Mao {len(p_h.hand)}  Deck {len(p_h.deck)}  Cemiterio {len(p_h.graveyard)}", 24, 154, self.SUBTEXT, small=True)
        self._draw_slots(p_h, 24, 182)
        self._draw_hand_preview(p_h, 24, 284, limit=5)

        self._draw_panel(14, 404, 408, 300, alt=True)
        self._draw_text("IA", 24, 416, self.DANGER)
        self._draw_text(
            f"{p_ai.hero.name} | Vida {p_ai.life} | Energia {p_ai.energy}/{p_ai.max_energy} +{p_ai.reserve}R",
            24,
            444,
            self.TEXT,
            small=True,
        )
        self._draw_text(f"Mao {len(p_ai.hand)}  Deck {len(p_ai.deck)}  Cemiterio {len(p_ai.graveyard)}", 24, 468, self.SUBTEXT, small=True)
        self._draw_slots(p_ai, 24, 496)
        self._draw_hand_preview(p_ai, 24, 598, limit=5)

        self._draw_panel(438, 90, 828, 614)
        self._draw_text("Log recente", 452, 102, self.WARN)
        logs = logger.get_lines()[-22:]
        y = 130
        for line in logs:
            self._draw_text(line[:118], 452, y, self.SUBTEXT, small=True)
            y += 24

    def _draw_slots(self, p: Player, x: int, y: int):
        for i in range(MAX_CREATURES):
            rect = pygame.Rect(x + i * 76, y, 72, 92)
            c = p.creature_at(i)
            pygame.draw.rect(self.screen, (23, 26, 40), rect, border_radius=6)
            pygame.draw.rect(self.screen, self.BORDER, rect, width=1, border_radius=6)
            if c is None:
                self._draw_text(f"[{i}] vazio", rect.x + 6, rect.y + 36, self.SUBTEXT, small=True)
            else:
                self._draw_text(f"[{i}]", rect.x + 4, rect.y + 4, self.SUBTEXT, small=True)
                img = self.art.get_scaled_surface(c.name, (64, 36))
                if img is not None:
                    self.screen.blit(img, (rect.x + 4, rect.y + 20))
                else:
                    self._draw_text(c.name[:11], rect.x + 4, rect.y + 24, self.TEXT, small=True)
                self._draw_text(f"{c.cur_off()}/{c.cur_vit()}", rect.x + 4, rect.y + 58, self.ACCENT, small=True)
                flags = []
                if c.tapped:
                    flags.append("T")
                if c.sick:
                    flags.append("S")
                if flags:
                    self._draw_text(" ".join(flags), rect.x + 40, rect.y + 58, self.WARN, small=True)

    def _draw_hand_preview(self, p: Player, x: int, y: int, limit: int = 5):
        hand = p.hand[:limit]
        for i, c in enumerate(hand):
            rect = pygame.Rect(x + i * 76, y, 72, 66)
            pygame.draw.rect(self.screen, (23, 26, 40), rect, border_radius=6)
            pygame.draw.rect(self.screen, self.BORDER, rect, width=1, border_radius=6)
            img = self.art.get_scaled_surface(c.name, (64, 42))
            if img is not None:
                self.screen.blit(img, (rect.x + 4, rect.y + 4))
            else:
                self._draw_text(c.name[:10], rect.x + 4, rect.y + 16, self.SUBTEXT, small=True)
            self._draw_text(str(c.cost), rect.x + 58, rect.y + 48, self.WARN, small=True)

    def choose_option(
        self,
        gs: "HUDPlayableGameState",
        active: Player,
        phase: str,
        event: str,
        options: list[tuple[str, object, tuple[int, int, int]]],
    ):
        while True:
            self._buttons = []
            self._draw_board(gs, active, phase, event)

            y = 130
            for label, value, color in options[:18]:
                self._draw_button(850, y, 400, 40, label, value, color=color)
                y += 48

            pygame.display.flip()
            self.clock.tick(60)

            for event_obj in pygame.event.get():
                if event_obj.type == pygame.QUIT:
                    raise QuitRequested()
                if event_obj.type == pygame.MOUSEBUTTONDOWN and event_obj.button == 1:
                    pos = event_obj.pos
                    for b in self._buttons:
                        if b.rect.collidepoint(pos):
                            return b.value

    def show_timed(self, gs: "HUDPlayableGameState", active: Player, phase: str, event: str, seconds: float = 0.8):
        end_ticks = pygame.time.get_ticks() + int(seconds * 1000)
        while pygame.time.get_ticks() < end_ticks:
            for event_obj in pygame.event.get():
                if event_obj.type == pygame.QUIT:
                    raise QuitRequested()
            self._buttons = []
            self._draw_board(gs, active, phase, event)
            pygame.display.flip()
            self.clock.tick(60)


class HUDPlayableGameState(GameState):
    def __init__(
        self,
        p1: Player,
        p2: Player,
        card_pool: dict,
        tags_db: dict,
        human_player: Player,
        hud: PlayHUD,
    ):
        super().__init__(p1, p2, card_pool, tags_db)
        self.human = human_player
        self.hud = hud

    def run(self) -> dict:
        p1, p2 = self.players
        p1.draw_card(7)
        p2.draw_card(7)

        first = random.choice(self.players)
        order = [first, self.opponent(first)]
        first_flags = [True, True]

        for turn in range(1, MAX_TURNS + 1):
            self.turn = turn
            cur = order[(turn - 1) % 2]
            is_first = first_flags[(turn - 1) % 2]
            first_flags[(turn - 1) % 2] = False

            self.hud.show_timed(self, cur, "Manutencao", f"Turno {turn} - {cur.name}", seconds=0.5)
            self.phase_maintenance(cur, is_first)
            v = self.check_victory()
            if v:
                self.winner = v
                break

            if cur is self.human:
                self.phase_main_human(cur)
                self.phase_combat_human_attacker(cur)
            else:
                self.phase_main_ai(cur)
                self.phase_combat_ai_attacker(cur)

            if self.winner:
                break

            self.phase_end(cur)
            v = self.check_victory()
            if v:
                self.winner = v
                break

        self.hud.show_timed(self, self.human, "Vitoria", f"Vencedor: {self.winner.name if self.winner else 'Empate'}", seconds=2.0)

        return {
            "winner": self.winner.name if self.winner else "Empate",
            "winner_hero": self.winner.hero.name if self.winner else "-",
            "turns": self.turn,
            "p1_life": p1.life,
            "p2_life": p2.life,
            "p1_name": p1.name,
            "p2_name": p2.name,
        }

    def phase_main_ai(self, player: Player):
        super().phase_main(player)
        self.hud.show_timed(self, player, "Principal", "IA executou fase principal.", seconds=0.7)

    def phase_main_human(self, player: Player):
        opp = self.opponent(player)
        while True:
            try_levelup_phase(player, self)
            playable = self._playable_cards(player)

            options: list[tuple[str, object, tuple[int, int, int]]] = []
            options.append(("Encerrar fase principal", None, (120, 70, 70)))
            for idx, card in playable:
                cost = self._effective_cost(player, card)
                options.append((f"Jogar [{idx}] {card.name} ({card.card_type}) c{cost}", idx, (55, 80, 130)))

            choice = self.hud.choose_option(
                self,
                player,
                "Principal",
                "Escolha uma carta para jogar ou encerre a fase.",
                options,
            )
            if choice is None:
                break

            card = player.hand[choice] if 0 <= choice < len(player.hand) else None
            if card is None:
                continue
            self._play_card_human(player, opp, card)

    def phase_combat_human_attacker(self, player: Player):
        opp = self.opponent(player)

        if player.hero.id == "hero_tesslia" and player.hero_level >= 1:
            cmd = player.commander()
            attackers = [cmd] if cmd and cmd.can_attack() else []
        else:
            candidates = [c for c in player.field_creatures if c.can_attack()]
            if not candidates:
                self.hud.show_timed(self, player, "Combate", "Sem atacantes disponiveis.", seconds=0.7)
                return

            selected: set[int] = set()
            while True:
                options: list[tuple[str, object, tuple[int, int, int]]] = [
                    ("Confirmar ataque", "confirm", (65, 120, 90)),
                    ("Sem ataque", "skip", (120, 70, 70)),
                ]
                for c in candidates:
                    mark = "[X]" if c.iid in selected else "[ ]"
                    options.append((f"{mark} {c.name} {c.cur_off()}/{c.cur_vit()}", c.iid, (55, 80, 130)))

                choice = self.hud.choose_option(
                    self,
                    player,
                    "Combate",
                    "Selecione atacantes e confirme.",
                    options,
                )

                if choice == "skip":
                    return
                if choice == "confirm":
                    break
                if isinstance(choice, int):
                    if choice in selected:
                        selected.remove(choice)
                    else:
                        selected.add(choice)

            attackers = [c for c in candidates if c.iid in selected]

        if not attackers:
            self.hud.show_timed(self, player, "Combate", "Ataque vazio.", seconds=0.7)
            return

        blocks = AI.choose_blockers(attackers, opp, player)
        self._resolve_attack_step(player, opp, attackers, blocks)

    def phase_combat_ai_attacker(self, ai_player: Player):
        defender = self.opponent(ai_player)

        if ai_player.hero.id == "hero_tesslia" and ai_player.hero_level >= 1:
            cmd = ai_player.commander()
            attackers = [cmd] if cmd and cmd.can_attack() else []
        else:
            attackers = AI.choose_attackers(ai_player, defender)

        if not attackers:
            self.hud.show_timed(self, ai_player, "Combate", "IA nao atacou.", seconds=0.7)
            return

        if defender is self.human:
            blocks = self._choose_blocks_human(defender, attackers)
        else:
            blocks = AI.choose_blockers(attackers, defender, ai_player)

        self._resolve_attack_step(ai_player, defender, attackers, blocks)

    def _resolve_attack_step(
        self,
        attacker_player: Player,
        defender_player: Player,
        attackers: list[CardInst],
        blocks: dict[int, list[CardInst]],
    ):
        for atk in attackers:
            atk.tapped = True
            blks = blocks.get(atk.iid, [])

            if not blks:
                dmg = atk.cur_off()
                defender_player.life -= dmg
                attacker_player.stats_damage_dealt += dmg
                if atk.has_kw("Roubo de Vida"):
                    attacker_player.heal(dmg)
                self.hud.show_timed(
                    self,
                    attacker_player,
                    "Combate",
                    f"{atk.name} causou {dmg} dano direto.",
                    seconds=0.8,
                )
            elif len(blks) == 1:
                self._resolve_creature_combat(atk, blks[0], attacker_player, defender_player)
                self.hud.show_timed(
                    self,
                    attacker_player,
                    "Combate",
                    f"{atk.name} foi bloqueada por {blks[0].name}.",
                    seconds=0.8,
                )
            else:
                names = ", ".join(b.name for b in blks)
                self._resolve_gang_combat(atk, blks, attacker_player, defender_player)
                self.hud.show_timed(
                    self,
                    attacker_player,
                    "Combate",
                    f"{atk.name} sofreu gang block por {names}.",
                    seconds=0.8,
                )

            if attacker_player.hero.id == "hero_tesslia" and atk is attacker_player.commander():
                attacker_player.levelup_counter += 1

            v = self.check_victory()
            if v:
                self.winner = v
                return

    def _choose_blocks_human(self, defender: Player, attackers: list[CardInst]) -> dict[int, list[CardInst]]:
        blocks: dict[int, list[CardInst]] = {}
        avail = [c for c in defender.field_creatures if c.can_block()]

        for atk in attackers:
            if atk.has_kw("Furtivo"):
                blocks[atk.iid] = []
                continue

            candidates = [b for b in avail if (not atk.has_kw("Voar") or b.has_kw("Voar"))]
            options: list[tuple[str, object, tuple[int, int, int]]] = [
                (f"Nao bloquear {atk.name}", None, (120, 70, 70)),
            ]
            for c in candidates:
                options.append((f"Bloquear com {c.name} {c.cur_off()}/{c.cur_vit()}", c.iid, (55, 80, 130)))

            choice = self.hud.choose_option(
                self,
                defender,
                "Combate",
                f"Escolha bloqueio para {atk.name} {atk.cur_off()}/{atk.cur_vit()}.",
                options,
            )

            if choice is None:
                blocks[atk.iid] = []
                continue

            chosen = next((c for c in candidates if c.iid == choice), None)
            if chosen is None:
                blocks[atk.iid] = []
            else:
                blocks[atk.iid] = [chosen]
                avail.remove(chosen)

        return blocks

    def _play_card_human(self, player: Player, opp: Player, card: CardInst) -> bool:
        cost_red = getattr(player, "_cost_reduction_next", 0)
        cost = max(0, card.cost - cost_red)
        if cost > player.total_energy():
            return False

        if card.card_type == "creature":
            if player.field_size() >= MAX_CREATURES:
                return False

            slots = [i for i in range(MAX_CREATURES) if player.creature_at(i) is None]
            slot_options = [(f"Slot {s}", s, (55, 80, 130)) for s in slots]
            slot = self.hud.choose_option(
                self,
                player,
                "Principal",
                f"Escolha o slot para invocar {card.name}.",
                slot_options,
            )
            if slot is None:
                return False

            if not player.spend(cost):
                return False

            player.hand.remove(card)
            card.sick = True
            card.tapped = False
            card.temp_off = 0
            card.temp_vit = 0
            player._cost_reduction_next = max(0, cost_red - card.cost)
            player.place_creature(card, prefer_slot=slot)
            player.cards_played_this_turn += 1
            player.stats_cards_played[card.name] = player.stats_cards_played.get(card.name, 0) + 1
            self.engine.resolve_tags(card, "first_act", player)
            self.engine.resolve_tags(player.hero, "on_first_act_triggered", player, {"card": card})
            return True

        if card.card_type in ("spell", "enchant", "terrain"):
            if not player.spend(cost):
                return False

            player.hand.remove(card)
            player.cards_played_this_turn += 1
            player.stats_cards_played[card.name] = player.stats_cards_played.get(card.name, 0) + 1

            is_cafe = ("cafe" in card.name.lower() or any(t.get("cafe") for t in card.effect_tags))
            if is_cafe:
                player.cafes_played += 1
                player.levelup_counter += 1

            if card.card_type in ("enchant", "terrain"):
                player.spells_field.append(card)
            else:
                player.spells_cast_this_turn += 1

            player.levelup_counter += 1
            self.engine.resolve_tags(card, "on_play", player)
            for c in player.field_creatures:
                self.engine.resolve_tags(c, "on_spell_cast", player)
            player.graveyard.append(card)
            return True

        if card.card_type == "artifact":
            options = [
                i for i in range(MAX_CREATURES)
                if player.creature_at(i) is not None and player.support_at(i) is None
            ]
            if not options:
                return False

            slot = self.hud.choose_option(
                self,
                player,
                "Principal",
                f"Escolha onde equipar {card.name}.",
                [(f"Slot {s}", s, (55, 80, 130)) for s in options],
            )
            if slot is None:
                return False

            if not player.spend(cost):
                return False

            player.hand.remove(card)
            if not player.place_support(card, slot):
                player.hand.append(card)
                return False

            player.spells_field.append(card)
            player.cards_played_this_turn += 1
            player.stats_cards_played[card.name] = player.stats_cards_played.get(card.name, 0) + 1
            self.engine.resolve_tags(card, "on_play", player)
            return True

        return False

    def _playable_cards(self, player: Player) -> list[tuple[int, CardInst]]:
        out: list[tuple[int, CardInst]] = []
        for i, c in enumerate(player.hand):
            if self._effective_cost(player, c) <= player.total_energy():
                out.append((i, c))
        return out

    def _effective_cost(self, player: Player, card: CardInst) -> int:
        return max(0, card.cost - getattr(player, "_cost_reduction_next", 0))


def run_playable_match_hud(
    hero_player: str,
    hero_ai: str,
    data: dict,
    card_pool: dict,
    tags_db: dict,
    seed: Optional[int] = None,
) -> dict:
    if seed is not None:
        random.seed(seed)

    reset_iid()
    logger.clear()
    logger.set_verbose(False)

    h1, d1 = build_deck_for_hero(hero_player, data, card_pool, tags_db)
    h2, d2 = build_deck_for_hero(hero_ai, data, card_pool, tags_db)

    random.shuffle(d1)
    random.shuffle(d2)

    p1 = Player(name=f"Voce - {h1.name}", hero=h1, deck=d1)
    p2 = Player(name=f"IA - {h2.name}", hero=h2, deck=d2)

    hud = PlayHUD()
    gs = HUDPlayableGameState(p1, p2, card_pool, tags_db, human_player=p1, hud=hud)
    try:
        return gs.run()
    finally:
        hud.close()
