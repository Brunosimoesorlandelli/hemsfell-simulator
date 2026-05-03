"""
Hemsfell Heroes — Viewer
==========================
Loop principal do visualizador Pygame.
Gerencia eventos de teclado, auto-play e comunica com o Renderer.

Uso:
  python -m ui.viewer                              (Gimble vs Tifon)
  python -m ui.viewer --deck1 hero_tesslia --deck2 hero_rasmus
  python main.py view --deck1 hero_gimble --deck2 hero_tifon
"""

from __future__ import annotations
import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from .renderer import Renderer
from .instrumented import run_instrumented
from .snapshot import Snapshot
from engine.loader import load_data, build_card_pool, load_tags


class Viewer:
    def __init__(self):
        self.renderer   = Renderer()
        self.snapshots: list[Snapshot] = []
        self.idx        = 0
        self.auto_play  = False
        self.auto_delay = 1.2
        self._last_auto = 0.0

    def load_snapshots(self, snaps: list[Snapshot]):
        self.snapshots  = snaps
        self.idx        = 0
        self.auto_play  = False

    def run(self) -> str:
        """
        Executa o loop de eventos Pygame.
        Retorna "restart" ou "quit".
        """
        clock = self.renderer.clock
        while True:
            clock.tick(self.renderer.FPS)
            now = time.time()

            # auto-play
            if self.auto_play and self.snapshots:
                if now - self._last_auto >= self.auto_delay:
                    self.idx = min(self.idx+1, len(self.snapshots)-1)
                    self._last_auto = now

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"

                elif event.type == pygame.KEYDOWN:
                    k = event.key

                    if k in (pygame.K_ESCAPE, pygame.K_q):
                        return "quit"

                    elif k in (pygame.K_SPACE, pygame.K_RIGHT, pygame.K_DOWN):
                        self.idx = min(self.idx+1, len(self.snapshots)-1)

                    elif k in (pygame.K_LEFT, pygame.K_UP):
                        self.idx = max(self.idx-1, 0)

                    elif k == pygame.K_HOME:
                        self.idx = 0

                    elif k == pygame.K_END:
                        self.idx = max(0, len(self.snapshots)-1)

                    elif k == pygame.K_a:
                        self.auto_play  = not self.auto_play
                        self._last_auto = now

                    elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        self.auto_delay = max(0.2, self.auto_delay - 0.2)

                    elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.auto_delay = min(5.0, self.auto_delay + 0.2)

                    elif k == pygame.K_r:
                        return "restart"

            if self.snapshots:
                snap = self.snapshots[self.idx]
                self.renderer.render_frame(
                    snap, self.idx, len(self.snapshots),
                    self.auto_play, self.auto_delay,
                )

        pygame.quit()
        return "quit"


# ── Ponto de entrada standalone ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Hemsfell Heroes — Visualizador Pygame"
    )
    parser.add_argument("--deck1", default="hero_gimble")
    parser.add_argument("--deck2", default="hero_tifon")
    args = parser.parse_args()

    data      = load_data()
    card_pool = build_card_pool(data)
    tags_db   = load_tags()
    viewer    = Viewer()

    while True:
        print(f"\n🎮 Simulando {args.deck1} vs {args.deck2}…")
        snaps = run_instrumented(args.deck1, args.deck2, data, card_pool, tags_db)
        print(f"   {len(snaps)} snapshots capturados.\n")

        viewer.load_snapshots(snaps)
        result = viewer.run()

        if result == "restart":
            print("🔄 Reiniciando partida…")
        else:
            break

    pygame.quit()
    print("👋 Visualizador encerrado.")


if __name__ == "__main__":
    main()
