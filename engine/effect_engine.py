"""
Hemsfell Heroes — Motor de Efeitos
====================================
Resolve effect_tags de cartas. Recebe referência ao GameState.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Optional
from .logger import log
from .loader import make_card

if TYPE_CHECKING:
    from .models import CardInst, Player
    from .simulator import GameState


class EffectEngine:
    def __init__(self, gs: "GameState"):
        self.gs = gs

    def resolve_tags(self, card: "CardInst", trigger: str,
                     owner: "Player", context: dict = None):
        if context is None:
            context = {}
        tags = [t for t in card.effect_tags if t.get("trigger") == trigger]
        for tag in tags:
            self._resolve_tag(tag, card, owner, context)

    def _resolve_tag(self, tag: dict, card: "CardInst", owner: "Player", ctx: dict):
        action = tag.get("action", "")
        opp    = self.gs.opponent(owner)

        if not self._check_condition(tag, owner, opp, ctx):
            return

        if "level" in tag and owner.hero.id == card.id:
            if owner.hero_level < tag["level"]:
                return

        # ── AÇÕES ──────────────────────────────────────────────────────────
        if action == "draw":
            n = self._val(tag.get("value", 1), owner, ctx)
            drawn = owner.draw_card(n)
            if drawn:
                log(f"🃏 [{owner.name}] compra {len(drawn)}: "
                    f"{', '.join(c.name for c in drawn)}", 3)

        elif action == "deal_damage":
            n      = self._val(tag.get("value", 1), owner, ctx)
            target = tag.get("target", "any_creature")
            if "enemy_hero" in target:
                self._dmg_player(opp, n, card.name)
            elif "all_enemy_creatures" in target:
                for c in list(opp.field_creatures):
                    self._dmg_creature(c, n, owner, opp)
            elif "all_creatures" in target:
                for c in list(owner.field_creatures + opp.field_creatures):
                    o2 = owner if c in owner.field_creatures else opp
                    self._dmg_creature(c, n, owner, o2)
            elif "any" in target or "any_creature" in target:
                targets = list(opp.field_creatures)
                if targets:
                    t = min(targets, key=lambda c: c.cur_vit())
                    self._dmg_creature(t, n, owner, opp)

        elif action == "heal":
            n = self._val(tag.get("value", 1), owner, ctx)
            owner.heal(n)
            log(f"❤️  [{owner.name}] +{n} vida ({owner.life})", 3)

        elif action == "lose_life":
            n = self._val(tag.get("value", 1), owner, ctx)
            owner.lose_life(n)
            log(f"🩸 [{owner.name}] -{n} vida ({owner.life})", 3)
            self._on_owner_lose_life(owner, n)

        elif action == "buff":
            value_str = tag.get("value", "+0/+0")
            off_b, vit_b = self._parse_buff(value_str, owner, ctx)
            targets = self._resolve_targets(tag.get("target", "self"), card, owner, opp, tag)
            for t in targets:
                t.temp_off += off_b
                t.temp_vit += vit_b
                if tag.get("permanent"):
                    t.offense  += off_b; t.base_off += off_b
                    t.vitality += vit_b; t.base_vit += vit_b
                log(f"⚡ '{t.name}' recebe {value_str}", 3)

        elif action == "debuff":
            off_b, vit_b = self._parse_buff(tag.get("value", "0/0"), owner, ctx)
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                t.temp_off += off_b
                t.temp_vit += vit_b

        elif action == "grant_keyword":
            kw = tag.get("keyword", "")
            for t in self._resolve_targets(tag.get("target", "self"), card, owner, opp, tag):
                if kw and kw not in t.keywords:
                    t.keywords.append(kw)
                    log(f"🔑 '{t.name}' recebe '{kw}'", 3)

        elif action == "apply_status":
            status = tag.get("status", "")
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                if status and status not in t.status:
                    t.status.append(status)
                    log(f"🌀 '{t.name}' fica {status}", 3)

        elif action == "destroy":
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                o2 = owner if t in owner.field_creatures else opp
                if t in o2.field_creatures:
                    self.gs.destroy_creature(t, o2)

        elif action == "sacrifice":
            if owner.field_creatures:
                t = owner.field_creatures[0]
                owner.remove_creature(t)
                owner.graveyard.append(t)
                owner.deaths_this_turn += 1
                log(f"⚔️  [{owner.name}] sacrifica '{t.name}'", 3)

        elif action == "return_hand":
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                o2 = owner if t in owner.field_creatures else opp
                if t in o2.field_creatures:
                    o2.remove_creature(t)
                    o2.hand.append(t)
                    t.sick = True; t.tapped = False
                    t.temp_off = 0; t.temp_vit = 0
                    log(f"↩️  '{t.name}' retorna para mão de {o2.name}", 3)

        elif action == "mill":
            n = self._val(tag.get("value", 1), owner, ctx)
            target_p = opp if "opponent" in tag.get("target", "") else owner
            target_p.mill(n)

        elif action == "ban":
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                o2 = owner if t in owner.field_creatures else opp
                if t in o2.field_creatures:
                    o2.remove_creature(t)
                    o2.obscure.append(t)
                    log(f"🚫 '{t.name}' banida", 3)

        elif action == "search":
            filt = tag.get("filter", "")
            for i, c in enumerate(owner.deck):
                if self._matches_filter(c, filt):
                    owner.deck.pop(i)
                    owner.hand.append(c)
                    log(f"🔍 [{owner.name}] busca '{c.name}'", 3)
                    random.shuffle(owner.deck)
                    break

        elif action == "revive":
            filt = tag.get("filter", "")
            for c in owner.graveyard:
                if c.card_type == "creature" and self._matches_filter(c, filt):
                    owner.graveyard.remove(c)
                    c.sick = True; c.tapped = False
                    c.vitality = c.base_vit; c.temp_off = 0; c.temp_vit = 0
                    if owner.field_size() < 5:
                        owner.place_creature(c)
                        log(f"✨ '{c.name}' ressuscitada", 3)
                    break

        elif action == "add_energy":
            n = self._val(tag.get("value", 1), owner, ctx)
            from .config import MAX_ENERGY
            owner.energy = min(MAX_ENERGY, owner.energy + n)
            log(f"⚡ [{owner.name}] +{n} energia ({owner.energy}/{owner.max_energy})", 3)

        elif action == "fill_reserve":
            from .config import MAX_RESERVE
            owner.reserve = MAX_RESERVE

        elif action == "add_reserve":
            from .config import MAX_RESERVE
            n = self._val(tag.get("value", 1), owner, ctx)
            owner.reserve = min(MAX_RESERVE, owner.reserve + n)

        elif action == "tap":
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                t.tapped = True

        elif action == "untap":
            for t in self._resolve_targets(tag.get("target", "any_creature"), card, owner, opp, tag):
                t.tapped = False

        elif action == "discard":
            n = self._val(tag.get("value", 1), owner, ctx)
            for _ in range(n):
                if owner.hand:
                    c = random.choice(owner.hand)
                    owner.hand.remove(c)
                    owner.graveyard.append(c)

        elif action == "force_discard":
            target_p = opp if tag.get("target") == "opponent" else owner
            if target_p.hand:
                c = random.choice(target_p.hand)
                target_p.hand.remove(c)
                target_p.graveyard.append(c)

        elif action == "add_marker":
            n     = self._val(tag.get("value", 1), owner, ctx)
            mtype = tag.get("marker_type", "+1/+1")
            for t in self._resolve_targets(tag.get("target", "self"), card, owner, opp, tag):
                t.add_marker(mtype, n)
                log(f"📍 '{t.name}' +{n}x {mtype}", 3)

        elif action == "create_image":
            self._create_image(tag.get("image_id", ""), owner)

        elif action == "shuffle_graveyard_into_deck":
            owner.deck.extend(owner.graveyard)
            owner.graveyard.clear()
            random.shuffle(owner.deck)

        elif action == "discard_hand_draw_same":
            n = len(owner.hand)
            owner.graveyard.extend(owner.hand)
            owner.hand.clear()
            owner.draw_card(n)

        elif action == "choice_opponent":
            choices = tag.get("choices", [])
            if choices:
                self._resolve_tag(choices[0], card, owner, ctx)

        elif action == "increase_max_energy":
            from .config import MAX_ENERGY
            owner.max_energy = min(MAX_ENERGY, owner.max_energy + 1)

        elif action == "reduce_cost":
            n = self._val(tag.get("value", 1), owner, ctx)
            owner._cost_reduction_next = getattr(owner, "_cost_reduction_next", 0) + n

        elif action == "investigate":
            n       = self._val(tag.get("value", 1), owner, ctx)
            target_p = opp if "opponent" in tag.get("target", "") else owner
            self._investigate(target_p, n, owner)

        elif action == "gain_pista":
            n = self._val(tag.get("value", 1), owner, ctx)
            owner.pistas += n
            log(f"🔎 [{owner.name}] +{n} pista(s) ({owner.pistas})", 3)

        elif action == "set_stats":
            x = self._x_value(tag.get("x_source", ""), owner, opp, ctx)
            card.offense = x; card.vitality = x
            card.temp_off = 0; card.temp_vit = 0

        elif action == "survive_with_1hp":
            if "dying_creature" in ctx:
                dc = ctx["dying_creature"]
                if dc.card_type == "creature":
                    dc.vitality = 1

        elif action == "commander_buff":
            if owner.field_creatures:
                mid = len(owner.field_creatures) // 2
                cmd = owner.field_creatures[mid]
                off_b, vit_b = self._parse_buff(tag.get("value", "+2/0"), owner, ctx)
                cmd.temp_off += off_b
                if "Atropelar" not in cmd.keywords and owner.hero_level >= 2:
                    cmd.keywords.append("Atropelar")

        elif action == "chain_damage":
            targets = list(opp.field_creatures)
            if targets:
                t = min(targets, key=lambda c: c.cur_vit())
                n = self._val(tag.get("value", 1), owner, ctx)
                self._dmg_creature(t, n, owner, opp)
                if t not in opp.field_creatures:
                    new_targets = list(opp.field_creatures)
                    if new_targets:
                        t2 = min(new_targets, key=lambda c: c.cur_vit())
                        self._dmg_creature(t2, n, owner, opp)

        elif action == "element_bonus":
            element = getattr(owner, "_last_element", None)
            if element:
                sub = tag.get(element, {})
                if sub:
                    self._resolve_tag({**sub, "trigger": "on_play"}, card, owner, ctx)

        elif action == "elemental_damage":
            element = random.choice(["Agua", "Ar", "Fogo", "Terra"])
            n = self._val(tag.get("value", 1), owner, ctx)
            targets = list(opp.field_creatures)
            if targets:
                t = min(targets, key=lambda c: c.cur_vit())
                self._dmg_creature(t, n, owner, opp)
            owner._last_element = element

        elif action == "cafe_ritual":
            n = owner.cafes_played
            for _ in range(n):
                drawn = owner.draw_card(1)
                if drawn:
                    log(f"☕ Ritual do Barista: compra '{drawn[0].name}'", 3)

        elif action == "tranqueira_roll":
            n = owner.cards_played_this_turn
            if n < 5:
                owner.life -= n
            elif n == 5:
                self._create_image("img_bucha_canhao", owner)
            elif n == 6:
                self._create_image("img_trambuco_pipoco", owner)
            else:
                self._create_image("img_carcaca_tanque", owner)

        elif action == "spend_pistas_choice":
            cost = tag.get("cost", 2)
            if owner.pistas >= cost:
                owner.pistas -= cost
                choices = tag.get("choices", [])
                if choices:
                    self._resolve_tag(choices[0], card, owner, ctx)

        # noop silencioso para ações não implementadas
        # (permite adicionar novas ações sem crash)

    # ── HELPERS ──────────────────────────────────────────────────────────────

    def _dmg_player(self, player: "Player", n: int, source: str):
        player.life -= n
        log(f"💢 {player.name} ←{n} ({source}). Vida: {player.life}", 3)

    def _dmg_creature(self, creature: "CardInst", n: int,
                      attacker_owner: "Player", defender_owner: "Player"):
        if creature.has_kw("Robusto"):
            n = max(0, n - 1)
        if creature.has_kw("Indestrutivel"):
            return
        creature.vitality -= n
        log(f"⚔️  '{creature.name}' -{n} → {creature.cur_vit()} vit", 3)
        if creature.cur_vit() <= 0:
            attacker_owner.kills += 1
            self.gs.destroy_creature(creature, defender_owner)

    def _check_condition(self, tag: dict, owner: "Player", opp: "Player",
                         ctx: dict) -> bool:
        cond = tag.get("condition", "")
        if not cond:
            return True
        if cond == "own_turn":
            return ctx.get("is_own_turn", True)
        if cond.startswith("ally_class_count_gte"):
            _, n, cls = cond.split(":")
            return sum(1 for c in owner.field_creatures
                       if cls.lower() in c.race.lower()) >= int(n)
        if cond.startswith("ally_class_count_eq"):
            _, n, cls = cond.split(":")
            return sum(1 for c in owner.field_creatures
                       if cls.lower() in c.race.lower()) == int(n)
        if cond == "no_spell_cast_this_turn":
            return owner.spells_cast_this_turn == 0
        if cond.startswith("spell_cast_this_turn_gte"):
            return owner.spells_cast_this_turn >= int(cond.split(":")[1])
        if cond.startswith("graveyard_count_gte"):
            return len(owner.graveyard) >= int(cond.split(":")[1])
        if cond.startswith("owner_life_lte"):
            return owner.life <= int(cond.split(":")[1])
        if cond.startswith("ally_count_gte"):
            return len(owner.field_creatures) >= int(cond.split(":")[1])
        if cond.startswith("pair_in_field"):
            return any(c.id == cond.split(":")[1] for c in owner.field_creatures)
        if cond == "controls_no_effect_creature":
            return any(not c.effect for c in owner.field_creatures)
        return True

    def _val(self, value, owner: "Player", ctx: dict) -> int:
        if isinstance(value, int):
            return value
        if value == "X":
            return self._x_value("", owner, None, ctx)
        return 0

    def _x_value(self, source: str, owner: "Player", opp, ctx: dict) -> int:
        if source == "cards_in_hand":           return len(owner.hand)
        if source == "cards_played_this_turn":  return owner.cards_played_this_turn
        if source == "spells_cast_this_turn":   return owner.spells_cast_this_turn
        if source == "deaths_this_turn":        return owner.deaths_this_turn
        if source == "ally_vampiro_count":
            return sum(1 for c in owner.field_creatures if "Vampiro" in c.race)
        if source == "ally_gato_count":
            return sum(1 for c in owner.field_creatures if "Gato" in c.race)
        if source == "owner_graveyard_count":   return len(owner.graveyard)
        if source == "milled_cards_this_turn":  return owner.milled_this_turn
        if source == "enemy_creature_count":
            return len(opp.field_creatures) if opp else 0
        if source == "cafes_served_this_turn":  return owner.cafes_played
        if source == "all_energy_consumed":
            e = owner.total_energy()
            owner.energy = 0; owner.reserve = 0
            return e
        if source == "other_ally_recruta_count":
            return max(0, sum(1 for c in owner.field_creatures if "Recruta" in c.race) - 1)
        return 1

    def _parse_buff(self, s: str, owner: "Player", ctx: dict) -> tuple:
        s = s.replace(" ", "")
        parts = s.split("/")
        def pv(p):
            if "X" in p:
                return self._x_value("cards_played_this_turn", owner, None, ctx)
            try:
                return int(p)
            except:
                return 0
        return pv(parts[0]), (pv(parts[1]) if len(parts) > 1 else 0)

    def _resolve_targets(self, target_type: str, card: "CardInst",
                         owner: "Player", opp: "Player", tag: dict) -> list:
        filt = tag.get("filter", "")
        if target_type == "self":
            return [card] if card in owner.field_creatures else []
        if target_type in ("ally_creature", "any_ally"):
            pool = [c for c in owner.field_creatures if self._matches_filter(c, filt)]
            return [random.choice(pool)] if pool else []
        if target_type in ("enemy_creature", "any_creature", "any"):
            pool = [c for c in opp.field_creatures if self._matches_filter(c, filt)]
            return [min(pool, key=lambda c: c.cur_vit())] if pool else []
        if target_type == "all_ally_creatures":
            return [c for c in owner.field_creatures if self._matches_filter(c, filt)]
        if target_type == "all_enemy_creatures":
            return [c for c in opp.field_creatures if self._matches_filter(c, filt)]
        if target_type == "all_creatures":
            return owner.field_creatures + opp.field_creatures
        if target_type == "adjacent_allies":
            idx = owner.field_creatures.index(card) if card in owner.field_creatures else -1
            return [owner.field_creatures[idx + di]
                    for di in (-1, 1)
                    if 0 <= idx + di < len(owner.field_creatures)]
        if target_type == "attached_creature":
            return [c for c in owner.field_creatures if c.iid == card.linked_to]
        if target_type == "commander":
            if owner.field_creatures:
                return [owner.field_creatures[len(owner.field_creatures) // 2]]
        if target_type == "all_tapped_ally_creatures":
            return [c for c in owner.field_creatures if c.tapped]
        if target_type == "two_constants":
            return owner.all_constants()[:2]
        return []

    def _matches_filter(self, card: "CardInst", filt: str) -> bool:
        if not filt:
            return True
        for part in filt.split(","):
            part = part.strip()
            if part.startswith("class:"):
                if part[6:].lower() not in card.race.lower():
                    return False
            elif part.startswith("race:"):
                if part[5:].lower() not in card.race.lower():
                    return False
            elif part.startswith("name:"):
                if part[5:].lower() not in card.name.lower():
                    return False
            elif part.startswith("name_contains:"):
                if part[14:].lower() not in card.name.lower():
                    return False
            elif part.startswith("cost_lte:"):
                if card.cost > int(part[9:]):
                    return False
            elif part.startswith("cost_gte:"):
                if card.cost < int(part[9:]):
                    return False
            elif part == "tapped":
                if not card.tapped:
                    return False
            elif part == "type:creature":
                if card.card_type != "creature":
                    return False
            elif part == "type:spell":
                if card.card_type != "spell":
                    return False
            elif part == "type:artifact":
                if card.card_type != "artifact":
                    return False
            elif part == "type:terrain":
                if card.card_type != "terrain":
                    return False
            elif part == "has_effect:false":
                if card.effect.strip():
                    return False
            elif part == "not_image":
                if card.card_type == "image":
                    return False
            elif part.startswith("has_last_breath"):
                if "Último Suspiro" not in card.effect and \
                   "Ultimo Suspiro" not in card.effect:
                    return False
        return True

    def _create_image(self, img_id: str, owner: "Player"):
        from .config import MAX_CREATURES
        if owner.field_size() >= MAX_CREATURES:
            return
        data = self.gs.card_pool.get(img_id)
        if data:
            tags = self.gs.tags_db.get(img_id, [])
            img = make_card(data, {img_id: tags})
            img.sick = False
            owner.place_creature(img)
            log(f"🖼️  [{owner.name}] cria imagem '{img.name}'", 3)

    def _investigate(self, deck_owner: "Player", n: int, investigator: "Player"):
        top = deck_owner.deck[:n]
        log(f"🔍 [{investigator.name}] investiga {n} carta(s) de {deck_owner.name}", 3)
        for c in top:
            deck_owner.deck.remove(c)
            if c.cost <= 3:
                deck_owner.deck.insert(0, c)
            else:
                deck_owner.deck.append(c)
            investigator.pistas += 1
        for constant in investigator.spells_field:
            self.resolve_tags(constant, "on_investigate_reveal",
                              investigator, {"revealed_cards": top})

    def _on_owner_lose_life(self, owner: "Player", amount: int):
        for c in owner.field_creatures:
            self.resolve_tags(c, "on_owner_lose_life", owner, {"amount": amount})
        for enc in owner.spells_field:
            self.resolve_tags(enc, "on_owner_lose_life", owner, {"amount": amount})
