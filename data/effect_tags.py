"""
HEMSFELL HEROES — Sistema de Tags de Efeito
============================================
Cada carta tem uma lista de "effect_tags" que o motor lê para resolver efeitos.
Formato de uma tag:
  {
    "trigger":  quando ativa  (first_act, last_breath, start_of_turn, end_of_turn,
                                on_attack, on_damage, on_death_ally, on_summon_ally,
                                on_summon_enemy, on_spell_cast, on_block, on_tap,
                                passive, fura_fila, on_receive_damage, on_combat_damage,
                                on_ally_leave, on_enter_defense)
    "action":   o que faz     (draw, deal_damage, heal, buff, debuff, search, return_hand,
                               mill, ban, sacrifice, create_image, reduce_cost, grant_keyword,
                               revive, counter, add_energy, add_reserve, win_condition,
                               discard, give_control, destroy, copy_effect, conditional)
    "target":   alvo          (self, ally_creature, enemy_creature, enemy_hero, any_creature,
                               all_enemy_creatures, all_ally_creatures, all_creatures,
                               owner, opponent, top_deck_ally, top_deck_enemy, random_ally,
                               random_enemy, attached_creature)
    "value":    quantidade numérica (int, ou "X" para variável)
    "filter":   filtro opcional (ex: "class:Dragao", "keyword:Voar", "cost_lte:3",
                                     "race:Goblin", "type:spell", "tapped", "has_effect:false")
    "condition": condição opcional (ex: "ally_count_gte:2", "self_life_lte:10",
                                        "cards_in_hand_gte:10", "spell_cast_this_turn_gte:1",
                                        "graveyard_count_gte:5", "keyword_on_stack:fura_fila")
    "keyword":  palavra-chave a conceder (se action=grant_keyword)
    "image_id": id da imagem a criar (se action=create_image)
    "once_per_turn": bool
    "permanent": bool  (efeito dura além do turno)
    "until_end_of_turn": bool
  }
"""

# ─────────────────────────────────────────────────────────────────────────────
# MAPEAMENTO DE TAGS POR CARTA
# Apenas as cartas com efeitos não-triviais precisam de tags.
# Cartas com só keywords (Voar, Furtivo, etc.) não precisam de tags de efeito.
# ─────────────────────────────────────────────────────────────────────────────

