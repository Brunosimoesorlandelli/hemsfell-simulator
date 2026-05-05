"""
Aprendizado por reforco — política MLP (v3).

Arquitetura:
- MLPPolicy substitui LinearPolicy: rede neural rasa [N_feats → 64 → 32 → 1]
  com ReLU, capaz de aprender interações não-lineares entre features
  (ex: "atacar é bom QUANDO can_lethal_attack E opp_danger são altos juntos").
  Treinada via REINFORCE com baseline de média móvel para reduzir variância.
- Persistência em JSON (pesos das camadas) compatível com versões anteriores.

Melhorias v3 (alto impacto):
- [NEW] MLPPolicy: substitui produto escalar por rede 2 camadas com ReLU.
  Capacidade expressiva suficiente para aprender estratégias condicionais
  sem custo proibitivo de treino (< 5k parâmetros por scope/ação).
- [NEW] Features de contexto de turno: cards_played_this_turn_norm,
  energy_spent_ratio e field_delta_this_turn capturam o que já aconteceu
  no turno atual, permitindo decisões sequenciais coerentes.
- [FIX] record_invalid_action implementado: aplica penalidade leve (-0.5)
  quando o agente escolhe uma ação que não pode ser executada, corrigindo
  o AttributeError que ocorria em runtime.
- [NEW] board_delta no reward de fim de turno: captura ganho/perda de
  posição no campo (não apenas dano), melhorando o sinal de treino para
  estratégias de controle e midrange.

Mantidos de v2:
- Features de lethal (can_lethal_attack, opp_can_lethal).
- Retorno com desconto gamma para crédito temporal correto.
- Features capturadas no momento exato de cada decisão (não snapshot).
"""

