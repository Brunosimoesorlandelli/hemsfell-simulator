"""
Aprendizado por reforco leve para decisões de IA.

Modelo:
- Política linear por ação (contextual RL).
- Atualização incremental por recompensa ao fim do turno.
- Persistência em JSON para treinar em múltiplas execuções.

Melhorias v2 (alto impacto):
- [FIX] Features capturadas no momento de cada decisão (não mais snapshot
  congelado no início do turno) — decisões dentro de phase_main agora
  enxergam o campo já atualizado pelas jogadas anteriores do mesmo turno.
- [NEW] Features de lethal: can_lethal_attack e opp_can_lethal permitem ao
  agente reconhecer situações de vitória/derrota iminente e agir de forma
  correspondente (all-in vs. defesa total).
- [NEW] Retorno com desconto gamma em on_game_end: o crédito de vitória/
  derrota propaga para decisões passadas com decaimento exponencial, fazendo
  com que decisões boas de turnos anteriores sejam corretamente creditadas.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field

from . import ai_engine as AI


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _deck_target_mana(player) -> float:
    cards = list(player.deck) + list(player.hand) + list(player.graveyard)
    cards += list(player.field_creatures) + list(player.spells_field)
    cards = [c for c in cards if c.card_type != "hero"]
    if not cards:
        return 8.0
    avg_cost = sum(c.cost for c in cards) / len(cards)
    target = 6.5 + avg_cost * 0.8
    if player.hero.id in ("hero_rasmus", "hero_ngoro"):
        target -= 0.6
    if player.hero.id in ("hero_tesslia", "hero_saymon_primeiro"):
        target += 0.3
    return _clip(target, 6.0, 10.0)


def _board_value(player) -> float:
    return sum(AI.card_value(c, player) for c in player.field_creatures)


def state_features(gs, player, opp) -> dict[str, float]:
    """
    Constrói o vetor de features do estado ATUAL do jogo.

    Chamado no momento exato de cada decisão — não no início do turno —
    garantindo que o agente enxerga o campo já modificado por jogadas
    anteriores dentro do mesmo turno (fix do snapshot obsoleto).

    Inclui features de lethal (can_lethal_attack, opp_can_lethal) que
    permitem ao agente reconhecer situações de vitória ou derrota iminente.
    """
    target_mana = _deck_target_mana(player)
    f_self = _board_value(player)
    f_opp  = _board_value(opp)
    mana_gap = (target_mana - player.max_energy) / 10.0

    # ── Features de lethal ────────────────────────────────────────────────
    # Soma do dano potencial de cada lado considerando apenas atacantes validos.
    # Criaturas com Furtivo contam no lethal do jogador pois sempre passam.
    my_attackers  = [c for c in player.field_creatures if c.can_attack()]
    opp_potential = [c for c in opp.field_creatures
                     if not c.tapped and (not c.sick or c.has_kw("Investida"))]

    my_dmg  = sum(c.cur_off() for c in my_attackers)
    opp_dmg = sum(c.cur_off() for c in opp_potential)

    # 1.0 se o jogador pode eliminar o oponente neste combate
    can_lethal = 1.0 if my_dmg >= opp.life else 0.0
    # 1.0 se o oponente pode eliminar o jogador no proximo ataque
    opp_can_lethal = 1.0 if opp_dmg >= player.life else 0.0

    # Urgencia: quao proximo cada lado esta de morrer (0 = ok, 1 = quase morto)
    self_danger = _clip(1.0 - player.life / 30.0, 0.0, 1.0)
    opp_danger  = _clip(1.0 - opp.life / 30.0,    0.0, 1.0)

    return {
        # ── Identidade / tempo ────────────────────────────────────────────
        "bias":              1.0,
        "turn_norm":         _clip(gs.turn / 20.0, 0.0, 2.0),
        "saymon_flag":       1.0 if player.hero.id == "hero_saymon_primeiro" else 0.0,

        # ── Vida ──────────────────────────────────────────────────────────
        "life_self":         player.life / 30.0,
        "life_opp":          opp.life / 30.0,
        "life_diff":         (player.life - opp.life) / 30.0,
        "self_danger":       self_danger,
        "opp_danger":        opp_danger,

        # ── Lethal (NOVO) ─────────────────────────────────────────────────
        # Estes dois sinais sao os de maior impacto imediato: reconhecer
        # quando se pode ou precisa jogar tudo no ataque/defesa.
        "can_lethal_attack": can_lethal,
        "opp_can_lethal":    opp_can_lethal,

        # ── Campo ─────────────────────────────────────────────────────────
        "field_self":        _clip(f_self / 30.0, -2.0, 2.0),
        "field_opp":         _clip(f_opp  / 30.0, -2.0, 2.0),
        "field_diff":        _clip((f_self - f_opp) / 30.0, -2.0, 2.0),

        # ── Heroi / nivel ─────────────────────────────────────────────────
        "lvl_self":          player.hero_level / 3.0,
        "lvl_opp":           opp.hero_level / 3.0,

        # ── Energia / recursos ────────────────────────────────────────────
        "mana_self":         player.max_energy / 10.0,
        "mana_gap":          mana_gap,
        "reserve":           player.reserve / 3.0,
        "target_mana":       target_mana / 10.0,

        # ── Mao / deck ────────────────────────────────────────────────────
        "hand_self":         len(player.hand) / 10.0,
        "opp_creatures":     len(opp.field_creatures) / 5.0,
    }


# ─────────────────────────────────────────────────────────────────────────
#  POLITICA LINEAR
# ─────────────────────────────────────────────────────────────────────────

class LinearPolicy:
    def __init__(self):
        self.weights: dict[str, dict[str, float]] = {}

    def _slot(self, scope: str, action: str) -> dict[str, float]:
        key = f"{scope}|{action}"
        if key not in self.weights:
            self.weights[key] = {"bias": 0.0}
        return self.weights[key]

    def score(self, scope: str, action: str, feats: dict[str, float]) -> float:
        w = self._slot(scope, action)
        return sum(w.get(k, 0.0) * v for k, v in feats.items())

    def choose(self, scope: str, actions: list[str], feats: dict[str, float],
               epsilon: float = 0.0) -> str:
        if not actions:
            return "pass"
        if epsilon > 0.0 and random.random() < epsilon:
            return random.choice(actions)
        scored = [(self.score(scope, a, feats), a) for a in actions]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def update(self, scope: str, action: str, feats: dict[str, float],
               reward: float, alpha: float):
        w    = self._slot(scope, action)
        pred = self.score(scope, action, feats)
        err  = reward - pred
        for k, v in feats.items():
            w[k] = w.get(k, 0.0) + alpha * err * v

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"weights": self.weights}, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "LinearPolicy":
        pol = cls()
        if not os.path.exists(path):
            return pol
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pol.weights = data.get("weights", {})
        return pol


# ─────────────────────────────────────────────────────────────────────────
#  ESTRUTURAS INTERNAS
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class _Decision:
    scope:       str
    action:      str
    feats:       dict[str, float]
    # indice cronologico da decisao no episodio — usado pelo retorno descontado
    episode_idx: int = 0


@dataclass
class _TurnSnapshot:
    self_life:   int
    opp_life:    int
    hero_level:  int
    max_energy:  int
    board_self:  float
    board_opp:   float
    target_mana: float


# ─────────────────────────────────────────────────────────────────────────
#  RUNTIME DO EPISODIO
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class RLEpisodeRuntime:
    policy:   LinearPolicy
    training: bool  = True
    epsilon:  float = 0.10
    alpha:    float = 0.03

    # Fator de desconto para o retorno com gamma.
    # 0.95 significa que uma decisao tomada k passos antes do fim recebe
    # credito multiplicado por 0.95^k — decisoes mais antigas recebem menos,
    # mas ainda assim recebem sinal, diferente do esquema anterior (0 ou bonus).
    gamma:    float = 0.95

    turn_snaps:        dict[int, _TurnSnapshot]  = field(default_factory=dict)
    decisions:         dict[int, list[_Decision]] = field(default_factory=dict)
    last_reward:       dict[int, float]           = field(default_factory=dict)

    # Contador global de decisoes no episodio (por jogador).
    # Garante ordenacao cronologica correta em on_game_end.
    _decision_counter: dict[int, int] = field(default_factory=dict)

    def _scope(self, player, kind: str) -> str:
        return f"{kind}:{player.hero.id}"

    def _next_idx(self, pid: int) -> int:
        idx = self._decision_counter.get(pid, 0)
        self._decision_counter[pid] = idx + 1
        return idx

    # ── Inicio de turno ───────────────────────────────────────────────────

    def on_turn_start(self, gs, player, opp):
        pid = id(player)
        self.turn_snaps[pid] = _TurnSnapshot(
            self_life   = player.life,
            opp_life    = opp.life,
            hero_level  = player.hero_level,
            max_energy  = player.max_energy,
            board_self  = _board_value(player),
            board_opp   = _board_value(opp),
            target_mana = _deck_target_mana(player),
        )
        if pid not in self.decisions:
            self.decisions[pid] = []

    # ── Decisao de fase principal ─────────────────────────────────────────
    #
    # FIX: state_features() e chamado AQUI, no momento da decisao, e nao
    # mais no on_turn_start(). Isso garante que o vetor de features reflita
    # o estado real do campo apos cada carta ja jogada neste turno — o campo
    # muda entre jogadas e o snapshot congelado anterior tornava as features
    # obsoletas para a 2a, 3a decisao em diante.

    def decide_main_action(self, gs, player, opp, actions: list[str]) -> str:
        feats  = state_features(gs, player, opp)   # estado ATUAL, nao snapshot
        scope  = self._scope(player, "main")
        action = self.policy.choose(scope, actions, feats,
                                    self.epsilon if self.training else 0.0)
        pid = id(player)
        self.decisions[pid].append(
            _Decision(scope=scope, action=action, feats=feats,
                      episode_idx=self._next_idx(pid))
        )
        return action

    # ── Decisao de estilo de ataque ───────────────────────────────────────
    #
    # Mesmo fix: features capturadas no momento da decisao de ataque, onde
    # can_lethal_attack e especialmente relevante para o agente decidir
    # entre "all-in" e "ataque seguro".

    def decide_attack_style(self, gs, player, opp, styles: list[str]) -> str:
        feats  = state_features(gs, player, opp)   # estado ATUAL
        scope  = self._scope(player, "attack")
        style  = self.policy.choose(scope, styles, feats,
                                    self.epsilon if self.training else 0.0)
        pid = id(player)
        self.decisions[pid].append(
            _Decision(scope=scope, action=style, feats=feats,
                      episode_idx=self._next_idx(pid))
        )
        return style

    # ── Fim de turno: reward imediato ─────────────────────────────────────

    def on_turn_end(self, gs, player, opp):
        pid  = id(player)
        snap = self.turn_snaps.get(pid)
        if not snap:
            return

        damage_dealt = max(0.0, snap.opp_life - opp.life)
        damage_taken = max(0.0, snap.self_life - player.life)
        lvl_gain     = max(0.0, player.hero_level - snap.hero_level)
        mana_gain    = max(0.0, player.max_energy  - snap.max_energy)

        before_close = 1.0 - abs(snap.max_energy - snap.target_mana) / 10.0
        after_close  = 1.0 - abs(player.max_energy - snap.target_mana) / 10.0

        reward  = 0.0
        reward += 1.25 * damage_dealt
        reward -= 1.05 * damage_taken
        reward += 3.2  * lvl_gain
        reward += 0.8  * (after_close - before_close)
        reward += 0.5  * mana_gain

        if player.max_energy >= snap.target_mana:
            reward += 0.25
        if player.max_energy > snap.target_mana + 1:
            reward -= 0.25 * (player.max_energy - (snap.target_mana + 1))

        # Saymon usa vida como recurso; reduz penalidade quando ha ganho de
        # controle de campo em troca de vida perdida.
        if player.hero.id == "hero_saymon_primeiro" and damage_taken > 0:
            board_before = snap.board_self - snap.board_opp
            board_after  = _board_value(player) - _board_value(opp)
            if board_after > board_before:
                reward += 0.65 * damage_taken

        if player.life <= 6:
            reward -= 0.8

        self.last_reward[pid] = reward
        if self.training:
            for d in self.decisions.get(pid, []):
                self.policy.update(d.scope, d.action, d.feats, reward, self.alpha)

    # ── Fim de episodio: retorno com desconto gamma ───────────────────────
    #
    # MELHORIA: em vez de atualizar todas as decisoes do episodio com o mesmo
    # bonus fixo (+12 / -12), aplicamos decaimento exponencial via gamma.
    # A decisao mais recente recebe o bonus completo; cada decisao anterior
    # recebe gamma^k vezes o bonus, onde k e a distancia temporal ate o fim.
    #
    # Exemplo com gamma=0.95 e bonus=12 (vitoria):
    #   decisao N   (ultima):  12.0
    #   decisao N-1:           11.4
    #   decisao N-5:            9.3
    #   decisao N-10:           7.2
    #
    # Isso resolve o problema de credito temporal: uma sequencia de jogadas
    # que levou a vitoria 10 turnos depois ainda recebe sinal positivo,
    # proporcional a sua distancia temporal do desfecho final.

    def on_game_end(self, gs):
        if not self.training:
            return

        for p in gs.players:
            pid = id(p)

            if gs.winner is p:
                terminal_bonus = 12.0
            elif gs.winner is not None:
                terminal_bonus = -12.0
            else:
                terminal_bonus = 0.0   # empate: sem bonus/penalidade extra

            if terminal_bonus == 0.0:
                continue

            # Ordenar decisoes cronologicamente (mais antiga → mais recente)
            all_decisions = sorted(
                self.decisions.get(pid, []),
                key=lambda d: d.episode_idx
            )

            if not all_decisions:
                continue

            n = len(all_decisions)

            # Percorre de tras para frente calculando o retorno descontado.
            # steps_from_end = 0 para a ultima decisao, aumenta para as anteriores.
            # gamma^0 = 1.0 (bonus total para a ultima decisao)
            # gamma^k decai exponencialmente para decisoes mais antigas.
            for i in range(n - 1, -1, -1):
                d = all_decisions[i]
                steps_from_end = n - 1 - i
                discounted = terminal_bonus * (self.gamma ** steps_from_end)
                self.policy.update(d.scope, d.action, d.feats, discounted, self.alpha)