EFFECT_TAGS: dict[str, list[dict]] = {

    # ── DRAGÕES ───────────────────────────────────────────────────────────────
    "crt_valorian_pseudo": [
        {"trigger": "passive", "action": "ascension",
         "condition": "markers_gte:10", "image_id": "img_valorian_verdadeiro",
         "description": "Ascensao 10: substitui por Valorian, o Dragao Verdadeiro"}
    ],
    "crt_drelizabeth": [
        {"trigger": "first_act", "action": "search", "target": "owner",
         "filter": "class:Dragao", "value": 1}
    ],
    "crt_wyvern": [
        {"trigger": "on_combat_damage", "action": "deal_damage",
         "target": "adjacent_to_blocker", "value": 1}
    ],
    "crt_smallgui": [
        {"trigger": "first_act", "action": "deal_damage",
         "target": "any_creature", "value": 2, "optional": True}
    ],
    "crt_xarqiroth": [
        {"trigger": "first_act", "action": "draw", "target": "owner", "value": 2,
         "condition": "ally_class_count_gte:2:Dragao"}
    ],
    "crt_breathker": [
        {"trigger": "passive", "action": "buff", "target": "adjacent_allies",
         "value": "0/+1", "permanent": True}
    ],
    "crt_dancadon": [
        {"trigger": "on_death_ally", "action": "survive_with_1hp",
         "filter": "class:Dragao", "once_per_turn": True}
    ],
    "crt_dragao_limo": [
        {"trigger": "last_breath", "action": "deal_damage",
         "target": "all_creatures", "value": 2}
    ],
    "crt_valorian_verdadeiro": [
        {"trigger": "on_summon_ally", "action": "deal_damage",
         "filter": "class:Dragao", "target": "enemy_hero", "value": 2}
    ],

    # ── GOBLINS ───────────────────────────────────────────────────────────────
    "crt_burro_de_carga": [
        {"trigger": "first_act", "action": "reduce_cost",
         "target": "next_card_this_turn", "value": 1}
    ],
    "crt_tira_dentes": [
        {"trigger": "first_act", "action": "return_hand",
         "target": "any_creature", "filter": "cost_lte:3"}
    ],
    "crt_carreta_furacao": [
        {"trigger": "fura_fila", "action": "grant_keyword",
         "target": "self", "keyword": "Investida"},
        {"trigger": "fura_fila", "action": "buff", "target": "self",
         "value": "+1/0", "until_end_of_turn": True}
    ],
    "crt_biriba": [
        {"trigger": "fura_fila", "action": "buff", "target": "self",
         "value": "+X/+X", "x_source": "cards_played_this_turn",
         "until_end_of_turn": True}
    ],
    "crt_bombardeiro_maluco": [
        {"trigger": "fura_fila", "action": "deal_damage",
         "target": "any", "value": 2}
    ],
    "crt_zoiudo": [
        {"trigger": "fura_fila", "action": "destroy",
         "target": "any_creature", "filter": "cost_lte:X",
         "x_source": "cards_played_this_turn"}
    ],
    "crt_fusco": [
        {"trigger": "on_play_fura_fila_ally", "action": "draw",
         "target": "owner", "value": 1}
    ],
    "crt_bafo_fumaca": [
        {"trigger": "first_act", "action": "chain_damage",
         "target": "any_creature", "value": 1,
         "chain_on_kill": True}
    ],
    "crt_bombardeiro_gente_boa": [
        {"trigger": "on_summon_ally", "action": "deal_damage",
         "filter": "race:Goblin", "target": "any", "value": 1}
    ],
    "crt_chamine": [
        {"trigger": "first_act", "action": "search_graveyard",
         "target": "owner", "filter": "name:Suborno", "value": 1},
        {"trigger": "fura_fila", "action": "grant_last_breath",
         "target": "self", "last_breath_action": "return_hand",
         "until_end_of_turn": True}
    ],

    # ── GOBLIN ESPECIAL ───────────────────────────────────────────────────────
    "crt_acumulador": [
        {"trigger": "first_act", "action": "add_markers",
         "target": "self", "value": "X", "x_source": "cards_in_hand",
         "marker_type": "+1/+1"}
    ],
    "crt_jogador_viciado": [
        {"trigger": "on_turn_start", "action": "draw_then_damage",
         "target": "owner", "value": 1,
         "damage_if_creature": True, "once_per_turn": True}
    ],
    "crt_silhueta_noturna": [
        {"trigger": "on_death", "action": "return_to_field",
         "target": "self", "delay": "next_turn_start"}
    ],
    "crt_especialista_escudos": [],  # só Indestrutível (keyword)
    "crt_barreira_martires": [
        {"trigger": "passive", "action": "set_vitality",
         "target": "self", "value": "X", "x_source": "ally_divino_count"}
    ],

    # ── MALORGA ───────────────────────────────────────────────────────────────
    "crt_bestial_filhote": [
        {"trigger": "last_breath", "action": "deal_damage",
         "target": "enemy_hero", "value": 1}
    ],
    "crt_condenado": [
        {"trigger": "last_breath", "action": "buff",
         "target": "ally_creature", "value": "+1/+1", "permanent": True}
    ],
    "crt_bestial": [
        {"trigger": "last_breath", "action": "deal_damage",
         "target": "any_creature", "value": 2}
    ],
    "crt_vingador": [
        {"trigger": "on_death_ally", "action": "buff",
         "target": "self", "value": "+1/0", "until_end_of_turn": True}
    ],
    "crt_conjurador": [
        {"trigger": "first_act", "action": "sacrifice",
         "target": "ally_creature", "then": "draw", "value": 1}
    ],
    "crt_brutamontes": [
        {"trigger": "first_act", "action": "sacrifice_multi",
         "target": "ally_creature", "max": 3,
         "buff_per_sacrifice": "+2/0", "target_self": True}
    ],
    "crt_reanimador": [
        {"trigger": "last_breath", "action": "revive",
         "target": "owner_graveyard", "filter": "cost_lte:2"}
    ],
    "crt_explosivo_malorga": [
        {"trigger": "last_breath", "action": "deal_damage",
         "target": "enemy_hero", "value": "X",
         "x_source": "deaths_this_turn"}
    ],
    "crt_primordial": [
        {"trigger": "on_kill_enemy", "action": "revive",
         "target": "owner_graveyard", "filter": "cost_eq:1"},
        {"trigger": "last_breath", "action": "survive_if_sacrifice",
         "target": "ally_creature"}
    ],

    # ── VAMPIROS ──────────────────────────────────────────────────────────────
    "crt_servo_iniciante": [
        {"trigger": "first_act", "action": "lose_life",
         "target": "owner", "value": 3}
    ],
    "crt_discipulo_sangue": [
        {"trigger": "on_owner_lose_life", "action": "buff",
         "target": "self", "value": "+1/0", "until_end_of_turn": True,
         "once_per_turn": False}
    ],
    "crt_morcego_rastreador": [
        {"trigger": "on_owner_lose_life", "action": "draw",
         "target": "owner", "value": 1, "once_per_turn": True}
    ],
    "crt_o_carniceiro": [
        {"trigger": "first_act", "action": "lose_life",
         "target": "owner", "value": 4}
    ],
    "crt_cobra_dor": [
        {"trigger": "start_of_turn", "action": "lose_life",
         "target": "owner", "value": 2, "then_add_marker": True},
        {"trigger": "on_activate", "action": "heal",
         "target": "owner", "value": "X", "x_source": "self_markers",
         "cost_markers": "X"}
    ],
    "crt_condutor_rasnvia": [
        {"trigger": "first_act", "action": "draw", "target": "owner", "value": 1},
        {"trigger": "first_act_upgrade", "action": "search",
         "filter": "race:Vampiro,cost_gte:4", "value": 1,
         "cost_life": 4}
    ],
    "crt_extrator_lua": [
        {"trigger": "on_summon_enemy", "action": "force_attack",
         "target": "self", "attack_target": "summoned_creature"}
    ],
    "crt_viva_negra": [
        {"trigger": "last_breath", "action": "heal", "target": "owner", "value": 4},
        {"trigger": "on_activate", "action": "grant_keyword",
         "target": "self", "keyword": "Toque da Morte",
         "cost_life": 4, "until_end_of_turn": True}
    ],
    "crt_olhos_sangrentos": [
        {"trigger": "on_activate", "action": "grant_keyword",
         "target": "self", "keyword": "Veloz",
         "cost_life": 2, "until_end_of_turn": True}
    ],
    "crt_dominus_nox": [
        {"trigger": "first_act", "action": "heal", "target": "owner", "value": 4}
    ],
    "crt_lorde_sangue": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "adjacent_allies", "keyword": "Roubo de Vida"}
    ],
    "crt_o_ufanista": [
        {"trigger": "first_act", "action": "discard", "target": "owner", "value": 2},
        {"trigger": "passive", "action": "reduce_cost",
         "target": "self", "value": "X", "x_source": "ally_vampiro_count"}
    ],

    # ── ORDEM / TEMPLÁRIOS ────────────────────────────────────────────────────
    "crt_escudeiro_cruel": [
        {"trigger": "on_receive_damage_survive", "action": "buff",
         "target": "self", "value": "+1/0", "permanent": True}
    ],
    "crt_o_combatente": [
        {"trigger": "passive", "action": "buff",
         "target": "self", "value": "+1/0",
         "condition": "own_turn", "until_end_of_turn": True}
    ],
    "crt_inspetor_desconfiado": [
        {"trigger": "on_spell_cast_enemy", "action": "choice_opponent",
         "choices": [
             {"action": "lose_life", "target": "opponent", "value": 1},
             {"action": "draw", "target": "owner", "value": 1}
         ], "once_per_turn": True}
    ],
    "crt_jjjjjr": [
        {"trigger": "first_act", "action": "ban_until_leave",
         "target": "any_creature"}
    ],
    "crt_duelista_silenciosa": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "self_and_pair", "keyword": "Barreira Magica",
         "condition": "pair_in_field:crt_duelista_silencioso"}
    ],
    "crt_duelista_silencioso": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "self_and_pair", "keyword": "Robusto",
         "condition": "pair_in_field:crt_duelista_silenciosa"}
    ],
    "crt_cavaleiro_negro": [
        {"trigger": "on_kill_enemy", "action": "add_marker",
         "target": "self", "marker_type": "+1/+1",
         "once_per_turn": True}
    ],
    "crt_general_yara": [
        {"trigger": "on_combat_start", "action": "both_look_top",
         "then_choice": ["both_draw", "both_bottom"]}
    ],
    "crt_general_atos": [
        {"trigger": "end_of_turn", "action": "deal_damage",
         "target": "any_player", "value": 3,
         "condition": "no_spell_cast_this_turn"}
    ],
    "crt_general_nilo": [
        {"trigger": "on_kill_in_combat", "action": "attack_again",
         "target": "self", "once_per_turn": True}
    ],
    "crt_mestra_vigia": [],  # só Alerta (keyword)
    "crt_inspetor_aposentado": [
        {"trigger": "on_opponent_draw_extra", "action": "choice_opponent",
         "choices": [
             {"action": "lose_life", "target": "opponent", "value": "X",
              "x_source": "cards_drawn"},
             {"action": "reveal", "target": "drawn_cards"}
         ]}
    ],
    "crt_chefe_guarda": [
        {"trigger": "passive", "action": "double_first_act",
         "filter": "race:Recruta", "target": "ally_recrutas"}
    ],
    "crt_recruta_apaixonado": [
        {"trigger": "first_act", "action": "buff",
         "target": "ally_creature", "value": "+0/+2", "until_end_of_turn": True},
        {"trigger": "first_act", "action": "buff",
         "target": "ally_creature", "filter": "name:Recruta Elegante",
         "value": "+0/+1_bonus", "until_end_of_turn": True}
    ],
    "crt_recruta_elegante": [
        {"trigger": "first_act", "action": "tap",
         "target": "any_creature"}
    ],
    "crt_recruta_exibido": [
        {"trigger": "first_act", "action": "buff",
         "target": "self", "value": "+X/0",
         "x_source": "other_ally_recruta_count",
         "until_end_of_turn": True}
    ],
    "crt_recruta_solidario": [
        {"trigger": "first_act", "action": "buff",
         "target": "any_creature", "value": "+2/0", "until_end_of_turn": True}
    ],
    "crt_recruta_bom_briga": [
        {"trigger": "first_act", "action": "deal_damage",
         "target": "any_creature", "value": 2}
    ],
    "crt_recruta_trapaceira": [
        {"trigger": "first_act", "action": "deal_damage_conditional",
         "target": "any_creature", "value": 1, "bonus_if_tapped": 1}
    ],
    "crt_recruta_pinguço": [
        {"trigger": "first_act", "action": "heal",
         "target": "owner", "value": 2}
    ],
    "crt_recruta_vigilante": [
        {"trigger": "first_act", "action": "return_hand",
         "target": "any_creature", "filter": "tapped"}
    ],

    # ── QUARION / RECRUTAS ────────────────────────────────────────────────────
    "crt_barbaro_cansado": [
        {"trigger": "on_enter_defense", "action": "buff",
         "target": "self", "value": "+4/+4",
         "cost_energy": 1, "until_end_of_combat": True}
    ],
    "crt_assassino_aluguel": [
        {"trigger": "first_act", "action": "draw",
         "target": "owner", "value": 2,
         "then_discard": 2}
    ],
    "crt_escudeiro_fiel": [
        {"trigger": "passive", "action": "redirect_damage",
         "target": "self", "from": "ally_creatures"}
    ],
    "crt_o_informante": [
        {"trigger": "last_breath", "action": "draw",
         "target": "owner", "value": 1}
    ],

    # ── ELEMENTAL / URUK ──────────────────────────────────────────────────────
    "crt_golem_rochedo": [
        {"trigger": "first_act", "action": "grant_keyword",
         "target": "self", "keyword": "Robusto",
         "condition": "spell_cast_this_turn_gte:1"}
    ],
    "crt_manipuladora_arcana": [
        {"trigger": "first_act", "action": "reduce_cost",
         "target": "next_spell_this_turn", "value": 1}
    ],
    "crt_arquimago_sombrio": [
        {"trigger": "on_spell_cast", "action": "buff",
         "target": "self", "value": "+1/0", "until_end_of_turn": True}
    ],
    "crt_athos": [
        {"trigger": "on_spell_cast", "action": "draw",
         "target": "owner", "value": 1, "once_per_turn": True}
    ],
    "crt_feiticeira_espectral": [
        {"trigger": "on_spell_cast", "action": "add_marker",
         "target": "self", "marker_type": "spell"},
        {"trigger": "on_activate", "action": "search",
         "filter": "type:spell,cost_lte:X", "value": 1,
         "cost_markers": "X", "once_per_turn": True}
    ],
    "crt_fenix_cintilante": [
        {"trigger": "last_breath", "action": "search",
         "filter": "name_contains:Fenix", "target": "owner", "value": 1}
    ],

    # ── GATOS / RASMUS ────────────────────────────────────────────────────────
    "crt_morris": [
        {"trigger": "passive", "action": "set_stats",
         "target": "self", "value": "X/X",
         "x_source": "ally_gato_count"}
    ],
    "crt_gato_barista": [
        {"trigger": "first_act", "action": "search",
         "filter": "name_contains:Cafe", "target": "owner", "value": 1}
    ],
    "crt_gato_cachorro": [
        {"trigger": "passive", "action": "buff",
         "target": "self", "value": "+X/0",
         "x_source": "ally_gato_count"},
        {"trigger": "passive", "action": "buff",
         "target": "self", "value": "+0/+X",
         "x_source": "ally_cachorro_count"}
    ],
    "crt_gato_rua": [
        {"trigger": "on_death", "action": "shuffle_into_deck",
         "target": "self"}
    ],
    "crt_gato_afeicoadoo": [
        {"trigger": "first_act", "action": "link_combat",
         "target": "any_creature",
         "description": "Ataques entre os dois sempre se resolvem mutuamente"}
    ],
    "crt_gato_dorminhoco": [
        {"trigger": "first_act", "action": "enter_tapped"},
        {"trigger": "on_cafe_effect", "action": "untap", "target": "self"}
    ],
    "crt_gato_viciado": [
        {"trigger": "on_cafe_effect_ally", "action": "copy_cafe_effect",
         "target": "self"}
    ],

    # ── INVESTIGAÇÃO / NGORO ─────────────────────────────────────────────────
    "crt_cria_ladino": [
        {"trigger": "last_breath", "action": "mill",
         "target": "opponent_deck", "value": 2}
    ],
    "crt_saral": [
        {"trigger": "first_act", "action": "investigate",
         "target": "any_deck", "value": 2}
    ],
    "crt_contrabandista": [
        {"trigger": "first_act", "action": "search",
         "filter": "type:artifact", "target": "owner", "value": 1}
    ],
    "crt_allen_burn": [
        {"trigger": "on_combat_damage_to_hero", "action": "investigate",
         "target": "opponent_deck", "value": 1}
    ],
    "crt_nburnu": [
        {"trigger": "passive", "action": "buff",
         "target": "self", "value": "+X/0",
         "x_source": "milled_cards_this_turn",
         "until_end_of_turn": True}
    ],
    "crt_espio_infiltrado": [
        {"trigger": "on_investigate_reveal_creature", "action": "buff",
         "target": "self", "value": "+1/0", "until_end_of_turn": True}
    ],
    "crt_nmali": [
        {"trigger": "on_investigate_reveal_spell", "action": "mill",
         "target": "opponent_deck", "value": 1}
    ],
    "crt_liaz": [
        {"trigger": "on_investigate_reveal", "action": "grant_keyword_conditional",
         "creature_kw": "Furtivo", "spell_kw": "Barreira Magica",
         "artifact_bonus": "+1/+1",
         "until_end_of_turn": True}
    ],
    "crt_carthana": [
        {"trigger": "on_summon_enemy", "action": "investigate",
         "target": "any_deck", "value": 1}
    ],

    # ── REVOLUCIONÁRIO ────────────────────────────────────────────────────────
    "crt_maria_vai_outras": [
        {"trigger": "passive", "action": "copy_stats",
         "target": "self", "source": "highest_offense_ally"}
    ],
    "crt_revolucionario": [
        {"trigger": "first_act", "action": "ban",
         "target": "enemy_constant", "value": 1}
    ],
    "crt_lider_recluso": [
        {"trigger": "first_act", "action": "search",
         "filter": "has_effect:false,type:creature",
         "target": "owner", "value": 1}
    ],
    "crt_mimico": [
        {"trigger": "on_receive_damage_from_opponent", "action": "remove_own_effects",
         "target": "self"}
    ],

    # ── NATUREZA ─────────────────────────────────────────────────────────────
    "crt_natureza_1": [
        {"trigger": "on_tap", "action": "add_marker",
         "target": "any_card", "marker_type": "action", "value": 1}
    ],
    "crt_natureza_2": [
        {"trigger": "on_marker_add", "action": "add_marker",
         "target": "same_card", "marker_type": "action", "value": 1,
         "description": "Adiciona 1 marcador extra sempre que um marcador de acao seria colocado"}
    ],
    "crt_natureza_3": [
        {"trigger": "on_activate", "action": "untap",
         "target": "any_creature",
         "cost_markers": 2, "marker_type": "action"}
    ],
    "crt_natureza_4": [
        {"trigger": "on_summon_any", "action": "add_marker",
         "target": "self", "marker_type": "action", "value": 1}
    ],
    "crt_natureza_5": [
        {"trigger": "on_combat_phase", "action": "attack_if_has_markers",
         "then_remove_markers": 2, "marker_type": "action"}
    ],
    "crt_natureza_7": [
        {"trigger": "on_tap", "action": "convert_markers",
         "target": "any_creature",
         "from": "action", "to": "+1/+1", "then_ban_end_of_combat": True}
    ],
    "crt_natureza_8": [
        {"trigger": "on_tap", "action": "draw_per_markers",
         "target": "owner", "ratio": 3, "marker_type": "action"}
    ],
    "crt_natureza_9": [
        {"trigger": "on_activate", "action": "grant_keyword",
         "target": "all_ally_creatures", "keyword": "Atropelar",
         "cost_markers": 10, "marker_type": "action",
         "until_end_of_turn": True}
    ],
    "crt_natureza_10": [
        {"trigger": "on_activate", "action": "heal",
         "target": "owner", "value": 1,
         "cost_markers": 3, "marker_type": "action"}
    ],
    "crt_natureza_bomba": [
        {"trigger": "first_act", "action": "double_all_markers"},
        {"trigger": "end_of_turn", "action": "lose_game", "target": "owner"}
    ],

    # ── FEITIÇOS ─────────────────────────────────────────────────────────────
    "spl_ilusao_menor": [
        {"trigger": "on_play", "action": "create_image",
         "image_id": "img_dragao_filhote"}
    ],
    "spl_ilusao": [
        {"trigger": "on_play", "action": "create_image",
         "image_id": "img_dragao_jovem",
         "upgrade_if": "img_dragao_filhote_in_field",
         "replace": "img_dragao_filhote", "cost_reduction": 2}
    ],
    "spl_ilusao_maior": [
        {"trigger": "on_play", "action": "create_image",
         "image_id": "img_dragao_anciao",
         "upgrade_if": "img_dragao_jovem_in_field",
         "replace": "img_dragao_jovem", "cost_reduction": 3}
    ],
    "spl_sabedoria_ancestral": [
        {"trigger": "on_play", "action": "draw", "target": "owner",
         "value": 2, "condition": "ally_class_count_gte:1:Dragao"},
        {"trigger": "on_play", "action": "draw", "target": "owner",
         "value": 1, "condition": "ally_class_count_eq:0:Dragao"}
    ],
    "spl_escama_protetora": [
        {"trigger": "on_play", "action": "buff", "target": "ally_creature",
         "filter": "class:Dragao", "value": "+0/+2", "until_end_of_turn": True}
    ],
    "spl_investida_alada": [
        {"trigger": "on_play", "action": "force_attack",
         "target": "ally_creature", "filter": "class:Dragao,untapped",
         "attack_target": "any_creature"}
    ],
    "spl_bater_asas": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "ally_creature", "filter": "class:Dragao"}
    ],
    "spl_mete_o_pe": [
        {"trigger": "on_play", "action": "return_hand", "target": "ally_creature"},
        {"trigger": "fura_fila_bonus", "action": "reduce_cost",
         "target": "returned_card", "value": 1, "until_end_of_turn": True}
    ],
    "spl_fiado": [
        {"trigger": "on_play", "action": "draw", "target": "owner", "value": 1},
        {"trigger": "fura_fila_bonus", "action": "reduce_cost",
         "target": "self", "value": 1}
    ],
    "spl_conta_casa": [
        {"trigger": "on_play", "action": "reduce_cost",
         "target": "next_non_creature_this_turn", "value": 2}
    ],
    "spl_suborno": [
        {"trigger": "on_play", "action": "add_energy",
         "target": "owner", "value": 1},
        {"trigger": "on_play", "action": "disable_reserve_this_turn"}
    ],
    "spl_bicuda": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": "X",
         "x_source": "cards_played_this_turn"}
    ],
    "spl_tranqueira": [
        {"trigger": "on_play", "action": "tranqueira_roll",
         "x_source": "cards_played_this_turn"}
    ],
    "spl_combado": [
        {"trigger": "on_play", "action": "register_trigger",
         "on": "goblin_leave_field", "action2": "add_energy",
         "target": "owner", "value": 1, "until_end_of_turn": True}
    ],
    "spl_pinga": [
        {"trigger": "on_play", "action": "revive",
         "target": "owner_graveyard", "filter": "race:Goblin",
         "dies_end_of_turn": True},
        {"trigger": "fura_fila_bonus", "action": "grant_keyword",
         "target": "revived", "keyword": "Investida"}
    ],
    "spl_orbe_cromatico": [
        {"trigger": "on_play", "action": "elemental_damage",
         "target": "any_creature", "value": 1,
         "element": "choice"}
    ],
    "spl_punho_sismico": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": 1, "max_targets": 2,
         "element": "Terra"},
        {"trigger": "on_play", "action": "next_fire_gets_suffix",
         "suffix": "Sufocado"}
    ],
    "spl_tempestade_areia": [
        {"trigger": "on_play", "action": "debuff",
         "target": "all_enemy_creatures", "value": "-2/0",
         "until_turn_start": True, "element": "Terra"},
        {"trigger": "on_play", "action": "next_fire_gets_suffix",
         "suffix": "Sufocado"}
    ],
    "spl_terremoto": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "all_creatures", "value": "X",
         "x_source": "enemy_creature_count", "element": "Terra"},
        {"trigger": "on_play", "action": "next_fire_gets_suffix",
         "suffix": "Sufocado"}
    ],
    "spl_levantar_mar": [
        {"trigger": "on_play", "action": "create_image",
         "image_id": "img_clone_agua", "element": "Agua"},
        {"trigger": "on_play", "action": "next_air_gets_suffix",
         "suffix": "Atordoado"}
    ],
    "spl_bolha_protetora": [
        {"trigger": "on_play", "action": "negate_next_damage",
         "target": "owner_or_ally", "element": "Agua"},
        {"trigger": "on_play", "action": "next_air_gets_suffix",
         "suffix": "Atordoado"}
    ],
    "spl_nevasca": [
        {"trigger": "on_play", "action": "apply_status",
         "target": "all_enemy_creatures", "status": "Congelado",
         "element": "Agua", "bonus_if_already": "deal_damage:2"},
        {"trigger": "on_play", "action": "next_air_gets_suffix",
         "suffix": "Atordoado"}
    ],
    "spl_alta_voltagem": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": 1,
         "bonus_per_adjacent": 1, "element": "Ar"},
        {"trigger": "on_play", "action": "next_water_gets_suffix",
         "suffix": "Congelado"}
    ],
    "spl_nuvem_esmagadora": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "any_creature", "element": "Ar"},
        {"trigger": "on_play", "action": "next_creature_costs_more",
         "target": "opponent", "value": 1},
        {"trigger": "on_play", "action": "next_water_gets_suffix",
         "suffix": "Congelado"}
    ],
    "spl_tufao": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "all_creatures", "element": "Ar"}
    ],
    "spl_obliterar": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": "X",
         "x_source": "all_energy_consumed", "element": "Fogo"}
    ],
    "spl_lanca_ardente": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": 2, "element": "Fogo"},
        {"trigger": "on_play", "action": "next_earth_gets_suffix",
         "suffix": "Imobilizado"}
    ],
    "spl_bola_de_fogo": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": 4, "element": "Fogo"},
        {"trigger": "on_play", "action": "deal_damage",
         "target": "adjacent_to_target", "value": 1},
        {"trigger": "on_play", "action": "next_earth_gets_suffix",
         "suffix": "Imobilizado"}
    ],
    "spl_eclipse_final": [
        {"trigger": "on_play", "action": "deal_damage_repeat",
         "target": "any", "value": 2,
         "repeat_x": "spells_cast_this_turn"}
    ],
    "spl_invocar_elemental": [
        {"trigger": "on_play", "action": "create_image_choice",
         "choices": {
             "Fogo": "img_ignis", "Agua": "img_terron",
             "Terra": "img_undaris", "Ar": "img_zephyrus"
         }}
    ],
    "spl_ritual_ametista": [
        {"trigger": "on_play", "action": "sacrifice", "target": "ally_creature"},
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": 2}
    ],
    "spl_marcha_condenados": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "owner_graveyard",
         "filter": "has_last_breath:true", "value": 2}
    ],
    "spl_tremor_fenda": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "all_creatures", "value": 3}
    ],
    "spl_saliva_acida": [
        {"trigger": "on_play", "action": "grant_keyword",
         "target": "ally_creature", "filter": "race:Malorga",
         "keyword": "Toque da Morte", "until_end_of_turn": True}
    ],
    "spl_ataque_temerario": [
        {"trigger": "on_play", "action": "buff",
         "target": "any_creature", "value": "+2/0", "until_end_of_turn": True}
    ],
    "spl_danca_macabra": [
        {"trigger": "on_play", "action": "apply_status",
         "target": "any_creature", "status": "Vampirizado",
         "until_end_of_turn": True}
    ],
    "spl_nascer_sol": [
        {"trigger": "on_play", "action": "destroy",
         "target": "any_creature", "filter": "race:Vampiro"},
        {"trigger": "on_play", "action": "heal",
         "target": "owner", "value": 4}
    ],
    "spl_despertar_noite": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "all_creatures", "value": 2,
         "lifesteal": True}
    ],
    "spl_mordida_fatal": [
        {"trigger": "on_play", "action": "deal_damage",
         "target": "any_creature", "value": 3,
         "lifesteal": True, "if_kills_return_to_bottom": True}
    ],
    "spl_tumulo_sacrificio": [
        {"trigger": "on_play", "action": "next_creature_costs_life"}
    ],
    "spl_jogo_justo": [
        {"trigger": "on_play", "action": "tap",
         "target": "ally_creature", "value": 3},
        {"trigger": "on_play", "action": "draw", "target": "owner", "value": 2}
    ],
    "spl_chave_rara": [
        {"trigger": "on_play", "action": "search",
         "filter": "type:terrain", "target": "owner",
         "put_in_field": True, "value": 1}
    ],
    "spl_epifania": [
        {"trigger": "on_play", "action": "draw",
         "target": "owner", "value": "X",
         "x_source": "owner_graveyard_count"}
    ],
    "spl_nao_disse_por_favor": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "any_creature"}
    ],
    "spl_chinela_mae": [
        {"trigger": "on_play", "action": "counter", "target": "any_card"}
    ],
    "spl_aqui_nao": [
        {"trigger": "on_play", "action": "destroy",
         "target": "attacking_creature", "filter": "cost_lte:4"}
    ],
    "spl_sepultar": [
        {"trigger": "on_play", "action": "force_discard",
         "target": "opponent", "value": 1,
         "player_chooses": True}
    ],
    "spl_divinus_amp": [
        {"trigger": "on_play", "action": "ban_own",
         "filter": "color:Divino", "max": 3,
         "then_draw": 2, "per_banned": True}
    ],
    "spl_desenterrar": [
        {"trigger": "on_play", "action": "revive",
         "target": "owner_graveyard",
         "filter": "cost_lte:5,type:creature"}
    ],
    "spl_recomeco": [
        {"trigger": "on_play", "action": "shuffle_graveyard_into_deck"},
        {"trigger": "on_play", "action": "ban", "target": "self"}
    ],
    "spl_nada_se_cria": [
        {"trigger": "on_play", "action": "trigger_first_act",
         "target": "any_creature"}
    ],
    "spl_frenesi": [
        {"trigger": "on_play", "action": "grant_extra_attack",
         "target": "any_creature", "value": 1,
         "then_destroy_end_of_turn": True}
    ],
    "spl_punicao_divina": [
        {"trigger": "on_play", "action": "destroy",
         "target": "any_creature", "filter": "tapped"},
        {"trigger": "on_play", "action": "heal",
         "target": "owner", "value": "X",
         "x_source": "destroyed_card_cost"}
    ],
    "spl_escudo_anulador": [
        {"trigger": "on_play", "action": "negate_effect",
         "target": "any_card", "until_end_of_turn": True},
        {"trigger": "on_play", "action": "draw",
         "target": "affected_controller", "value": 1}
    ],
    "spl_vinganca": [
        {"trigger": "on_play", "action": "destroy",
         "target": "any_creature",
         "condition": "dealt_damage_to_owner_or_ally_this_turn"}
    ],
    "spl_condenar": [
        {"trigger": "on_play", "action": "register_trigger",
         "on": "end_of_turn_if_didnt_attack",
         "action2": "destroy", "target": "target_creature"}
    ],
    "spl_castigo": [
        {"trigger": "on_play", "action": "destroy",
         "target": "any_creature",
         "condition": "was_targeted_by_effect_this_turn"}
    ],
    "spl_bater_retirada": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "ally_creature", "filter": "cost_lte:3"}
    ],
    "spl_recrutas_ao_resgate": [
        {"trigger": "on_play", "action": "fill_field_recrutas",
         "optional_sacrifice_first": True}
    ],
    "spl_juramento_solene": [
        {"trigger": "on_play", "action": "heal",
         "target": "owner", "value": "X",
         "x_source": "tapped_creature_count_field", "multiplier": 2}
    ],
    "spl_infusao_proibida": [
        {"trigger": "on_play", "action": "buff",
         "target": "any_creature", "value": "+X/+X",
         "x_source": "spells_played_this_turn",
         "until_end_of_turn": True}
    ],
    "spl_dzimo": [
        {"trigger": "on_play", "action": "redirect_self_target",
         "to": "ally_creature"}
    ],
    "spl_a_dama_ferro": [
        {"trigger": "on_play", "action": "purge_own_spells"},
        {"trigger": "on_play", "action": "create_image",
         "image_id": "img_tesslia_mao_ferro", "once_per_game": True}
    ],
    "spl_medida_desesperada": [
        {"trigger": "on_play", "action": "buff",
         "target": "all_ally_creatures", "value": "+1/+1",
         "at_end_of_turn": True},
        {"trigger": "on_play", "action": "buff",
         "target": "all_ally_creatures", "value": "+2/+2",
         "condition": "owner_life_lte:10", "at_end_of_turn": True}
    ],
    "spl_informante_fofoqueiro": [
        {"trigger": "on_play", "action": "draw",
         "target": "owner", "value": 4,
         "damage_per_non_creature": 3}
    ],
    "spl_tortura_coletiva": [
        {"trigger": "on_play", "action": "ping_until_two_die",
         "targets": 2, "from_each_player": True}
    ],
    "spl_contramedida": [
        {"trigger": "on_play", "action": "destroy",
         "target": "any_creature", "value": 2}
    ],
    "spl_logistica": [
        {"trigger": "on_play", "action": "search",
         "filter": "type:creature", "target": "owner", "value": 2},
        {"trigger": "on_play", "action": "put_bottom",
         "target": "owner_hand", "value": 2},
        {"trigger": "on_play", "action": "disable_draw_this_turn"}
    ],
    "spl_sua_escolha": [
        {"trigger": "on_play", "action": "choice_opponent",
         "choices": [
             {"action": "draw", "target": "owner", "value": 2},
             {"action": "mill", "target": "opponent_deck", "value": 2}
         ]}
    ],
    "spl_queima_arquivos": [
        {"trigger": "on_play", "action": "set_flag",
         "flag": "next_2_archived_go_to_graveyard"}
    ],
    "spl_cafe_expresso": [
        {"trigger": "on_play", "action": "untap", "target": "any_creature",
         "cafe": True},
        {"trigger": "on_play", "action": "buff",
         "target": "same_creature", "value": "+1/+1",
         "until_end_of_turn": True}
    ],
    "spl_cafe_pingado": [
        {"trigger": "on_play", "action": "negate_next_damage",
         "target": "any_creature", "value": 1, "cafe": True}
    ],
    "spl_cafe_com_leite": [
        {"trigger": "on_play", "action": "negate_next_damage",
         "target": "any_creature", "full": True, "cafe": True}
    ],
    "spl_cappuccino": [
        {"trigger": "on_play", "action": "buff",
         "target": "any_creature", "value": "+1/+1",
         "until_turn_start": True, "cafe": True},
        {"trigger": "on_play", "action": "grant_effect",
         "target": "same_creature",
         "effect": "on_combat_damage_tap_enemy_no_untap"}
    ],
    "spl_cafe_mocha": [
        {"trigger": "on_play", "action": "draw", "target": "owner",
         "value": 1, "cafe": True},
        {"trigger": "on_play", "action": "draw", "target": "owner",
         "value": 1, "condition": "cafe_played_this_turn_gte:1"}
    ],
    "spl_cafe_latte": [
        {"trigger": "on_play", "action": "return_hand",
         "target": "any_creature", "cafe": True},
        {"trigger": "on_play", "action": "grant_flag",
         "target": "returned_card", "flag": "no_summoning_sick_on_recast",
         "filter": "race:Gato"}
    ],
    "spl_cafe_filtrado": [
        {"trigger": "on_play", "action": "buff",
         "target": "any_creature", "value": "+5/+5",
         "until_turn_start": True,
         "no_untap_next_maintenance": True, "cafe": True}
    ],
    "spl_cafe_duplo": [
        {"trigger": "on_play", "action": "buff",
         "target": "any_creature", "value": "+1/+1",
         "count": 2, "until_turn_start": True, "cafe": True}
    ],
    "spl_ritual_barista": [
        {"trigger": "on_play", "action": "cafe_ritual",
         "x_source": "cafes_served_this_turn",
         "choices_per_cafe": ["draw:1", "tap_creature", "buff_creature:+2/+2"]}
    ],
    "spl_cafe_blend": [
        {"trigger": "on_play", "action": "double_next_cafe_effect"}
    ],
    "spl_tentar_de_novo": [
        {"trigger": "on_play", "action": "discard_hand_draw_same"}
    ],
    "spl_compra_estrategica": [
        {"trigger": "on_play", "action": "draw_then_conditional",
         "target": "owner", "value": 1,
         "creature": "deal_damage:cost", "spell": "repeat_effect"}
    ],
    "spl_cafe_preto": [
        {"trigger": "on_play", "action": "add_marker",
         "target": "any_creature", "marker_type": "+5/+5",
         "until_turn_start": True,
         "no_untap_next_maintenance": True, "cafe": True}
    ],
    "spl_cafe_descafeinado": [
        {"trigger": "on_play", "action": "add_marker",
         "target": "any_creature", "marker_type": "+2/+2",
         "until_turn_start": True, "cafe": True}
    ],
    "spl_cafe_expresso_duplo": [
        {"trigger": "on_play", "action": "buff",
         "target": "any", "value": "+0/+2", "cafe": True}
    ],
    "spl_descarte_estrategico": [
        {"trigger": "on_play", "action": "force_random_discard",
         "target": "opponent",
         "creature": "deal_damage:cost:any",
         "spell": "force_discard:opponent:1",
         "instant": "play_card",
         "terrain": "end_turn_opponent"}
    ],
    "spl_cold_brew": [
        {"trigger": "on_play", "action": "exile_until_turn_start",
         "target": "any_creature", "returns_tapped": True, "cafe": True}
    ],
    "spl_infusao_cafe": [
        {"trigger": "on_play", "action": "double_marker_generation",
         "until_end_of_turn": True, "cafe": True}
    ],
    "spl_chorinho": [
        {"trigger": "on_play", "action": "draw", "target": "owner", "value": 1,
         "condition": "only_ordem_creatures_and_drew_gte:2"}
    ],
    "spl_fuga": [
        {"trigger": "on_play", "action": "return_hand", "target": "any_creature"},
        {"trigger": "on_play", "action": "transfer_artifact",
         "target": "returned_card_artifact", "to": "opponent_choice",
         "cost_reduction": "all"}
    ],
    "spl_sopro_natural": [
        {"trigger": "on_play", "action": "revive",
         "target": "owner_graveyard", "value": 3,
         "condition": "graveyard_count_gte:5",
         "then_ban_graveyard": True}
    ],

    # ── ARTEFATOS ─────────────────────────────────────────────────────────────
    "art_coracao_rubi": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+0/+2"},
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Defensor",
         "condition": "attached_class:Dragao"}
    ],
    "art_anel_esmeralda": [
        {"trigger": "on_tap_destroy_self", "action": "increase_max_energy",
         "target": "owner", "value": 1}
    ],
    "art_garras_leviata": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Voar"},
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+2/0",
         "condition": "attached_class:Dragao"}
    ],
    "art_anel_safira": [
        {"trigger": "on_tap_destroy_self", "action": "fill_reserve",
         "target": "owner"}
    ],
    "art_anel_ametista": [
        {"trigger": "on_tap", "action": "add_energy",
         "target": "owner", "value": 1,
         "condition": "ally_caos_constant_exists"}
    ],
    "art_anel_rubi": [
        {"trigger": "on_tap_destroy_self", "action": "add_energy",
         "target": "owner", "value": 2, "exceed_max": True},
        {"trigger": "on_play", "action": "set_flag",
         "flag": "no_energy_increase_next_turn"}
    ],
    "art_anel_diamante": [
        {"trigger": "on_tap_two_creatures", "action": "add_energy",
         "target": "owner", "value": 2}
    ],
    "art_poo_da_ira": [
        {"trigger": "on_tap_destroy_self", "action": "buff",
         "target": "any_creature", "value": "+4/+4",
         "destroy_target_end_of_turn": True}
    ],
    "art_anti_artefato": [
        {"trigger": "on_tap_destroy_self", "action": "destroy",
         "target": "any_artifact", "unstoppable": True}
    ],
    "art_pergaminho_estabilizar": [
        {"trigger": "on_activate_destroy", "action": "grant_effect",
         "target": "all_ally_creatures",
         "effect": "on_tap_add_reserve:1",
         "cost_energy": 1, "until_end_of_turn": True}
    ],
    "art_pacto_sangue": [
        {"trigger": "on_tap", "action": "buff",
         "target": "attached_creature", "value": "+2/0",
         "cost_life": 2, "until_end_of_turn": True}
    ],
    "art_silencio_ensurdecedor": [
        {"trigger": "passive", "action": "apply_status",
         "target": "any_constant", "status": "Sufocado"},
        {"trigger": "end_of_turn", "action": "pay_or_destroy",
         "target": "self", "cost_life": 2}
    ],
    "art_anel_casamento": [
        {"trigger": "on_play", "action": "link_fate",
         "target1": "attached_creature", "target2": "any_other_creature"}
    ],
    "art_correntes_purificadoras": [
        {"trigger": "on_targeted_by_effect", "action": "draw",
         "target": "owner", "value": 1},
        {"trigger": "on_would_go_to_graveyard", "action": "ban", "target": "self"}
    ],
    "art_machado_indomavel": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Indomavel"},
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+3/0"}
    ],
    "art_armadura_ferro": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Robusto"}
    ],
    "art_aegis_chama": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Defensor_5"},
        {"trigger": "on_would_die_in_combat", "action": "sacrifice_instead",
         "target": "ally_creature", "once_per_turn": True}
    ],
    "art_escudo_vingativo": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+0/+2"},
        {"trigger": "on_attached_leave_field", "action": "destroy",
         "target": "enemy_creature", "filter": "tapped"}
    ],
    "art_caneca_sorte": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+2/-1"},
        {"trigger": "passive", "action": "immune_to_spell_damage",
         "target": "attached_creature",
         "condition": "attached_name:Recruta Pinguço"}
    ],
    "art_dialogo": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+3/+2"},
        {"trigger": "on_kill", "action": "buff",
         "target": "attached_creature", "value": "+1/0",
         "condition": "attached_name:Recruta Bom de Briga",
         "permanent": True}
    ],
    "art_estandarte_ordem": [
        {"trigger": "passive", "action": "suporte",
         "target": "attached_creature", "value": "+1/+1"},
        {"trigger": "passive", "action": "suporte",
         "target": "attached_creature", "value": "+2/+2",
         "condition": "attached_name:Recruta Solidario"}
    ],
    "art_escudo_duro": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+1/+4"},
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Defensor_2",
         "condition": "attached_name:Recruta Apaixonado"}
    ],
    "art_gran_finale": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+2/+2"},
        {"trigger": "on_die_in_combat",
         "action": "return_hand_both",
         "targets": ["attached_creature", "winner"],
         "condition": "attached_name:Recruta Elegante"}
    ],
    "art_fatiadora": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "-2/0"},
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Atropelar"}
    ],
    "art_luvas_larapio": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Atropelar"},
        {"trigger": "on_combat_damage_to_hero", "action": "mill",
         "target": "opponent_deck", "value": "X",
         "x_source": "damage_dealt"}
    ],
    "art_adaga_ametista": [
        {"trigger": "passive", "action": "buff",
         "target": "attached_creature", "value": "+2/0"},
        {"trigger": "on_deal_damage", "action": "lose_life",
         "target": "owner", "value": 1}
    ],
    "art_manto_invisibilidade": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "attached_creature", "keyword": "Furtivo"}
    ],
    "art_arac_need_you": [
        {"trigger": "on_tap", "action": "grant_unblockable_by_non_flyers",
         "target": "attached_creature",
         "condition": "other_ally_natureza_constant_exists"}
    ],
    "art_natureza_2_wip": [
        {"trigger": "passive", "action": "reduce_cost",
         "target": "all_ally_creatures", "value": 1},
        {"trigger": "end_of_turn", "action": "deal_damage",
         "target": "owner", "value": 1}
    ],

    # ── ENCANTOS ─────────────────────────────────────────────────────────────
    "enc_trabalho_honesto": [
        {"trigger": "start_of_turn", "action": "add_energy",
         "target": "owner", "value": 1}
    ],
    "enc_planto_cura": [
        {"trigger": "on_receive_damage", "action": "heal",
         "target": "owner", "value": 1}
    ],
    "enc_totem_cinzas": [
        {"trigger": "on_death_ally", "action": "add_marker",
         "target": "self", "marker_type": "soul"},
        {"trigger": "on_activate", "action": "revive",
         "target": "owner_graveyard", "value": 1,
         "cost_markers": "cost_x2", "marker_type": "soul"}
    ],
    "enc_estandarte_runa": [
        {"trigger": "on_activate", "action": "trigger_last_breath",
         "target": "top_of_graveyard", "once_per_turn": True}
    ],
    "enc_maestria_elemental": [
        {"trigger": "on_play", "action": "create_image_choice",
         "choices": {
             "Fogo": "img_maestria_piromancia",
             "Agua": "img_maestria_hidromancia",
             "Terra": "img_maestria_geomancia",
             "Ar": "img_maestria_aeromancia"
         }}
    ],
    "enc_maquina_expresso": [
        {"trigger": "on_tap", "action": "choice",
         "choices": [
             {"action": "add_markers", "target": "self",
              "marker_type": "coffee", "value": "X+1", "cost_energy": "X"},
             {"action": "heal_targets", "target": "any",
              "value": "X", "x_source": "self_markers",
              "cost_markers": "all", "counts_as_cafe": True}
         ]}
    ],
    "enc_hora_cafe": [
        {"trigger": "on_cafe_played", "action": "draw",
         "target": "owner", "value": 1}
    ],
    "enc_prestidigitacao": [
        {"trigger": "on_draw", "action": "option_draw_from_bottom",
         "target": "owner"}
    ],
    "enc_circulo_protecao": [
        {"trigger": "passive", "action": "grant_keyword",
         "target": "all_tapped_ally_creatures", "keyword": "Barreira Magica"}
    ],
    "enc_castelo_carmesim": [
        {"trigger": "on_owner_lose_life", "action": "escalating_effect",
         "steps": [
             {"step": 1, "action": "draw", "value": 1},
             {"step": 2, "action": "deal_damage", "target": "any", "value": 2},
             {"step": 3, "action": "heal", "target": "owner", "value": 2},
             {"step": "4+", "action": "heal", "target": "owner", "value": 1}
         ]}
    ],

    # ── TERRENOS ─────────────────────────────────────────────────────────────
    "ter_alpes_draconicos": [
        {"trigger": "on_death_ally", "action": "create_image",
         "filter": "class:Dragao,not_image", "image_id": "img_dragao_filhote"}
    ],
    "ter_parque_goblin": [
        {"trigger": "passive", "action": "buff_goblins_by_card_count",
         "thresholds": {
             "4": {"keyword": "Atropelar"},
             "5": {"keyword": "Investida"},
             "6": {"last_breath": "deal_damage:1"},
             "7": {"keyword": "Toque da Morte"}
         }, "until_end_of_turn": True}
    ],
    "ter_mudrasovna": [
        {"trigger": "passive", "action": "reduce_cost",
         "target": "all_spells_owner_turn", "value": 1}
    ],
    "ter_cemiterio_amaldioado": [
        {"trigger": "on_death_ally", "action": "create_image",
         "filter": "not_image", "image_id": "img_fantasma_1_1_voar"}
    ],
    "ter_altar_carnificina": [
        {"trigger": "on_death_ally", "action": "grant_keyword",
         "target": "any_ally_creature", "keyword": "Toque da Morte",
         "until_end_of_turn": True, "once_per_turn": True}
    ],
    "ter_arte_guerra": [
        {"trigger": "on_combat_start", "action": "allow_repositioning",
         "both_players": True}
    ],
    "ter_torneio_campoes": [
        {"trigger": "passive", "action": "allow_hero_combat",
         "hero_offense": "level", "if_hero_dies": "owner_loses"}
    ],
    "ter_saideira_recrutas": [
        {"trigger": "on_ally_leave_field", "action": "trigger_first_act",
         "filter": "race:Recruta"}
    ],
    "ter_cafe_do_tempo": [
        {"trigger": "start_of_turn", "action": "create_image",
         "image_id": "img_gato_multidimensional"}
    ],
    "ter_base_investigacao": [
        {"trigger": "on_investigate_reveal", "action": "conditional_effect",
         "creature": {"action": "mill", "target": "opponent_deck", "value": 1},
         "spell": {"action": "deal_damage", "target": "enemy_creature", "value": 1},
         "artifact": {"action": "add_reserve", "target": "owner", "value": 1},
         "enchant": {"action": "draw", "target": "owner", "value": 1},
         "terrain": {"action": "discard", "target": "opponent", "value": 1}}
    ],
    "ter_recrutamento_revolucionario": [
        {"trigger": "start_of_turn_both", "action": "draw",
         "target": "current_player", "value": 1,
         "condition": "controls_no_effect_creature"}
    ],

    # ── HERÓIS ───────────────────────────────────────────────────────────────
    "hero_gimble": [
        {"trigger": "end_of_turn", "action": "heal",
         "target": "owner", "value": 1,
         "condition": "ally_class_count_gte:2:Dragao", "level": 1},
        {"trigger": "on_activate", "action": "untap",
         "target": "ally_creature", "filter": "class:Dragao",
         "once_per_turn": True, "level": 2},
        {"trigger": "start_of_turn", "action": "add_marker",
         "target": "all_ally_dragao", "marker_type": "+1/+1",
         "level": 3}
    ],
    "hero_sr_goblin": [
        {"trigger": "on_goblin_leave", "action": "draw",
         "target": "owner", "value": 1,
         "once_per_turn": True, "level": 1},
        {"trigger": "start_of_turn", "action": "draw",
         "target": "owner", "value": 1, "level": 2},
        {"trigger": "on_first_goblin_summon_turn", "action": "reduce_cost",
         "target": "first_goblin", "value": "all", "level": 3}
    ],
    "hero_saymon_primeiro": [
        {"trigger": "on_activate", "action": "deal_damage",
         "target": "any", "value": 1,
         "cost_life": 2, "once_per_turn": True, "level": 1},
        {"trigger": "passive", "action": "prevent_self_death_from_own_effects",
         "level": 2},
        {"trigger": "on_activate", "action": "grant_keyword",
         "target": "any_creature", "keyword": "Roubo de Vida",
         "cost_life": 2, "once_per_turn": True, "level": 3}
    ],
    "hero_uruk": [
        {"trigger": "end_of_turn", "action": "element_bonus",
         "source": "last_spell_element",
         "Ar": {"action": "add_energy", "value": 1},
         "Fogo": {"action": "deal_damage", "target": "any", "value": 1},
         "Terra": {"action": "draw", "value": 1},
         "Agua": {"action": "heal", "value": 1}, "level": 1},
        {"trigger": "on_last_spell_cast", "action": "duplicate_spell",
         "level": 2},
        {"trigger": "on_first_spell_cast_turn", "action": "reduce_cost",
         "target": "first_spell", "value": 1, "level": 3}
    ],
    "hero_tifon": [
        {"trigger": "on_death_ally", "action": "draw",
         "target": "owner", "value": 1,
         "once_per_turn": True, "level": 1},
        {"trigger": "passive", "action": "double_last_breath",
         "level": 2},
        {"trigger": "on_last_breath_death_ally", "action": "deal_damage",
         "target": "enemy_hero", "value": 1, "level": 3}
    ],
    "hero_tesslia": [
        {"trigger": "passive", "action": "commander_buff",
         "target": "center_creature", "value": "+2/0", "level": 1},
        {"trigger": "passive", "action": "grant_keyword",
         "target": "commander", "keyword": "Atropelar",
         "additional_buff": "+1/0", "level": 2},
        {"trigger": "on_commander_would_die", "action": "sacrifice_instead",
         "target": "ally_creature", "once_per_turn": True, "level": 3}
    ],
    "hero_quarion": [
        {"trigger": "on_first_death_ally_turn", "action": "return_hand",
         "target": "dead_creature", "level": 1},
        {"trigger": "on_first_act_triggered", "action": "draw",
         "target": "owner", "value": 1,
         "once_per_turn": True, "level": 2},
        {"trigger": "on_first_first_act_creature_turn", "action": "double_first_act",
         "level": 3}
    ],
    "hero_rasmus": [
        {"trigger": "end_of_turn", "action": "add_reserve",
         "target": "owner", "value": "X",
         "x_source": "cafes_played_this_turn",
         "max_x": 3, "level": 1},
        {"trigger": "on_cafe_on_gato", "action": "double_cafe_effect",
         "level": 2},
        {"trigger": "on_first_cafe_turn", "action": "put_bottom",
         "target": "first_cafe_card", "level": 3}
    ],
    "hero_ngoro": [
        {"trigger": "start_of_turn", "action": "investigate",
         "target": "any_deck", "value": 1, "level": 1},
        {"trigger": "on_investigate", "action": "gain_pista",
         "value": 1, "level": 1},
        {"trigger": "on_investigate", "action": "spend_pistas_choice",
         "cost": 2, "choices": [
             {"action": "draw", "value": 1},
             {"action": "mill", "target": "opponent_deck", "value": 2}
         ], "level": 2},
        {"trigger": "on_activate", "action": "grant_keyword",
         "target": "ally_creature", "keyword": "Furtivo",
         "cost_pistas": 3, "until_end_of_turn": True, "level": 3}
    ],
    "hero_lider_revolucionario": [
        {"trigger": "on_first_no_effect_creature_turn",
         "action": "reduce_cost", "target": "first_no_effect_creature",
         "value": 1, "level": 1},
        {"trigger": "on_activate", "action": "apply_status",
         "target": "any_card", "status": "Sufocado",
         "until_turn_start": True, "once_per_turn": True, "level": 2},
        {"trigger": "on_activate", "action": "buff",
         "target": "ally_creature", "filter": "has_effect:false",
         "value": "+1/+1", "until_end_of_turn": True, "level": 3}
    ],
    "hero_campeao_natureza": [
        {"trigger": "on_activate", "action": "add_marker",
         "target": "two_constants", "marker_type": "action",
         "value": 2, "once_per_turn": True, "level": 1},
        {"trigger": "on_activate", "action": "tap",
         "target": "any_creature",
         "cost_markers": 4, "marker_type": "action",
         "until_turn_start": True, "level": 2},
        {"trigger": "passive", "action": "win_condition",
         "condition": "any_card_markers_gte:50", "level": 3}
    ],
}