from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from typing import List

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
    anteriores dentro do mesmo turno.

    v3: adicionadas features de contexto de turno:
      - cards_played_this_turn_norm: quantas cartas já foram jogadas neste turno
        (normalizado por 5). Permite ao agente reconhecer que já fez jogadas.
      - energy_spent_ratio: fração da energia total já gasta. Sinaliza quando
        o orçamento está quase esgotado vs. ainda há margem para jogar mais.
      - field_delta_this_turn: variação no board advantage desde o início do turno.
        Captura se as jogadas já feitas melhoraram ou pioraram a posição.
    """
    target_mana = _deck_target_mana(player)
    f_self = _board_value(player)
    f_opp  = _board_value(opp)
    mana_gap = (target_mana - player.max_energy) / 10.0

    # ── Features de lethal ────────────────────────────────────────────────
    my_attackers  = [c for c in player.field_creatures if c.can_attack()]
    opp_potential = [c for c in opp.field_creatures
                     if not c.tapped and (not c.sick or c.has_kw("Investida"))]

    my_dmg  = sum(c.cur_off() for c in my_attackers)
    opp_dmg = sum(c.cur_off() for c in opp_potential)

    can_lethal     = 1.0 if my_dmg >= opp.life else 0.0
    opp_can_lethal = 1.0 if opp_dmg >= player.life else 0.0

    self_danger = _clip(1.0 - player.life / 30.0, 0.0, 1.0)
    opp_danger  = _clip(1.0 - opp.life / 30.0,    0.0, 1.0)

    # ── Features de contexto de turno (NEW v3) ────────────────────────────
    # Quantas cartas já jogamos neste turno (normalizado).
    # Informa ao agente que já agiu — importante para decisões de "passar" ou
    # continuar jogando após gastar parte da energia.
    cards_this_turn = getattr(player, "cards_played_this_turn", 0)
    cards_played_norm = _clip(cards_this_turn / 5.0, 0.0, 1.0)

    # Fração da energia total já gasta.
    # energy_spent_ratio = 1.0 significa que não sobrou energia; 0.0 = turno novo.
    total_budget = max(1, player.max_energy + player.reserve)
    energy_remaining = player.energy + player.reserve
    energy_spent_ratio = _clip(1.0 - energy_remaining / total_budget, 0.0, 1.0)

    # Variação no board advantage desde o início do turno.
    # Usa o snapshot guardado pelo on_turn_start; se não existir (primeiro turno),
    # usa 0.0 como referência neutra.
    pid = id(player)
    snap = None
    # Acessa o snapshot se disponível via atributo temporário injetado pelo runtime
    _snap_ref = getattr(player, "_rl_turn_snap", None)
    if _snap_ref is not None:
        board_start_self = _snap_ref.board_self
        board_start_opp  = _snap_ref.board_opp
        field_delta = _clip(
            ((f_self - f_opp) - (board_start_self - board_start_opp)) / 15.0,
            -2.0, 2.0
        )
    else:
        field_delta = 0.0

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

        # ── Lethal ────────────────────────────────────────────────────────
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

        # ── Contexto de turno (NEW v3) ────────────────────────────────────
        # Quantas cartas já jogamos neste turno — permite ao agente saber
        # que já agiu antes de decidir jogar mais ou passar.
        "cards_played_this_turn_norm": cards_played_norm,

        # Fração da energia já gasta — sinaliza quando o orçamento se esgota.
        "energy_spent_ratio":          energy_spent_ratio,

        # Variação no board advantage desde o início do turno — mede se as
        # jogadas já feitas melhoraram a posição antes de decidir a próxima.
        "field_delta_this_turn":       field_delta,
    }


# ─────────────────────────────────────────────────────────────────────────
#  POLÍTICA MLP (v3 — substitui LinearPolicy)
# ─────────────────────────────────────────────────────────────────────────
#
#  Arquitetura por scope+ação: [N_feats → H1 → H2 → 1] com ReLU.
#  Isso permite aprender relações NÃO-LINEARES entre features — por exemplo:
#    "atacar é bom QUANDO (can_lethal_attack=1 AND opp_danger > 0.7)"
#  é impossível de representar num produto escalar, mas trivial para uma MLP.
#
#  Treinamento: gradiente manual de REINFORCE (sem PyTorch para manter zero
#  dependências externas). A atualização segue:
#    Δw = alpha * (reward - baseline) * ∂score/∂w
#  onde baseline é a média móvel dos rewards recentes (reduz variância).
#
#  Persistência: pesos salvos em JSON (lista de matrizes) por chave
#  "{scope}|{action}", compatível com o formato de save/load anterior.

_MLP_H1 = 64   # neurônios na 1ª camada oculta
_MLP_H2 = 32   # neurônios na 2ª camada oculta


def _relu(x: float) -> float:
    return x if x > 0.0 else 0.0


def _relu_vec(v: List[float]) -> List[float]:
    return [_relu(x) for x in v]


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _mat_vec(mat: List[List[float]], vec: List[float]) -> List[float]:
    """Multiplica matriz (linhas × colunas) por vetor coluna."""
    return [_dot(row, vec) for row in mat]


def _add_vec(a: List[float], b: List[float]) -> List[float]:
    return [x + y for x, y in zip(a, b)]


def _zeros(n: int) -> List[float]:
    return [0.0] * n


def _zeros_mat(rows: int, cols: int) -> List[List[float]]:
    return [[0.0] * cols for _ in range(rows)]


def _rand_init(rows: int, cols: int) -> List[List[float]]:
    """He initialization: escala √(2/fan_in) para camadas ReLU."""
    scale = math.sqrt(2.0 / cols)
    return [[random.gauss(0.0, scale) for _ in range(cols)] for _ in range(rows)]


class _MLPNet:
    """
    Rede MLP: [N_in → H1 → H2 → 1].
    Mantém os pesos e as ativações intermediárias do último forward pass
    para calcular o gradiente analítico em backward().
    """

    def __init__(self, n_in: int):
        self.n_in = n_in
        # Camada 1: H1 × N_in
        self.W1: List[List[float]] = _rand_init(_MLP_H1, n_in)
        self.b1: List[float]       = _zeros(_MLP_H1)
        # Camada 2: H2 × H1
        self.W2: List[List[float]] = _rand_init(_MLP_H2, _MLP_H1)
        self.b2: List[float]       = _zeros(_MLP_H2)
        # Camada de saída: 1 × H2 (vetor linha)
        self.W3: List[float]       = _zeros(_MLP_H2)
        self.b3: float             = 0.0

        # Ativações salvas pelo último forward() para uso em backward()
        self._x:  List[float] = []
        self._h1: List[float] = []
        self._h2: List[float] = []

    # ── Forward ───────────────────────────────────────────────────────────
    def forward(self, x: List[float]) -> float:
        self._x  = x
        z1       = _add_vec(_mat_vec(self.W1, x),  self.b1)
        self._h1 = _relu_vec(z1)
        z2       = _add_vec(_mat_vec(self.W2, self._h1), self.b2)
        self._h2 = _relu_vec(z2)
        return _dot(self.W3, self._h2) + self.b3

    # ── Backward (REINFORCE): Δw = alpha * delta * ∂score/∂w ─────────────
    def backward(self, delta: float, alpha: float):
        """
        Atualização de gradiente ascendente (maximizar score).
        delta = reward - baseline (sinal de REINFORCE).
        """
        # Gradiente da camada de saída
        # ∂score/∂W3[j] = h2[j],  ∂score/∂b3 = 1
        for j in range(_MLP_H2):
            self.W3[j] += alpha * delta * self._h2[j]
        self.b3 += alpha * delta

        # Backprop para h2: dL/dz2[j] = W3[j] * relu'(z2[j])
        # relu'(z) = 1 se h2[j] > 0, senão 0
        dz2 = [
            (self.W3[j] * delta if self._h2[j] > 0.0 else 0.0)
            for j in range(_MLP_H2)
        ]

        # Gradiente W2 e b2
        for i in range(_MLP_H2):
            if dz2[i] == 0.0:
                continue
            for j in range(_MLP_H1):
                self.W2[i][j] += alpha * dz2[i] * self._h1[j]
            self.b2[i] += alpha * dz2[i]

        # Backprop para h1: dL/dz1[j] = Σ_i W2[i][j] * dz2[i]
        dz1 = [
            sum(self.W2[i][j] * dz2[i] for i in range(_MLP_H2)) *
            (1.0 if self._h1[j] > 0.0 else 0.0)
            for j in range(_MLP_H1)
        ]

        # Gradiente W1 e b1
        for i in range(_MLP_H1):
            if dz1[i] == 0.0:
                continue
            for j in range(self.n_in):
                self.W1[i][j] += alpha * dz1[i] * self._x[j]
            self.b1[i] += alpha * dz1[i]

    # ── Serialização ──────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {"W1": self.W1, "b1": self.b1,
                "W2": self.W2, "b2": self.b2,
                "W3": self.W3, "b3": self.b3,
                "n_in": self.n_in}

    @classmethod
    def from_dict(cls, d: dict) -> "_MLPNet":
        net = cls.__new__(cls)
        net.n_in = d["n_in"]
        net.W1 = d["W1"]; net.b1 = d["b1"]
        net.W2 = d["W2"]; net.b2 = d["b2"]
        net.W3 = d["W3"]; net.b3 = d["b3"]
        net._x = []; net._h1 = []; net._h2 = []
        return net


class MLPPolicy:
    """
    Política MLP por scope+ação.

    Interface idêntica à LinearPolicy anterior para compatibilidade com
    o RLEpisodeRuntime — apenas score(), choose(), update(), save() e load().

    Baseline: média móvel exponencial dos rewards por scope (reduz variância
    do gradiente REINFORCE sem introduzir bias assintótico).
    """

    _BASELINE_ALPHA = 0.05   # taxa de atualização da baseline EMA

    def __init__(self):
        # chave = "{scope}|{action}" → _MLPNet
        self._nets:     dict[str, _MLPNet]  = {}
        # baseline EMA por scope (não por ação) para estabilidade
        self._baseline: dict[str, float]    = {}
        # dimensão do vetor de features (fixada na primeira chamada)
        self._n_in: int = 0

    def _key(self, scope: str, action: str) -> str:
        return f"{scope}|{action}"

    def _net(self, scope: str, action: str) -> _MLPNet:
        k = self._key(scope, action)
        if k not in self._nets:
            if self._n_in == 0:
                raise RuntimeError("MLPPolicy: n_in não inicializado. "
                                   "Chame prime() antes do primeiro score().")
            self._nets[k] = _MLPNet(self._n_in)
        return self._nets[k]

    def prime(self, n_in: int):
        """Define a dimensão do vetor de features. Chamado uma vez no primeiro uso."""
        if self._n_in == 0:
            self._n_in = n_in

    def score(self, scope: str, action: str, feats: dict[str, float]) -> float:
        x = list(feats.values())
        self.prime(len(x))
        return self._net(scope, action).forward(x)

    def choose(self, scope: str, actions: list[str], feats: dict[str, float],
               epsilon: float = 0.0) -> str:
        if not actions:
            return "pass"
        if epsilon > 0.0 and random.random() < epsilon:
            return random.choice(actions)
        x = list(feats.values())
        self.prime(len(x))
        best_action = actions[0]
        best_score  = float("-inf")
        for a in actions:
            s = self._net(scope, a).forward(x)
            if s > best_score:
                best_score  = s
                best_action = a
        return best_action

    def update(self, scope: str, action: str, feats: dict[str, float],
               reward: float, alpha: float):
        """
        Atualização REINFORCE com baseline EMA.
        delta = reward - baseline[scope] → reduz variância sem bias.
        """
        x = list(feats.values())
        self.prime(len(x))

        # Atualiza baseline EMA do scope
        bl = self._baseline.get(scope, 0.0)
        bl = bl + self._BASELINE_ALPHA * (reward - bl)
        self._baseline[scope] = bl

        delta = reward - bl
        net   = self._net(scope, action)
        net.forward(x)          # garante ativações atualizadas
        net.backward(delta, alpha)

    def save(self, path: str,
             metadata: dict | None = None,
             checkpoint_tag: str | None = None):
        """
        Salva a política em JSON.

        metadata e checkpoint_tag são opcionais — aceitos para compatibilidade
        com rl_trainer.py (que os usa para rastrear checkpoints e config de treino).
        São gravados no JSON mas não afetam o comportamento da política.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "version":        3,
            "n_in":           self._n_in,
            "baseline":       self._baseline,
            "nets":           {k: net.to_dict() for k, net in self._nets.items()},
            "metadata":       metadata or {},
            "checkpoint_tag": checkpoint_tag or "",
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "MLPPolicy":
        pol = cls()
        if not os.path.exists(path):
            return pol
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            print(f"[RL] Aviso: arquivo de politica '{path}' invalido ou em formato "
                  f"antigo (binario/corrompido). Iniciando politica do zero.")
            return pol
        version = data.get("version", 1)
        if version < 3:
            # Arquivo antigo (LinearPolicy): descarta pesos incompatíveis.
            # A rede começa do zero mas mantém compatibilidade de API.
            return pol
        pol._n_in     = data.get("n_in", 0)
        pol._baseline = data.get("baseline", {})
        for k, net_d in data.get("nets", {}).items():
            pol._nets[k] = _MLPNet.from_dict(net_d)
        return pol


