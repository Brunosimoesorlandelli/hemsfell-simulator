"""
Hemsfell Heroes — Simulador v2.2
==================================
GameState: orquestra as fases do jogo e usa os módulos especializados.
"""

from __future__ import annotations
import random
from typing import Optional
from .models import Player, CardInst
from .config import MAX_CREATURES, MAX_ENERGY, MAX_RESERVE, STARTING_HAND, MAX_TURNS, LEVELUP_COST
from .logger import log
from .level_system import try_levelup_phase
from .effect_engine import EffectEngine
from . import ai_engine as AI


# ─────────────────────────────────────────────
#  GAMESTATE
# ─────────────────────────────────────────────
class GameState:
    def __init__(self, p1: Player, p2: Player, card_pool: dict, tags_db: dict):
        self.players   = [p1, p2]
        self.turn      = 0
        self.winner: Optional[Player] = None
        self.card_pool = card_pool
        self.tags_db   = tags_db
        self.engine    = EffectEngine(self)
        self.rl_runtime = None

    def opponent(self, p: Player) -> Player:
        return self.players[1] if p is self.players[0] else self.players[0]

    def _is_interaction_card(self, card: CardInst) -> bool:
        actions = {t.get("action", "") for t in card.effect_tags}
        return any(a in actions for a in (
            "destroy", "deal_damage", "return_hand", "apply_status", "tap", "force_discard"
        ))

    # ── Destruição de criatura ────────────────────────────────────────────
    def destroy_creature(self, card: CardInst, owner: Player):
        if card not in owner.field_creatures:
            return
        owner.remove_creature(card)
        owner.deaths_this_turn += 1
        if owner.hero.id == "hero_tifon":
            owner.levelup_counter += 1
        log(f"💀 '{card.name}' destruída ({owner.name})", 2)

        double = getattr(owner, "_double_last_breath", False)
        for _ in range(2 if double else 1):
            self.engine.resolve_tags(card, "last_breath", owner)

        owner.graveyard.append(card)

        for c in list(owner.field_creatures):
            self.engine.resolve_tags(c, "on_death_ally", owner, {"dead": card})
        for enc in owner.spells_field:
            self.engine.resolve_tags(enc, "on_death_ally", owner, {"dead": card})
        self.engine.resolve_tags(owner.hero, "on_death_ally", owner, {"dead": card})

    # ── Verificação de vitória ────────────────────────────────────────────
    def check_victory(self) -> Optional[Player]:
        for p in self.players:
            if p.life <= 0:
                return self.opponent(p)
            if not p.deck and self.turn > 0:
                return self.opponent(p)
            if len(p.hand) >= 20 and "Colecionador" in p.hero.name:
                return p
        return None

    # ── FASES ─────────────────────────────────────────────────────────────
    def phase_maintenance(self, player: Player, first_turn: bool):
        log(f"\n📋 MANUTENÇÃO — {player.name}", 1)
        opp = self.opponent(player)
        player.reset_turn_flags()

        for c in player.field_creatures:
            if c.no_untap_next:
                c.no_untap_next = False
            elif "Imobilizado" in c.status:
                c.status.remove("Imobilizado")
            else:
                c.tapped = False
            c.sick = False
            c.vitality  = c.base_vit + c.markers.get("+1/+1", 0)
            c.temp_off  = 0
            c.temp_vit  = 0
            for st in ["Congelado", "Atordoado"]:
                if st in c.status:
                    c.status.remove(st)

        if first_turn:
            # Primeiro turno: obrigatório pegar energia (regra: max_energy começa em 0)
            action = "energy"
        else:
            action = AI._choose_maintenance_action(player, opp)

        if action == "energy":
            player.max_energy = min(MAX_ENERGY, player.max_energy + 1)
            drawn = player.draw_card(1)
            log(f"⚡ +1 energia ({player.max_energy}) | compra: "
                f"{drawn[0].name if drawn else '—vazio—'}", 2)
        else:
            drawn = player.draw_card(2)
            log(f"🃏 Compra 2: {', '.join(c.name for c in drawn) if drawn else '—'}", 2)

        player.energy = player.max_energy
        log(f"⚡ Energia: {player.energy}/{player.max_energy} +{player.reserve}R", 2)

        # triggers de manutenção por herói
        if player.hero.id == "hero_gimble":
            from .level_system import _dragon_count
            if _dragon_count(player) >= 2 and player.hero_level >= 1:
                player.heal(1)
                log(f"🐉 Gimble Nv1: +1 vida ({player.life})", 2)
            if player.hero_level >= 3:
                for c in player.field_creatures:
                    if "dragao" in c.race.lower() or "dragon" in c.race.lower():
                        c.add_marker("+1/+1", 1)

        if player.hero.id == "hero_sr_goblin" and player.hero_level >= 2:
            drawn = player.draw_card(1)
            if drawn:
                log(f"🃏 Goblin Nv2: extra '{drawn[0].name}'", 2)

        if player.hero.id == "hero_ngoro" and player.hero_level >= 1:
            target_d = self.opponent(player) if random.random() > 0.5 else player
            self.engine._investigate(target_d, 1, player)

        self.engine.resolve_tags(player.hero, "start_of_turn", player)
        for enc in player.spells_field:
            self.engine.resolve_tags(enc, "start_of_turn", player)
            self.engine.resolve_tags(enc, "start_of_turn_both", player)

        if self.rl_runtime is not None:
            self.rl_runtime.on_turn_start(self, player, opp)

    def phase_main(self, player: Player):
        log(f"\n⚙️  PRINCIPAL — {player.name}", 1)
        opp = self.opponent(player)
        player.turns_played += 1
        player.mana_budget_total += player.total_energy()
        player.max_energy_reached = max(player.max_energy_reached, player.max_energy)

        excluded_iids: set[int] = set()
        played_any = False
        while True:
            try_levelup_phase(player, self)
            card = None
            forced_pass = False

            if self.rl_runtime is not None:
                actions = []
                cost_red = getattr(player, "_cost_reduction_next", 0)
                can_levelup = (
                    player.hero_level < 3
                    and not player.leveled_up_this_turn
                    and player.total_energy() >= LEVELUP_COST.get(player.hero_level + 1, 99)
                )
                if can_levelup:
                    actions.append("levelup_if_possible")

                can_play_creature = False
                can_play_spell = False
                can_play_artifact = False
                for c in player.hand:
                    if c.iid in excluded_iids:
                        continue
                    cost_preview = max(0, c.cost - cost_red)
                    if c.card_type == "creature":
                        if cost_preview <= player.energy and player.field_size() < MAX_CREATURES:
                            can_play_creature = True
                    elif c.card_type in ("spell", "enchant", "terrain"):
                        if c.card_type == "spell":
                            if "Acelerado" not in c.keywords and cost_preview <= player.total_energy() and self._spell_useful(c, player, opp):
                                can_play_spell = True
                        else:
                            if cost_preview <= player.energy and self._spell_useful(c, player, opp):
                                can_play_spell = True
                    elif c.card_type == "artifact":
                        if cost_preview <= player.energy and AI.choose_artifact_slot(player) is not None:
                            can_play_artifact = True

                if can_play_creature:
                    actions.append("play_best_creature")
                if can_play_spell:
                    actions.append("play_best_spell")
                if can_play_artifact:
                    actions.append("play_best_artifact")
                actions.append("pass")

                action = self.rl_runtime.decide_main_action(self, player, opp, actions)
                if action == "pass":
                    break
                if action == "levelup_if_possible":
                    pre_lvl = player.hero_level
                    try_levelup_phase(player, self)
                    if player.hero_level == pre_lvl:
                        excluded_iids.add(-1)
                        self.rl_runtime.record_invalid_action(player, action)
                    else:
                        played_any = True
                    continue

                profile = AI.analyze_opponent(opp)
                candidates = []
                for c in player.hand:
                    if c.iid in excluded_iids:
                        continue
                    cost_preview = max(0, c.cost - getattr(player, "_cost_reduction_next", 0))
                    if action == "play_best_creature":
                        if c.card_type != "creature":
                            continue
                        if cost_preview > player.energy or player.field_size() >= MAX_CREATURES:
                            continue
                        candidates.append(c)
                    elif action == "play_best_spell":
                        if c.card_type not in ("spell", "enchant", "terrain"):
                            continue
                        if c.card_type == "spell":
                            if "Acelerado" in c.keywords:
                                continue
                            if cost_preview > player.total_energy():
                                continue
                        else:
                            if cost_preview > player.energy:
                                continue
                        if self._spell_useful(c, player, opp):
                            candidates.append(c)
                    elif action == "play_best_artifact":
                        if c.card_type != "artifact":
                            continue
                        if cost_preview > player.energy:
                            continue
                        if AI.choose_artifact_slot(player) is None:
                            continue
                        candidates.append(c)
                if candidates:
                    card = max(
                        candidates,
                        key=lambda c: AI.hand_card_score(c, player, opp, self.turn, profile),
                    )
                else:
                    forced_pass = True
                    self.rl_runtime.record_invalid_action(player, action)
            else:
                card = AI.choose_card_to_play(player, opp, self.turn, excluded_iids)
                if card is None:
                    break
                if played_any and not AI.should_play_card_now(card, player, opp, self.turn):
                    break

            if forced_pass:
                break

            cost_red = getattr(player, "_cost_reduction_next", 0)
            cost = max(0, card.cost - cost_red)
            # Regra: reserva só pode ser usada para feitiços.
            # Criaturas, encantos, terrenos e artefatos usam apenas energia regular.
            is_spell = card.card_type == "spell"
            avail_energy = player.total_energy() if is_spell else player.energy
            if cost > avail_energy:
                excluded_iids.add(card.iid)
                continue

            # Criatura
            if card.card_type == "creature":
                if player.field_size() >= MAX_CREATURES:
                    excluded_iids.add(card.iid)
                    continue
                if not player.spend(cost, allow_reserve=False):
                    excluded_iids.add(card.iid)
                    continue

                player.hand.remove(card)
                card.sick = True; card.tapped = False
                card.temp_off = 0; card.temp_vit = 0
                player._cost_reduction_next = max(0, cost_red - card.cost)
                player.place_creature(card)
                player.cards_played_this_turn += 1
                player.cards_played_total += 1
                player.creatures_played_total += 1
                player.stats_cards_played[card.name] = \
                    player.stats_cards_played.get(card.name, 0) + 1
                if self._is_interaction_card(card):
                    player.interaction_plays += 1
                log(f"🐉 [{player.name}] invoca '{card.name}' (custo {cost})", 2)
                self.engine.resolve_tags(card, "first_act", player)
                self.engine.resolve_tags(player.hero,
                                         "on_first_act_triggered",
                                         player, {"card": card})
                played_any = True
                continue

            # Feitiço/encanto/terreno
            if card.card_type in ("spell", "enchant", "terrain"):
                if "Acelerado" in card.keywords:
                    excluded_iids.add(card.iid)
                    continue
                if not self._spell_useful(card, player, opp):
                    excluded_iids.add(card.iid)
                    continue
                # Feitiço pode usar reserva; encanto/terreno não
                _allow_res = (card.card_type == "spell")
                if not player.spend(cost, allow_reserve=_allow_res):
                    excluded_iids.add(card.iid)
                    continue

                player.hand.remove(card)
                player.cards_played_this_turn += 1
                player.cards_played_total += 1
                player.stats_cards_played[card.name] = \
                    player.stats_cards_played.get(card.name, 0) + 1

                is_cafe = ("cafe" in card.name.lower()
                           or any(t.get("cafe") for t in card.effect_tags))
                if is_cafe:
                    player.cafes_played += 1
                    player.levelup_counter += 1

                if card.card_type in ("enchant", "terrain"):
                    player.spells_field.append(card)
                    log(f"🌍 [{player.name}] coloca '{card.name}'", 2)
                else:
                    log(f"🪄 [{player.name}] conjura '{card.name}' (custo {cost})", 2)
                    player.spells_cast_this_turn += 1
                    player.spells_cast_total += 1

                player.levelup_counter += 1
                if self._is_interaction_card(card):
                    player.interaction_plays += 1
                self.engine.resolve_tags(card, "on_play", player)
                for c in player.field_creatures:
                    self.engine.resolve_tags(c, "on_spell_cast", player)
                player.graveyard.append(card)
                played_any = True
                continue

            # Artefato
            if card.card_type == "artifact":
                slot = AI.choose_artifact_slot(player)
                if slot is None:
                    excluded_iids.add(card.iid)
                    continue
                if not player.spend(cost, allow_reserve=False):
                    excluded_iids.add(card.iid)
                    continue
                player.hand.remove(card)
                if not player.place_support(card, slot):
                    player.hand.append(card)
                    excluded_iids.add(card.iid)
                    continue
                player.spells_field.append(card)
                player.cards_played_this_turn += 1
                player.cards_played_total += 1
                player.stats_cards_played[card.name] = \
                    player.stats_cards_played.get(card.name, 0) + 1
                if self._is_interaction_card(card):
                    player.interaction_plays += 1
                self.engine.resolve_tags(card, "on_play", player)
                log(f"🛡️  [{player.name}] equipa '{card.name}' no slot {slot}", 2)
                played_any = True
                continue

            excluded_iids.add(card.iid)

        log(f"📊 {player.name}: vida {player.life} | "
            f"campo {player.field_size()} | mão {len(player.hand)}", 2)
        creature_plays_this_turn = max(0, player.cards_played_this_turn - player.spells_cast_this_turn)
        if player.cards_played_this_turn >= 2 and player.spells_cast_this_turn >= 1 and creature_plays_this_turn >= 1:
            player.combo_turns += 1
        if player.hero_level >= 3:
            player.level3_reached = True

    def _spell_useful(self, spell: CardInst, owner: Player, opp: Player) -> bool:
        tags = spell.effect_tags
        if not tags:
            return bool(spell.effect)
        for t in tags:
            target = t.get("target", "")
            if "ally_creature" in target and not owner.field_creatures:
                return False
            if "enemy_creature" in target and not opp.field_creatures:
                return False
        return True

    def phase_combat(self, player: Player):
        log(f"\n⚔️  COMBATE — {player.name}", 1)
        opp = self.opponent(player)

        if player.hero.id == "hero_tesslia" and player.hero_level >= 1:
            cmd = player.commander()
            attackers = [cmd] if cmd and cmd.can_attack() else []
        else:
            can_attack = [c for c in player.field_creatures if c.can_attack()]
            base = AI.choose_attackers(player, opp)
            if self.rl_runtime is None or not can_attack:
                attackers = base
            else:
                styles = ["safe", "all", "evasive", "none"]
                style = self.rl_runtime.decide_attack_style(self, player, opp, styles)
                if style == "none":
                    attackers = []
                elif style == "all":
                    attackers = can_attack
                elif style == "evasive":
                    attackers = [
                        c for c in can_attack
                        if c.has_kw("Furtivo") or c.has_kw("Voar") or c.has_kw("Investida")
                    ]
                    if not attackers:
                        attackers = base
                else:
                    attackers = base

        if not attackers:
            log("Sem atacantes.", 2)
            return

        # Regra: resolução dos combates da esquerda para direita (por slot)
        attackers.sort(key=lambda c: c.slot if c.slot is not None else 99)

        log(f"Atacando com: {', '.join(c.name for c in attackers)}", 2)

        blocks = AI.choose_blockers(attackers, opp, player)
        for atk in attackers:
            blks = blocks.get(atk.iid, [])
            if atk.has_kw("Furtivo"):
                log(f"👻 '{atk.name}' Furtivo — ataque direto", 2)
            elif blks:
                log(f"🛡️  '{opp.name}' bloqueia '{atk.name}' com '{blks[0].name}'", 2)
            else:
                log(f"💥 '{atk.name}' — ataque direto!", 2)

        # Hook: defensor pode responder com feitiço Acelerado antes do dano
        accel = AI.choose_accelerated_response(opp, player, context="combat")
        if accel and accel.cost <= opp.total_energy():
            if opp.spend(accel.cost, allow_reserve=True):
                opp.hand.remove(accel)
                opp.spells_cast_this_turn += 1
                opp.cards_played_this_turn += 1
                log(f"⚡ [{opp.name}] reage com '{accel.name}' (Acelerado)", 2)
                self.engine.resolve_tags(accel, "on_play", opp)
                opp.graveyard.append(accel)
                attackers = [a for a in attackers if a in player.field_creatures]

        # Detecta Defensor X: bloqueador que aparece em múltiplas entradas
        blocker_to_attackers: dict[int, list] = {}
        for atk in attackers:
            for blk in blocks.get(atk.iid, []):
                blocker_to_attackers.setdefault(blk.iid, []).append(atk)

        defensor_resolved_atk_iids: set[int] = set()
        for blk_iid, atk_list in blocker_to_attackers.items():
            if len(atk_list) > 1:
                # Localiza o objeto bloqueador
                blk = next(
                    (b for a in atk_list for b in blocks.get(a.iid, []) if b.iid == blk_iid),
                    None
                )
                if blk:
                    self._resolve_defensor_block(blk, atk_list, opp, player)
                    for a in atk_list:
                        defensor_resolved_atk_iids.add(a.iid)

        for atk in attackers:
            atk.tapped = True
            if atk.iid in defensor_resolved_atk_iids:
                continue  # já resolvido como Defensor X
            blks = blocks.get(atk.iid, [])
            if not blks:
                dmg = atk.cur_off()
                opp.life -= dmg
                player.stats_damage_dealt += dmg
                log(f"💢 '{atk.name}' causa {dmg} → vida {opp.name}: {opp.life}", 2)
                if atk.has_kw("Roubo de Vida"):
                    player.heal(dmg)
            else:
                self._resolve_creature_combat(atk, blks[0], player, opp)

            if player.hero.id == "hero_tesslia" and atk is player.commander():
                player.levelup_counter += 1

            v = self.check_victory()
            if v:
                self.winner = v
                return

    def _resolve_defensor_block(self, blk: CardInst, attackers: list[CardInst],
                                 blk_owner: Player, atk_owner: Player):
        """
        Resolve Defensor X: 1 bloqueador vs N atacantes simultaneamente.
        Regra: bloqueador recebe dano de TODOS os atacantes.
        Bloqueador concentra seu dano no atacante de maior valor que consiga matar,
        ou no mais forte se não conseguir matar nenhum.
        Atacantes NÃO causam dano ao herói (estão bloqueados).
        """
        log(f"🛡️  Defensor '{blk.name}' ({blk.cur_off()}/{blk.cur_vit()}) bloqueia "
            f"{', '.join(a.name for a in attackers)}", 2)

        # Dano total recebido pelo bloqueador (simultâneo)
        total_incoming = 0
        any_atk_tdm = False
        for atk in attackers:
            dmg = atk.cur_off()
            if blk.has_kw("Robusto"):
                dmg = max(0, dmg - 1)
            total_incoming += dmg
            if atk.has_kw("Toque da Morte") and atk.cur_off() > 0:
                any_atk_tdm = True

        # Aplica dano ao bloqueador
        if not blk.has_kw("Indestrutivel"):
            blk.vitality -= total_incoming
        blk_dies = (blk.cur_vit() <= 0 or any_atk_tdm) and not blk.has_kw("Indestrutivel")

        # Bloqueador escolhe 1 alvo para seu dano (maior valor que consegue matar)
        blk_dmg = blk.cur_off()
        if blk.has_kw("Congelado") or blk.has_kw("Sufocado"):
            blk_dmg = 0

        target_atk = None
        if blk_dmg > 0:
            killable = [a for a in attackers
                        if not a.has_kw("Indestrutivel")
                        and (blk.has_kw("Toque da Morte") or a.cur_vit() <= blk_dmg)]
            if killable:
                target_atk = max(killable, key=lambda a: card_value(a, atk_owner))
            else:
                target_atk = max(attackers, key=lambda a: a.cur_off())

        # Destrói atacantes alvo do dano do bloqueador
        if target_atk and blk_dmg > 0:
            recv = max(0, blk_dmg - (1 if target_atk.has_kw("Robusto") else 0))
            target_atk.vitality -= recv
            atk_dies = (target_atk.cur_vit() <= 0 or blk.has_kw("Toque da Morte")) \
                       and not target_atk.has_kw("Indestrutivel")
            if atk_dies and target_atk in atk_owner.field_creatures:
                blk_owner.kills += 1
                self.destroy_creature(target_atk, atk_owner)
                log(f"💀 '{target_atk.name}' destruído pelo Defensor", 2)

        # Resolve Atropelar dos atacantes não mortos pelo Defensor
        for atk in attackers:
            if atk not in atk_owner.field_creatures:
                continue  # foi destruído
            if atk.has_kw("Atropelar") and total_incoming > 0:
                # Calcula excesso apenas sobre a vitalidade do bloqueador
                excess = max(0, atk.cur_off() - blk.base_vit)
                if excess > 0:
                    blk_owner.life -= excess
                    atk_owner.stats_damage_dealt += excess
                    log(f"🐂 '{atk.name}' Atropelar +{excess} a {blk_owner.name}", 2)
            if atk.has_kw("Roubo de Vida"):
                atk_owner.heal(atk.cur_off())

        # Destrói bloqueador se necessário
        if blk_dies and blk in blk_owner.field_creatures:
            atk_owner.kills += 1
            self.destroy_creature(blk, blk_owner)

        log(f"   Defensor {'💀' if blk_dies else '✓'}  "
            f"alvo='{target_atk.name if target_atk else '—'}'", 2)
        """Resolve combate com múltiplos bloqueadores em um único atacante (gang block)."""
        log(f"⚔️  '{atk.name}' ({atk.cur_off()}/{atk.cur_vit()}) vs "
            f"{', '.join(b.name for b in blockers)} (gang block)", 2)

        # Verifica Veloz: atacante age antes se consegue matar TODOS antes de sofrer dano
        veloz_immunity = False
        if atk.has_kw("Veloz"):
            sim_pool = atk.cur_off()
            would_kill_all = True
            for blk in sorted(blockers, key=lambda b: b.cur_vit()):
                if blk.has_kw("Indestrutivel"):
                    would_kill_all = False
                    break
                lethal = (1 if atk.has_kw("Toque da Morte")
                          else blk.cur_vit() + (1 if blk.has_kw("Robusto") else 0))
                if sim_pool < lethal:
                    would_kill_all = False
                    break
                sim_pool -= lethal
            veloz_immunity = would_kill_all

        # Bloqueadores causam dano simultâneo ao atacante (exceto se Veloz matou todos)
        atk_damage_taken = 0
        any_blk_tdm = False
        if not veloz_immunity:
            for blk in blockers:
                dmg = max(0, blk.cur_off() - (1 if atk.has_kw("Robusto") else 0))
                atk_damage_taken += dmg
                if blk.has_kw("Toque da Morte") and blk.cur_off() > 0:
                    any_blk_tdm = True

        atk.vitality -= atk_damage_taken
        atk_dies = atk.cur_vit() <= 0 or any_blk_tdm
        if atk.has_kw("Indestrutivel"):
            atk_dies = False

        # Atacante distribui dano: mata menores primeiro (escolha ótima do atacante)
        atk_pool = atk.cur_off()
        killed_blockers = []
        for blk in sorted(blockers, key=lambda b: b.cur_vit()):
            if atk_pool <= 0 and not atk.has_kw("Toque da Morte"):
                break
            if blk.has_kw("Indestrutivel"):
                continue
            lethal = (1 if atk.has_kw("Toque da Morte")
                      else blk.cur_vit() + (1 if blk.has_kw("Robusto") else 0))
            assign = lethal if atk_pool >= lethal or atk.has_kw("Toque da Morte") else atk_pool
            dmg_received = max(0, assign - (1 if blk.has_kw("Robusto") else 0))
            blk.vitality -= dmg_received
            blk_dies = blk.cur_vit() <= 0 or atk.has_kw("Toque da Morte")
            if blk_dies:
                killed_blockers.append(blk)
                atk_pool = max(0, atk_pool - lethal)
            else:
                atk_pool = 0

        # Destroi bloqueadores mortos
        for blk in killed_blockers:
            if blk in blk_owner.field_creatures:
                atk_owner.kills += 1
                self.destroy_creature(blk, blk_owner)

        # Destroi atacante se necessário
        if atk_dies and atk in atk_owner.field_creatures:
            blk_owner.kills += 1
            self.destroy_creature(atk, atk_owner)

        # Atropelar: excesso vai ao herói SOMENTE se TODOS os bloqueadores morreram
        all_killed = len(killed_blockers) == len(blockers)
        if not atk_dies and atk.has_kw("Atropelar") and all_killed and atk_pool > 0:
            blk_owner.life -= atk_pool
            atk_owner.stats_damage_dealt += atk_pool
            log(f"🐂 '{atk.name}' Atropelar: +{atk_pool} ao herói {blk_owner.name}", 2)

        # Roubo de Vida
        if not atk_dies and atk.has_kw("Roubo de Vida"):
            atk_owner.heal(atk.cur_off())

        log(f"   Resultado: atk={'💀' if atk_dies else '✓'}  "
            f"mortos=[{', '.join(b.name for b in killed_blockers)}]", 2)

    def _resolve_creature_combat(self, atk: CardInst, blk: CardInst,
                                  atk_owner: Player, blk_owner: Player):
        log(f"⚔️  '{atk.name}' vs '{blk.name}'", 2)
        atk_dmg = atk.cur_off()
        blk_dmg = blk.cur_off()

        if blk.has_kw("Robusto"): atk_dmg = max(0, atk_dmg - 1)
        if atk.has_kw("Robusto"): blk_dmg = max(0, blk_dmg - 1)

        if atk.has_kw("Veloz") and not blk.has_kw("Veloz"):
            blk.vitality -= atk_dmg
            blk_killed = blk.cur_vit() <= 0 or atk.has_kw("Toque da Morte")
            if blk_killed:
                atk_owner.kills += 1
                self.destroy_creature(blk, blk_owner)
                if atk.has_kw("Atropelar") and atk_dmg > blk.base_vit:
                    excess = atk_dmg - blk.base_vit
                    blk_owner.life -= excess
                    atk_owner.stats_damage_dealt += excess
                return

        blk.vitality -= atk_dmg
        atk.vitality -= blk_dmg

        blk_died = blk.cur_vit() <= 0 or atk.has_kw("Toque da Morte")
        atk_died = atk.cur_vit() <= 0 or blk.has_kw("Toque da Morte")

        if blk.has_kw("Indestrutivel"): blk_died = False
        if atk.has_kw("Indestrutivel"): atk_died = False

        if blk_died:
            atk_owner.kills += 1
            self.destroy_creature(blk, blk_owner)
            if atk.has_kw("Atropelar") and atk_dmg > blk.base_vit:
                excess = atk_dmg - blk.base_vit
                blk_owner.life -= excess
                atk_owner.stats_damage_dealt += excess

        if atk_died:
            blk_owner.kills += 1
            self.destroy_creature(atk, atk_owner)

        if not atk_died and atk.has_kw("Roubo de Vida"):
            atk_owner.heal(atk_dmg)

    def phase_end(self, player: Player):
        log(f"\n🔚 FIM DE TURNO — {player.name}", 1)
        if player.energy > 0:
            transfer = min(player.energy, MAX_RESERVE - player.reserve)
            if transfer > 0:
                player.reserve += transfer
                player.energy  -= transfer
        player.energy = 0

        for c in player.field_creatures:
            c.temp_off = 0
            c.temp_vit = 0

        self.engine.resolve_tags(player.hero, "end_of_turn", player)
        for c in player.field_creatures:
            self.engine.resolve_tags(c, "end_of_turn", player)
        for enc in player.spells_field:
            self.engine.resolve_tags(enc, "end_of_turn", player)

        if player.hero.id == "hero_rasmus" and player.hero_level >= 1:
            gain = min(player.cafes_played, MAX_RESERVE - player.reserve)
            if gain > 0:
                player.reserve += gain
                log(f"☕ Rasmus Nv1: +{gain} reserva ({player.reserve})", 2)

        player.hand_limit()
        player.life_min = min(player.life_min, player.life)

    # ── LOOP PRINCIPAL ────────────────────────────────────────────────────
    def run(self) -> dict:
        p1, p2 = self.players
        p1.draw_card(STARTING_HAND)
        p2.draw_card(STARTING_HAND)

        first = random.choice(self.players)
        order = [first, self.opponent(first)]
        first_flags = [True, True]

        for turn in range(1, MAX_TURNS + 1):
            self.turn = turn
            cur       = order[(turn - 1) % 2]
            is_first  = first_flags[(turn - 1) % 2]
            first_flags[(turn - 1) % 2] = False

            log(f"\n{'─'*60}\nTURNO {turn} — {cur.name} (Nv{cur.hero_level})\n{'─'*60}")

            self.phase_maintenance(cur, is_first)
            v = self.check_victory()
            if v:
                self.winner = v
                break

            self.phase_main(cur)
            self.phase_combat(cur)
            if self.winner:
                if self.rl_runtime is not None:
                    self.rl_runtime.on_turn_end(self, cur, self.opponent(cur))
                break

            self.phase_end(cur)
            if self.rl_runtime is not None:
                self.rl_runtime.on_turn_end(self, cur, self.opponent(cur))
            v = self.check_victory()
            if v:
                self.winner = v
                break

        if self.rl_runtime is not None:
            self.rl_runtime.on_game_end(self)

        def _metrics(p: Player) -> dict:
            mana_eff = p.mana_spent_total / p.mana_budget_total if p.mana_budget_total > 0 else 0.0
            return {
                "mana_spent_total": p.mana_spent_total,
                "mana_budget_total": p.mana_budget_total,
                "mana_efficiency": mana_eff,
                "max_energy_reached": p.max_energy_reached,
                "cards_played_total": p.cards_played_total,
                "spells_cast_total": p.spells_cast_total,
                "creatures_played_total": p.creatures_played_total,
                "combo_turns": p.combo_turns,
                "interaction_plays": p.interaction_plays,
                "turns_played": p.turns_played,
                "life_min": p.life_min,
                "level3_reached": p.level3_reached,
            }

        return {
            "winner":       self.winner.name if self.winner else "Empate",
            "winner_hero":  self.winner.hero.name if self.winner else "—",
            "loser_hero":   self.opponent(self.winner).hero.name if self.winner else "—",
            "winner_level": self.winner.hero_level if self.winner else 0,
            "loser_level":  self.opponent(self.winner).hero_level if self.winner else 0,
            "turns":        self.turn,
            "p1_life":      p1.life,
            "p2_life":      p2.life,
            "p1_kills":     p1.kills,
            "p2_kills":     p2.kills,
            "p1_damage":    p1.stats_damage_dealt,
            "p2_damage":    p2.stats_damage_dealt,
            "p1_cards":     dict(p1.stats_cards_played),
            "p2_cards":     dict(p2.stats_cards_played),
            "p1_cards_drawn": dict(p1.stats_cards_drawn),
            "p2_cards_drawn": dict(p2.stats_cards_drawn),
            "p1_metrics":   _metrics(p1),
            "p2_metrics":   _metrics(p2),
            "p1_name":      p1.name,
            "p2_name":      p2.name,
        }
