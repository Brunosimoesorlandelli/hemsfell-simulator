# Hemsfell Heroes

Simulador tático do jogo de cartas **Hemsfell Heroes** com motor de IA, visualizador Pygame e ferramentas de análise.

---

## Estrutura do projeto

```
hemsfell/
├── main.py               ← ponto de entrada unificado
├── engine/               ← lógica do jogo
│   ├── config.py         ← constantes (vida inicial, energia, limites…)
│   ├── models.py         ← CardInst, Player
│   ├── logger.py         ← log centralizado
│   ├── loader.py         ← leitura do JSON, construção de decks
│   ├── ai_engine.py      ← motor de IA tática
│   ├── level_system.py   ← condições e aplicação de level up
│   ├── effect_engine.py  ← resolução de effect_tags
│   ├── simulator.py      ← GameState, fases do jogo
│   └── stats.py          ← coleta e relatório de estatísticas
├── data/
│   ├── cards_real.json   ← todas as cartas, heróis e decks
│   └── effect_tags.py    ← dicionário de efeitos por carta
├── ui/
│   ├── snapshot.py       ← foto imutável do estado do jogo
│   ├── instrumented.py   ← GameState que captura snapshots
│   ├── renderer.py       ← funções de desenho Pygame
│   └── viewer.py         ← loop principal do visualizador
├── tools/
│   ├── batch_runner.py   ← execução de múltiplas partidas
│   ├── matchup_matrix.py ← tabela todos-vs-todos
│   └── deck_inspector.py ← inspeção de decks
├── tests/
│   ├── test_models.py    ← testes unitários de CardInst e Player
│   ├── test_simulator.py ← testes de integração
│   └── test_ai.py        ← testes do motor de IA
└── docs/
    ├── regras.md         ← regras do jogo
    ├── keywords.md       ← glossário de keywords
    └── changelog.md      ← histórico de versões
```

---

## Instalação

```bash
pip install pygame   # necessário apenas para o visualizador
```

---

## Uso

### Simular partidas

```bash
# 1 partida com log detalhado
python main.py sim --deck1 hero_gimble --deck2 hero_tifon

# 500 partidas com estatísticas
python main.py sim --deck1 hero_tesslia --deck2 hero_rasmus --games 500

# Todos os confrontos possíveis, 200 partidas cada
python main.py sim --all-matchups --games 200

# Simular usando política RL treinada
python main.py sim --deck1 hero_gimble --deck2 hero_tifon --rl-policy reports/rl_policy.json
```

### Visualizador passo a passo

```bash
python main.py view --deck1 hero_gimble --deck2 hero_tifon
```

Se existir a pasta `assets/cards`, o visualizador usa automaticamente as artes reais das cartas.

**Controles:** `ESPAÇO/→` avança · `←` volta · `A` auto-play · `+/-` velocidade · `R` reinicia · `ESC` sai

### Modo jogável (Humano vs IA)

```bash
python main.py play --deck-player hero_gimble --deck-ai hero_tifon
```

Abre a HUD visual em Pygame para jogar sem terminal:
- Fase principal: clique nas ações para jogar cartas.
- Combate (seu turno): selecione atacantes e confirme.
- Combate (turno da IA): escolha bloqueadores.
- Campo e prévia da mão exibem as artes de `assets/cards` quando houver correspondência.

Opcional:

```bash
python main.py play --deck-player hero_tesslia --deck-ai hero_rasmus --seed 42
```

Fallback no terminal (modo antigo):

```bash
python main.py play --deck-player hero_gimble --deck-ai hero_tifon --terminal
```

### Tabela de matchups

```bash
python main.py matrix --games 50
```

### Treinar IA por reforço (RL)

```bash
# treino rápido no confronto específico
python main.py rl-train --deck1 hero_gimble --deck2 hero_tifon --episodes 500

# treino variando confrontos
python main.py rl-train --all-matchups --episodes 3000
```

Parâmetros úteis:
- `--policy-path reports/rl_policy.json` (arquivo da política)
- `--epsilon-start` e `--epsilon-end` (exploração)
- `--alpha` (taxa de aprendizado)
- `--seed` (reprodutibilidade)

### Avaliar evolução da IA (base vs RL)

```bash
# avaliação em um confronto
python main.py rl-eval --deck1 hero_gimble --deck2 hero_tifon --games 200 --policy-path reports/rl_policy.json

# avaliação em todos os confrontos
python main.py rl-eval --all-matchups --games 100 --policy-path reports/rl_policy.json
```

Opcional:
- `--output reports/rl_eval.txt` para salvar relatório.

### Métricas estratégicas por deck

```bash
python main.py deck-metrics --games 50
```

O relatório por deck inclui:
- Win Rate (WR)
- Consistência da estratégia principal (calculada por arquétipo)
- Velocidade (turno médio de vitória)
- Resiliência e Interação
- Eficiência de mana/recursos

### Inspecionar deck

```bash
python main.py inspect --deck hero_gimble
```

### Listar heróis

```bash
python main.py heroes
```

---

## Rodar os testes

```bash
python tests/test_models.py
python tests/test_ai.py
python tests/test_simulator.py
```

---

## Heróis disponíveis

| ID                        | Herói                        |
|---------------------------|------------------------------|
| `hero_gimble`             | Gimble, Presenteado Sortudo  |
| `hero_sr_goblin`          | Sr. Goblin, O Mercador       |
| `hero_saymon_primeiro`    | Saymon, o Primeiro           |
| `hero_colecionador`       | Colecionador                 |
| `hero_uruk`               | Uruk, a Encantriz            |
| `hero_tifon`              | Tifon, a Peste               |
| `hero_tesslia`            | Tesslia, a Mão de Ferro      |
| `hero_quarion`            | Quarion Siannodel            |
| `hero_rasmus`             | Rasmus, o Barista do Tempo   |
| `hero_ngoro`              | Ngoro, o Investigador        |
| `hero_lider_revolucionario` | Líder Revolucionário       |
| `hero_campeao_natureza`   | Campeão de Natureza          |
