"""
Hemsfell Heroes — Configuração Global
======================================
Todas as constantes do jogo ficam aqui.
Altere aqui para ajustar balanceamento sem tocar no código do simulador.
"""

# ── Jogo ──────────────────────────────────────────────────────────────────
MAX_HAND        = 10    # máximo de cartas na mão
MAX_CREATURES   = 5     # slots de criatura por jogador
MAX_ENERGY      = 10    # energia máxima por turno
MAX_RESERVE     = 3     # energia reserva máxima
STARTING_LIFE   = 30    # vida inicial de cada jogador
STARTING_HAND   = 7     # cartas na mão inicial
MAX_TURNS       = 100    # limite de turnos antes de empate

# ── Level up ──────────────────────────────────────────────────────────────
LEVELUP_COST = {2: 2, 3: 3}   # custo em energia para subir de nível

# ── IA ────────────────────────────────────────────────────────────────────
# Valores usados pela ai_engine na avaliação de cartas/estado
AI_LIFE_VALUE          = 1    # quanto vale 1 ponto de vida do herói
AI_HIGH_COST_PENALTY   = 0.5    # penalidade por custo alto sem campo desenvolvido

# Bônus por keyword na avaliação de carta em campo
AI_KW_VALUE = {
    "Voar":           2.0,
    "Furtivo":        3.5,
    "Investida":      1.5,
    "Atropelar":      2.0,
    "Veloz":          1.5,
    "Toque da Morte": 3.0,
    "Roubo de Vida":  2.0,
    "Robusto":        1.0,
    "Indomavel":      0.5,
    "Indestrutivel":  5.0,
    "Barreira Magica":2.5,
    "Defensor":       1.0,
}

# ── Caminhos ──────────────────────────────────────────────────────────────
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.dirname(_HERE)
DATA_DIR      = os.path.join(PROJECT_ROOT, "data")
CARDS_PATH    = os.path.join(DATA_DIR, "cards_real.json")
TAGS_MODULE   = "data.effect_tags"   # import path do dicionário EFFECT_TAGS
REPORTS_DIR   = os.path.join(PROJECT_ROOT, "reports")