# Aliases para compatibilidade com código que instancie as classes diretamente.
LinearPolicy = MLPPolicy
DQNPolicy    = MLPPolicy


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
    _decision_counter: dict[int, int]        = field(default_factory=dict)

    # Ultimas features reais capturadas por jogador — usadas em
    # record_invalid_action para evitar IndexError na MLP (o vetor precisa
    # ter o mesmo n_in com que a rede foi inicializada).
    _last_feats:       dict[int, dict]       = field(default_factory=dict)

    # Contador de acoes invalidas no episodio — centralizado aqui para
    # evitar o uso fragil de getattr(self, "_invalid_count", 0).
    _invalid_count:    int                   = field(default=0)

    def _scope(self, player, kind: str) -> str:
        return f"{kind}:{player.hero.id}"

    def _next_idx(self, pid: int) -> int:
        idx = self._decision_counter.get(pid, 0)
        self._decision_counter[pid] = idx + 1
        return idx

    # ── Inicio de turno ───────────────────────────────────────────────────

    def on_turn_start(self, gs, player, opp):
        pid = id(player)
        snap = _TurnSnapshot(
            self_life   = player.life,
            opp_life    = opp.life,
            hero_level  = player.hero_level,
            max_energy  = player.max_energy,
            board_self  = _board_value(player),
            board_opp   = _board_value(opp),
            target_mana = _deck_target_mana(player),
        )
        self.turn_snaps[pid] = snap
        # Injeta referência ao snap no player para que state_features()
        # possa calcular field_delta_this_turn sem precisar do runtime.
        player._rl_turn_snap = snap
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
        self._last_feats[pid] = feats   # salva para uso em record_invalid_action
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

    # ── Ação inválida (NEW v3) ────────────────────────────────────────────
    #
    # Chamado pelo simulator quando o agente escolhe uma ação que não pode
    # ser executada (ex: "play_best_creature" sem criaturas jogáveis).
    # Aplica penalidade leve para desincentivar ações inválidas sem colapsar
    # o aprendizado — o sinal é proporcional ao alpha atual.

    def record_invalid_action(self, player, action: str):
        if not self.training:
            return
        pid   = id(player)
        scope = self._scope(player, "main")
        # Usa as ultimas features reais capturadas em decide_main_action.
        # Evita IndexError causado por vetor de tamanho errado na MLP —
        # o {"bias": 1.0} original tinha apenas 1 feature enquanto a rede
        # espera n_in features (tipicamente 25).
        feats = self._last_feats.get(pid)
        if feats is None:
            # Seguranca: se ainda nao houve nenhuma decisao neste turno,
            # nao aplica penalidade para evitar inicializar a rede com
            # dimensao errada.
            return
        self.policy.update(scope, action, feats, -0.5, self.alpha)
        self._invalid_count += 1

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

        # ── board_delta (NEW v3) ──────────────────────────────────────────
        # Captura variação no board advantage durante o turno.
        # Corrige o viés do reward anterior que só recompensava dano direto,
        # ignorando turnos que limpam o campo inimigo ou constroem posição.
        board_self_now   = _board_value(player)
        board_opp_now    = _board_value(opp)
        board_adv_before = snap.board_self - snap.board_opp
        board_adv_after  = board_self_now  - board_opp_now
        board_delta      = board_adv_after - board_adv_before
        board_delta_reward = _clip(board_delta / 30.0, -1.5, 1.5) * 0.6

        reward  = 0.0
        reward += 1.25 * damage_dealt
        reward -= 1.05 * damage_taken
        reward += 3.2  * lvl_gain
        reward += 0.8  * (after_close - before_close)
        reward += 0.5  * mana_gain
        reward += board_delta_reward          # NEW v3

        if player.max_energy >= snap.target_mana:
            reward += 0.25
        if player.max_energy > snap.target_mana + 1:
            reward -= 0.25 * (player.max_energy - (snap.target_mana + 1))

        # Saymon usa vida como recurso; reduz penalidade quando há ganho de
        # controle de campo em troca de vida perdida.
        if player.hero.id == "hero_saymon_primeiro" and damage_taken > 0:
            if board_adv_after > board_adv_before:
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

    # ── Sumário do episódio (NEW v3) ──────────────────────────────────────
    #
    # Chamado pelo trainer após cada jogo para coletar métricas de diagnóstico.
    # Retorna um dict compatível com o que rl_trainer.py espera em:
    #   summary = runtime.summarize()
    #   summary["reward_avg"]
    #   summary["invalid_action_rate"]
    #   summary["pass_rate"]
    #   summary["action_distribution"]

    def summarize(self) -> dict:
        """
        Retorna métricas do episódio para logging no trainer.

        - reward_avg: média dos rewards imediatos acumulados no turno (last_reward).
        - invalid_action_rate: fração de decisões que foram inválidas (penalizadas).
        - pass_rate: fração de decisões de fase principal onde a ação foi "pass".
        - action_distribution: contagem de ações por scope, útil para detectar
          colapso de política (ex: agente sempre escolhe "pass").
        """
        all_rewards = list(self.last_reward.values())
        reward_avg = sum(all_rewards) / max(1, len(all_rewards))

        # Conta decisões inválidas registradas via record_invalid_action
        invalid_count = self._invalid_count
        total_decisions = sum(
            len(dlist) for dlist in self.decisions.values()
        )
        invalid_rate = invalid_count / max(1, total_decisions)

        # Conta ações "pass" na fase principal
        pass_count = 0
        main_count = 0
        action_dist: dict[str, dict[str, int]] = {}
        for dlist in self.decisions.values():
            for d in dlist:
                scope_label = d.scope.split(":")[0] if ":" in d.scope else d.scope
                action_dist.setdefault(scope_label, {})
                action_dist[scope_label][d.action] = (
                    action_dist[scope_label].get(d.action, 0) + 1
                )
                if "main" in d.scope:
                    main_count += 1
                    if d.action == "pass":
                        pass_count += 1

        pass_rate = pass_count / max(1, main_count)

        return {
            "reward_avg":          reward_avg,
            "invalid_action_rate": invalid_rate,
            "pass_rate":           pass_rate,
            "action_distribution": action_dist,
        }