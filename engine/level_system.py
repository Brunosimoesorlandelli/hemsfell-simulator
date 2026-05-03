"""
Hemsfell Heroes — Sistema de Level Up
=======================================
Verifica condições e aplica level up para cada herói.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from .config import LEVELUP_COST
from .logger import log

if TYPE_CHECKING:
    from .models import Player


def _dragon_count(player: "Player") -> int:
    return sum(1 for c in player.field_creatures
               if "dragao" in c.race.lower() or "dragon" in c.race.lower())


def check_levelup(player: "Player", gs) -> bool:
    """Retorna True se o jogador atende à condição de level up."""
    if player.leveled_up_this_turn:
        return False
    target = player.hero_level + 1
    if target > 3:
        return False

    hid = player.hero.id

    if hid == "hero_gimble":
        return _dragon_count(player) >= {2: 2, 3: 4}[target]

    if hid == "hero_sr_goblin":
        return player.cards_played_this_turn >= {2: 3, 3: 5}[target]

    if hid == "hero_saymon_primeiro":
        return player.life_lost_times_this_turn >= {2: 3, 3: 5}[target]

    if hid == "hero_colecionador":
        return len(player.graveyard) >= {2: 10, 3: 5}[target]

    if hid == "hero_uruk":
        return player.levelup_counter >= {2: 4, 3: 8}[target]

    if hid == "hero_tifon":
        return player.levelup_counter >= {2: 3, 3: 7}[target]

    if hid == "hero_tesslia":
        return player.levelup_counter >= {2: 3, 3: 6}[target]

    if hid == "hero_quarion":
        names = {c.name for c in player.field_creatures}
        return len(names) >= {2: 2, 3: 4}[target]

    if hid == "hero_rasmus":
        return player.levelup_counter >= {2: 3, 3: 6}[target]

    if hid == "hero_ngoro":
        return player.pistas >= {2: 4, 3: 8}[target]

    if hid == "hero_lider_revolucionario":
        no_eff = sum(1 for c in player.all_constants() if not c.effect.strip())
        return no_eff >= {2: 3, 3: 4}[target]

    if hid == "hero_campeao_natureza":
        total = sum(c.markers.get("action", 0) for c in player.all_constants())
        return total >= {2: 10, 3: 20}[target]

    return False


def apply_levelup(player: "Player", gs):
    """Gasta energia e aplica o novo nível. Não verifica condição."""
    new_level = player.hero_level + 1
    cost      = LEVELUP_COST[new_level]
    if not player.spend(cost):
        return

    player.hero_level           = new_level
    player.leveled_up_this_turn = True
    log(f"🌟 [{player.name}] {player.hero.name} → NÍVEL {new_level}! (-{cost}⚡)", 1)

    hid = player.hero.id

    if hid == "hero_tifon" and new_level == 2:
        player._double_last_breath = True
        log("      ↳ Último Suspiro agora ativa duas vezes.", 2)

    if hid == "hero_tesslia" and new_level == 2:
        cmd = player.commander()
        if cmd and "Atropelar" not in cmd.keywords:
            cmd.keywords.append("Atropelar")
            log(f"      ↳ Comandante '{cmd.name}' recebe Atropelar.", 2)

    if hid == "hero_colecionador":
        player.obscure.extend(player.graveyard)
        player.graveyard.clear()
        log("      ↳ Cemitério banido.", 2)


def try_levelup_phase(player: "Player", gs):
    """Tenta subir de nível se a condição for atendida e houver energia."""
    if player.hero_level >= 3:
        return
    if player.leveled_up_this_turn:
        return
    target = player.hero_level + 1
    if player.total_energy() < LEVELUP_COST[target]:
        return
    if check_levelup(player, gs):
        apply_levelup(player, gs)
