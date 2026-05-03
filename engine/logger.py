"""
Hemsfell Heroes — Logger
=========================
Log centralizado: captura linhas para o visualizador e imprime quando verbose.
"""

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
