# Hemsfell Heroes — Changelog

## [v2.2] — Reestruturação do projeto

### Estrutura
- Projeto reorganizado em pacotes: `engine/`, `data/`, `ui/`, `tools/`, `tests/`, `docs/`
- `main.py` unificado como ponto de entrada com subcomandos: `sim`, `view`, `matrix`, `inspect`, `heroes`

### Engine
- Constantes centralizadas em `engine/config.py`
- `CardInst` e `Player` movidos para `engine/models.py`
- Log centralizado em `engine/logger.py`
- Carregamento de dados isolado em `engine/loader.py`
- Sistema de level up em `engine/level_system.py`
- Motor de efeitos em `engine/effect_engine.py`
- Motor de IA em `engine/ai_engine.py`
- `GameState` e fases em `engine/simulator.py`
- Estatísticas em `engine/stats.py`

### UI
- Visualizador dividido em: `ui/snapshot.py`, `ui/renderer.py`, `ui/viewer.py`, `ui/instrumented.py`

### Tools
- `tools/batch_runner.py` — runner de múltiplas partidas
- `tools/matchup_matrix.py` — tabela todos-vs-todos
- `tools/deck_inspector.py` — inspeção de decks no terminal

### Tests
- `tests/test_models.py` — testes unitários de `CardInst` e `Player`
- `tests/test_simulator.py` — testes de integração do simulador
- `tests/test_ai.py` — testes do motor de IA

---

## [v2.1] — Simulador original (hemsfell_sim2.py)
- IA tática com look-ahead de 1 turno
- Sistema de level up por herói
- Campo posicionado com 5 slots
- Motor de efeitos via `effect_tags`
- Visualizador Pygame com snapshots

## [v1.0] — Versão inicial
- Simulação básica de combate
- Decks estáticos
