"""
Hemsfell Heroes — Loader
=========================
Carrega cartas do JSON, constrói instâncias e monta decks dos heróis.
"""

from __future__ import annotations
import json
import random
import importlib
from .models import CardInst
from .logger import log
from .config import CARDS_PATH, TAGS_MODULE


# ─────────────────────────────────────────────
#  LEITURA DO JSON
# ─────────────────────────────────────────────

def load_data(path: str = CARDS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_tags() -> dict:
    """Importa o dicionário EFFECT_TAGS do módulo data.effect_tags."""
    try:
        mod = importlib.import_module(TAGS_MODULE)
        return mod.EFFECT_TAGS
    except (ImportError, AttributeError):
        # fallback: tenta importar diretamente se rodando fora do pacote
        try:
            from data.effect_tags import EFFECT_TAGS  # type: ignore
            return EFFECT_TAGS
        except ImportError:
            log("⚠️  effect_tags não encontrado — efeitos desativados")
            return {}


# ─────────────────────────────────────────────
#  CONSTRUÇÃO DE CARTAS
# ─────────────────────────────────────────────

def build_card_pool(data: dict) -> dict:
    """Retorna dict {id: raw_dict} para todas as cartas do JSON."""
    pool = {}
    for section in ["heroes", "creatures", "spells", "artifacts",
                    "enchants", "terrains", "images"]:
        for c in data.get(section, []):
            pool[c["id"]] = c
    return pool


def make_card(raw: dict, tags_db: dict) -> CardInst:
    """Constrói uma CardInst a partir do raw dict do JSON."""
    cid  = raw["id"]
    tags = tags_db.get(cid, [])
    return CardInst(
        id         = cid,
        name       = raw["name"],
        card_type  = raw.get("type", "creature"),
        color      = raw.get("color", "Neutro"),
        cost       = raw.get("cost", 0),
        offense    = raw.get("offense", 0),
        vitality   = raw.get("vitality", 0),
        base_off   = raw.get("offense", 0),
        base_vit   = raw.get("vitality", 0),
        keywords   = list(raw.get("keywords", [])),
        effect     = raw.get("effect", ""),
        effect_tags= tags,
        race       = raw.get("race", ""),
        abilities  = raw.get("abilities", {}),
        subtype    = raw.get("subtype", ""),
    )


# ─────────────────────────────────────────────
#  MONTAGEM DE DECK
# ─────────────────────────────────────────────

def build_deck_for_hero(
    hero_id: str,
    data: dict,
    card_pool: dict,
    tags_db: dict,
) -> tuple[CardInst, list[CardInst]]:
    """
    Monta o deck do herói a partir da seção 'decks' do JSON.
    Retorna (hero_inst, [CardInst]) embaralhado.
    Lança ValueError se não houver deck registrado para o herói.
    """
    if hero_id not in card_pool:
        raise ValueError(f"Herói '{hero_id}' não encontrado no card_pool.")

    hero_inst = make_card(card_pool[hero_id], tags_db)

    deck_entry = next(
        (d for d in data.get("decks", []) if d.get("hero_id") == hero_id),
        None,
    )
    if deck_entry is None:
        raise ValueError(
            f"Deck não encontrado para '{hero_id}'. "
            f"Adicione um deck com hero_id='{hero_id}' na seção 'decks'."
        )

    deck: list[CardInst] = []
    missing: list[str] = []
    for cid in deck_entry["cards"]:
        if cid in card_pool:
            deck.append(make_card(card_pool[cid], tags_db))
        else:
            missing.append(cid)

    if missing:
        log(f"⚠️  Deck '{deck_entry['name']}': {len(missing)} carta(s) não encontradas: "
            f"{missing[:5]}")

    random.shuffle(deck)
    return hero_inst, deck


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def hero_list(data: dict) -> list[dict]:
    """Retorna lista de {id, name} de todos os heróis."""
    return [{"id": h["id"], "name": h["name"]} for h in data.get("heroes", [])]
