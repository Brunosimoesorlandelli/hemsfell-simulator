"""
Carregamento e busca de artes de carta por nome.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pygame


def _normalize(text: str) -> str:
    text = text or ""
    text = text.strip().lower()
    text = re.sub(r"\(\d+\)$", "", text).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


class CardArtLibrary:
    def __init__(self, base_dir: str | None = None):
        root = Path(__file__).resolve().parents[1]
        self.base_dir = Path(base_dir) if base_dir else (root / "assets" / "cards")
        self._name_to_path: dict[str, Path] = {}
        self._surface_cache: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
        self._build_index()

    def _build_index(self):
        if not self.base_dir.exists():
            return
        for p in self.base_dir.glob("*.png"):
            key = _normalize(p.stem)
            if key and key not in self._name_to_path:
                self._name_to_path[key] = p

    def _resolve(self, card_name: str) -> Path | None:
        key = _normalize(card_name)
        if not key:
            return None
        direct = self._name_to_path.get(key)
        if direct:
            return direct

        # fallback leve para pequenas variações de escrita
        for k, p in self._name_to_path.items():
            if key in k or k in key:
                return p

        best_score = 0.0
        best_path: Path | None = None
        for k, p in self._name_to_path.items():
            score = SequenceMatcher(None, key, k).ratio()
            if score > best_score:
                best_score = score
                best_path = p
        if best_score >= 0.84:
            return best_path
        return None

    def get_scaled_surface(
        self,
        card_name: str,
        size: tuple[int, int],
    ) -> pygame.Surface | None:
        cache_key = (card_name, size)
        if cache_key in self._surface_cache:
            return self._surface_cache[cache_key]

        path = self._resolve(card_name)
        if path is None:
            return None
        try:
            img = pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            return None

        surf = pygame.transform.smoothscale(img, size)
        self._surface_cache[cache_key] = surf
        return surf
