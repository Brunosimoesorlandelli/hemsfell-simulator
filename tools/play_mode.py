"""
Modo jogavel para testes de decks (Humano vs IA).

Executa uma partida usando o mesmo engine do simulador, mas com escolhas
manuais para jogar cartas, atacar e bloquear.
"""

from __future__ import annotations

import random
from typing import Optional

from engine import ai_engine as AI
from engine import logger
from engine.config import MAX_CREATURES, MAX_TURNS
from engine.level_system import try_levelup_phase
from engine.loader import build_deck_for_hero
from engine.models import CardInst, Player, reset_iid
from engine.simulator import GameState


class PlayableGameState(GameState):
    def __init__(
        self,
        p1: Player,
        p2: Player,
        card_pool: dict,
        tags_db: dict,
        human_player: Player,
    ):
        super().__init__(p1, p2, card_pool, tags_db)
        self.human = human_player

    def run(self) -> dict:
        p1, p2 = self.players
        p1.draw_card(7)
        p2.draw_card(7)

        first = random.choice(self.players)
        order = [first, self.opponent(first)]
        first_flags = [True, True]

        print("\n" + "=" * 70)
        print("Modo jogavel iniciado")
        print(f"Voce controla: {self.human.hero.name}")
        print("=" * 70)

        for turn in range(1, MAX_TURNS + 1):
            self.turn = turn
            cur = order[(turn - 1) % 2]
            is_first = first_flags[(turn - 1) % 2]
            first_flags[(turn - 1) % 2] = False

            print("\n" + "-" * 70)
            print(f"Turno {turn}: {cur.name} | nivel {cur.hero_level}")
            print("-" * 70)

            self.phase_maintenance(cur, is_first)
            v = self.check_victory()
            if v:
                self.winner = v
                break

            if cur is self.human:
                self.phase_main_human(cur)
                self.phase_combat_human_attacker(cur)
            else:
                super().phase_main(cur)
                self.phase_combat_ai_attacker(cur)

            if self.winner:
                break

            self.phase_end(cur)
            v = self.check_victory()
            if v:
                self.winner = v
                break

        return {
            "winner": self.winner.name if self.winner else "Empate",
            "winner_hero": self.winner.hero.name if self.winner else "-",
            "turns": self.turn,
            "p1_life": p1.life,
            "p2_life": p2.life,
            "p1_name": p1.name,
            "p2_name": p2.name,
        }

    def phase_main_human(self, player: Player):
        opp = self.opponent(player)
        print("\n[Fase Principal]")

        while True:
            try_levelup_phase(player, self)
            self._print_board(player)

            playable = self._playable_cards(player)
            if not playable:
                print("Sem cartas jogaveis com a energia atual.")
                break

            print("\nCartas jogaveis:")
            for i, card in playable:
                cost = self._effective_cost(player, card)
                print(f"  {i}: {card.name} ({card.card_type}) custo {cost}")

            choice = input("Escolha indice da carta para jogar (Enter para passar): ").strip()
            if not choice:
                break
            if not choice.isdigit():
                print("Entrada invalida.")
                continue

            idx = int(choice)
            if idx < 0 or idx >= len(player.hand):
                print("Indice fora da mao.")
                continue

            card = player.hand[idx]
            if not self._play_card_human(player, opp, card):
                continue

    def phase_combat_human_attacker(self, player: Player):
        opp = self.opponent(player)
        print("\n[Fase de Combate - Voce ataca]")

        if player.hero.id == "hero_tesslia" and player.hero_level >= 1:
            cmd = player.commander()
            attackers = [cmd] if cmd and cmd.can_attack() else []
            if attackers:
                print(f"Tesslia: comandante '{attackers[0].name}' ataca obrigatoriamente.")
        else:
            candidates = [c for c in player.field_creatures if c.can_attack()]
            if not candidates:
                print("Sem atacantes disponiveis.")
                return

            print("Atacantes disponiveis:")
            for i, c in enumerate(candidates):
                print(f"  {i}: {self._card_line(c)}")

            raw = input("Indices para atacar (ex: 0,2) ou Enter para nao atacar: ").strip()
            if not raw:
                print("Ataque cancelado.")
                return

            attackers = []
            for token in raw.split(","):
                token = token.strip()
                if not token.isdigit():
                    continue
                i = int(token)
                if 0 <= i < len(candidates):
                    attackers.append(candidates[i])

            uniq: dict[int, CardInst] = {a.iid: a for a in attackers}
            attackers = list(uniq.values())

        if not attackers:
            print("Sem atacantes validos.")
            return

        blocks = AI.choose_blockers(attackers, opp, player)
        self._resolve_attack_step(player, opp, attackers, blocks)

    def phase_combat_ai_attacker(self, ai_player: Player):
        defender = self.opponent(ai_player)
        print("\n[Fase de Combate - IA ataca]")

        if ai_player.hero.id == "hero_tesslia" and ai_player.hero_level >= 1:
            cmd = ai_player.commander()
            attackers = [cmd] if cmd and cmd.can_attack() else []
        else:
            attackers = AI.choose_attackers(ai_player, defender)

        if not attackers:
            print("IA nao declarou atacantes.")
            return

        print("IA ataca com:")
        for a in attackers:
            print(f"  - {self._card_line(a)}")

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
                print(f"{atk.name} causa {dmg} de dano direto em {defender_player.name}.")
                if atk.has_kw("Roubo de Vida"):
                    attacker_player.heal(dmg)
            elif len(blks) == 1:
                print(f"{atk.name} foi bloqueada por {blks[0].name}.")
                self._resolve_creature_combat(atk, blks[0], attacker_player, defender_player)
            else:
                names = ", ".join(b.name for b in blks)
                print(f"{atk.name} foi bloqueada por {names} (gang block).")
                self._resolve_gang_combat(atk, blks, attacker_player, defender_player)

            if attacker_player.hero.id == "hero_tesslia" and atk is attacker_player.commander():
                attacker_player.levelup_counter += 1

            v = self.check_victory()
            if v:
                self.winner = v
                return

    def _choose_blocks_human(
        self,
        defender: Player,
        attackers: list[CardInst],
    ) -> dict[int, list[CardInst]]:
        blocks: dict[int, list[CardInst]] = {}
        avail = [c for c in defender.field_creatures if c.can_block()]

        for atk in attackers:
            if atk.has_kw("Furtivo"):
                blocks[atk.iid] = []
                print(f"{atk.name} tem Furtivo e nao pode ser bloqueada.")
                continue

            candidates = [b for b in avail if (not atk.has_kw("Voar") or b.has_kw("Voar"))]
            if not candidates:
                blocks[atk.iid] = []
                print(f"Sem bloqueadores validos para {atk.name}.")
                continue

            print(f"\nEscolha bloqueio para atacante '{atk.name}' ({atk.cur_off()}/{atk.cur_vit()}):")
            print("  Enter = nao bloquear")
            for i, c in enumerate(candidates):
                print(f"  {i}: {self._card_line(c)}")

            raw = input("Bloqueador: ").strip()
            if not raw:
                blocks[atk.iid] = []
                continue
            if not raw.isdigit():
                blocks[atk.iid] = []
                continue

            idx = int(raw)
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]
                blocks[atk.iid] = [chosen]
                avail.remove(chosen)
            else:
                blocks[atk.iid] = []

        return blocks

    def _play_card_human(self, player: Player, opp: Player, card: CardInst) -> bool:
        cost_red = getattr(player, "_cost_reduction_next", 0)
        cost = max(0, card.cost - cost_red)
        if cost > player.total_energy():
            print("Energia insuficiente.")
            return False

        if card.card_type == "creature":
            if player.field_size() >= MAX_CREATURES:
                print("Campo cheio.")
                return False

            slots = [i for i in range(MAX_CREATURES) if player.creature_at(i) is None]
            print(f"Slots livres: {slots}")
            raw_slot = input("Escolha slot (Enter = primeiro livre): ").strip()
            slot = slots[0]
            if raw_slot:
                if not raw_slot.isdigit() or int(raw_slot) not in slots:
                    print("Slot invalido.")
                    return False
                slot = int(raw_slot)

            if not player.spend(cost):
                print("Nao foi possivel gastar energia.")
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
            print(f"Voce invocou {card.name} no slot {slot} (custo {cost}).")

            self.engine.resolve_tags(card, "first_act", player)
            self.engine.resolve_tags(player.hero, "on_first_act_triggered", player, {"card": card})
            return True

        if card.card_type in ("spell", "enchant", "terrain"):
            if not player.spend(cost):
                print("Nao foi possivel gastar energia.")
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
                print(f"Voce colocou {card.name} em campo.")
            else:
                player.spells_cast_this_turn += 1
                print(f"Voce conjurou {card.name} (custo {cost}).")

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
                print("Sem alvo para artefato (precisa criatura com suporte livre).")
                return False

            print(f"Slots validos para artefato: {options}")
            raw_slot = input("Escolha slot do artefato: ").strip()
            if not raw_slot.isdigit() or int(raw_slot) not in options:
                print("Slot invalido.")
                return False
            slot = int(raw_slot)

            if not player.spend(cost):
                print("Nao foi possivel gastar energia.")
                return False

            player.hand.remove(card)
            if not player.place_support(card, slot):
                print("Falha ao anexar artefato.")
                player.hand.append(card)
                return False

            player.spells_field.append(card)
            player.cards_played_this_turn += 1
            player.stats_cards_played[card.name] = player.stats_cards_played.get(card.name, 0) + 1
            self.engine.resolve_tags(card, "on_play", player)
            print(f"Voce equipou {card.name} no slot {slot}.")
            return True

        print(f"Tipo de carta nao suportado no modo jogavel: {card.card_type}")
        return False

    def _playable_cards(self, player: Player) -> list[tuple[int, CardInst]]:
        out: list[tuple[int, CardInst]] = []
        for i, c in enumerate(player.hand):
            if self._effective_cost(player, c) <= player.total_energy():
                out.append((i, c))
        return out

    def _effective_cost(self, player: Player, card: CardInst) -> int:
        return max(0, card.cost - getattr(player, "_cost_reduction_next", 0))

    def _print_board(self, player: Player):
        opp = self.opponent(player)
        print("\nEstado atual:")
        print(
            f"Voce: {player.hero.name} | Vida {player.life} | Energia {player.energy}/{player.max_energy} +{player.reserve}R"
        )
        print(
            f"IA  : {opp.hero.name} | Vida {opp.life} | Energia {opp.energy}/{opp.max_energy} +{opp.reserve}R"
        )

        print("\nSeu campo:")
        for slot in range(MAX_CREATURES):
            c = player.creature_at(slot)
            if c is None:
                print(f"  [{slot}] (vazio)")
            else:
                print(f"  [{slot}] {self._card_line(c)}")

        print(f"\nSua mao ({len(player.hand)} cartas):")
        for i, c in enumerate(player.hand):
            print(f"  {i}: {c.name} [{c.card_type}] custo {c.cost}")

    @staticmethod
    def _card_line(card: CardInst) -> str:
        status = ""
        if card.status:
            status = " [" + ",".join(card.status) + "]"
        tapped = " T" if card.tapped else ""
        return f"{card.name} {card.cur_off()}/{card.cur_vit()}{tapped}{status}"


def run_playable_match(
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

    gs = PlayableGameState(p1, p2, card_pool, tags_db, human_player=p1)
    return gs.run()
