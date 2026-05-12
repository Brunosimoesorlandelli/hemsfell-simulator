"""
Hemsfell Heroes — Logger
=========================
Log centralizado: captura linhas para o visualizador e imprime quando verbose.
"""

import os

_VERBOSE: bool = False
_LOG_LINES: list[str] = []


def set_verbose(v: bool):
    global _VERBOSE
    _VERBOSE = v


def clear():
    _LOG_LINES.clear()


def get_lines() -> list[str]:
    return list(_LOG_LINES)


def log(msg: str, indent: int = 0):
    line = "  " * indent + msg
    if _VERBOSE:
        print(line)
    _LOG_LINES.append(line)


def sep(char: str = "─", w: int = 60):
    log(char * w)


def sec(title: str):
    sep("═")
    log(f"  {title}")
    sep("═")


def write_header(path: str, p1_name: str, p2_name: str, n_games: int):
    """Cria (ou sobrescreve) o arquivo de log com o cabeçalho do matchup."""
    import time
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("HEMSFELL HEROES — LOG COMPLETO DE SIMULAÇÕES\n")
        f.write(f"Gerado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Matchup: {p1_name} vs {p2_name}  ({n_games} partida(s))\n")
        f.write("=" * 64 + "\n\n")


def dump_to_file(path: str, game_index: int, winner: str):
    """Appenda o log do jogo atual no arquivo, com cabeçalho de separação."""
    if not _LOG_LINES:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{'─' * 64}\n")
        f.write(f"  PARTIDA #{game_index}  |  Vencedor: {winner}\n")
        f.write(f"{'─' * 64}\n")
        f.write("\n".join(_LOG_LINES))
        f.write("\n\n")
