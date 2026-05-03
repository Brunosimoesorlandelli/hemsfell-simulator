"""
Hemsfell Heroes â€” Renderer
============================
FunÃ§Ãµes puras de desenho Pygame.
Recebe superfÃ­cies e snapshots, nÃ£o mantÃ©m estado de jogo.
"""

from __future__ import annotations
import textwrap
import pygame
from .snapshot import Snapshot
from .card_art import CardArtLibrary


# â”€â”€ Paleta â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class C:
    BG           = (15,  15,  25)
    BG2          = (22,  22,  38)
    PANEL        = (28,  28,  48)
    PANEL_DARK   = (18,  18,  32)
    BORDER       = (55,  55,  90)
    BORDER_LIT   = (120, 120, 200)
    P1           = (70,  130, 220)
    P2           = (220,  70,  70)
    CARD_BG      = (35,  35,  58)
    CARD_BDR     = (80,  80, 130)
    CARD_ATTACK  = (220, 160,  30)
    CARD_BLOCK   = (30,  180, 220)
    CARD_TAPPED  = (100,  80,  80)
    WHITE        = (255, 255, 255)
    GRAY         = (170, 170, 170)
    GRAY_DARK    = (100, 100, 120)
    YELLOW       = (255, 220,  60)
    GREEN        = ( 80, 220, 100)
    RED          = (220,  70,  70)
    CYAN         = ( 60, 200, 220)
    ORANGE       = (220, 150,  40)
    PURPLE       = (160,  80, 220)
    LIFE_HIGH    = ( 80, 210,  90)
    LIFE_MED     = (220, 180,  40)
    LIFE_LOW     = (210,  60,  60)


# â”€â”€ Layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HEADER_H   = 56
PLAYER_H   = 120
BATTLE_H   = 280
FOOTER_H   = 180
CARD_W     = 110
CARD_H     = 150
CARD_GAP   = 14
SUP_W      = 90
SUP_H      = 60
MAX_SLOTS  = 5

KW_SHORT = {
    "Voar": "âœˆ", "Furtivo": "ðŸ‘»", "Investida": "âš¡",
    "Atropelar": "ðŸ‚", "Veloz": "ðŸ’¨", "Toque da Morte": "â˜ ",
    "Roubo de Vida": "ðŸ©¸", "Robusto": "ðŸ›¡", "Indomavel": "ðŸ”¥",
    "Indestrutivel": "ðŸ’Ž",
}


# â”€â”€ Classe Renderer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class Renderer:
    W   = 1024
    H   = 900
    FPS = 60

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Hemsfell Heroes â€” Visualizador")
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.clock  = pygame.time.Clock()
        self.art    = CardArtLibrary()
        self._init_fonts()

    def _init_fonts(self):
        def font(size, bold=False):
            try:
                return pygame.font.SysFont("segoeui", size, bold=bold)
            except:
                return pygame.font.Font(None, size)
        self.f_title = font(22, bold=True)
        self.f_name  = font(16, bold=True)
        self.f_body  = font(14)
        self.f_small = font(12)
        self.f_tiny  = font(10)
        self.f_hero  = font(18, bold=True)
        self.f_big   = font(28, bold=True)
        self.f_event = font(20, bold=True)
        self.f_ctrl  = font(13)

    # â”€â”€ Primitivas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def txt(self, surf, text, font, color, x, y, anchor="topleft", max_w=0):
        if max_w and font.size(text)[0] > max_w:
            while text and font.size(text + "â€¦")[0] > max_w:
                text = text[:-1]
            text += "â€¦"
        s = font.render(text, True, color)
        r = s.get_rect()
        setattr(r, anchor, (x, y))
        surf.blit(s, r)
        return r

    def pill(self, surf, x, y, w, h, color, radius=6):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, color, rect, border_radius=radius)
        return rect

    def life_color(self, life: int) -> tuple:
        if life > 15: return C.LIFE_HIGH
        if life >  8: return C.LIFE_MED
        return C.LIFE_LOW

    # â”€â”€ Carta â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def draw_card(self, surf, card: dict, x: int, y: int,
                  is_attacker=False, is_blocker=False, highlight=False) -> pygame.Rect:
        if card is None:
            return pygame.Rect(x, y, CARD_W, CARD_H)

        tapped = card["tapped"]
        if tapped:
            bg_col, bdr_col = C.CARD_TAPPED, (80, 60, 60)
        elif is_attacker:
            bg_col, bdr_col = (50, 40, 15), C.CARD_ATTACK
        elif is_blocker:
            bg_col, bdr_col = (15, 40, 55), C.CARD_BLOCK
        elif highlight:
            bg_col, bdr_col = (45, 45, 75), C.BORDER_LIT
        else:
            bg_col, bdr_col = C.CARD_BG, C.CARD_BDR

        w, h = CARD_W, CARD_H
        rect = pygame.Rect(x, y, w, h)

        # Glow effect for highlight
        if highlight:
            glow_surf = pygame.Surface((w + 10, h + 10), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*C.BORDER_LIT, 100), glow_surf.get_rect(), border_radius=10)
            surf.blit(glow_surf, (x - 5, y - 5))

        # sombra
        pygame.draw.rect(surf, (8, 8, 16),
                         pygame.Rect(x+3, y+3, w, h), border_radius=8)
        pygame.draw.rect(surf, bg_col, rect, border_radius=8)
        pygame.draw.rect(surf, bdr_col, rect, width=2, border_radius=8)

        # nome (atÃ© 2 linhas)
        name   = card["name"]
        words  = name.split()
        lines, cur = [], ""
        for word in words:
            test = (cur + " " + word).strip()
            if self.f_small.size(test)[0] <= w - 10:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = word
        if cur: lines.append(cur)
        for i, ln in enumerate(lines[:2]):
            self.txt(surf, ln, self.f_small, C.WHITE, x+5, y+6+i*14)

        # raÃ§a
        if card["race"]:
            self.txt(surf, card["race"][:14], self.f_tiny, C.GRAY_DARK,
                     x+5, y+36, max_w=w-10)

        pygame.draw.line(surf, bdr_col, (x+4, y+50), (x+w-4, y+50))

        art = self.art.get_scaled_surface(card["name"], (w-10, 44))
        if art is not None:
            surf.blit(art, (x+5, y+54))
        else:
            pygame.draw.rect(surf, (26, 26, 42), (x+5, y+54, w-10, 44), border_radius=4)
            self.txt(surf, card["name"][:12], self.f_tiny, C.GRAY_DARK, x+8, y+72)

        # off / vit
        self.txt(surf, str(card["off"]), self.f_hero, C.YELLOW,
                 x+w//2-14, y+100, anchor="topright")
        self.txt(surf, "/", self.f_name, C.GRAY, x+w//2, y+104, anchor="midtop")
        self.txt(surf, str(card["vit"]), self.f_hero, C.GREEN,
                 x+w//2+16, y+100, anchor="topleft")

        # custo
        self.txt(surf, f"â—†{card['cost']}", self.f_small, C.CYAN,
                 x+w-6, y+6, anchor="topright")

        # keywords
        badges = [KW_SHORT.get(k, k[:2]) for k in card["keywords"][:4]]
        if badges:
            self.txt(surf, " ".join(badges), self.f_tiny, C.ORANGE, x+4, y+124)

        # status
        if card["status"]:
            col = C.RED if any(s in card["status"] for s in ["Congelado","Atordoado"]) \
                  else C.PURPLE
            self.txt(surf, ", ".join(s[:6] for s in card["status"][:2]),
                     self.f_tiny, col, x+4, y+124)

        # markers / effects summary
        markers = []
        for mk, val in card["markers"].items():
            if val:
                markers.append(f"{val}×{mk[:6]}")
        if markers:
            self.txt(surf, " ".join(markers[:2]), self.f_tiny, C.GREEN,
                     x+4, y+140)

        # attack/block badge
        if is_attacker or is_blocker or tapped:
            badge = None
            badge_col = C.YELLOW
            if is_attacker and is_blocker:
                badge = "ATK/BLK"
                badge_col = C.ORANGE
            elif is_attacker:
                badge = "ATACA"
                badge_col = C.ORANGE
            elif is_blocker:
                badge = "BLOQ"
                badge_col = C.CYAN
            elif tapped:
                badge = "TAP"
                badge_col = C.GRAY_DARK
            if badge:
                badge_rect = pygame.Rect(x+w-54, y+6, 48, 18)
                pygame.draw.rect(surf, badge_col, badge_rect, border_radius=6)
                self.txt(surf, badge, self.f_tiny, C.PANEL_DARK,
                         badge_rect.centerx, badge_rect.centery, anchor="center")

        # marcadores +1/+1
        m11 = card["markers"].get("+1/+1", 0)
        if m11 > 0:
            self.txt(surf, f"+{m11}", self.f_tiny, C.GREEN, x+4, y+h-20)

        # summoning sickness
        if card["sick"]:
            pygame.draw.circle(surf, C.GRAY_DARK, (x+w-10, y+h-10), 5)

        return rect

    def draw_support_card(self, surf, card: dict | None, x: int, y: int):
        w, h = SUP_W, SUP_H
        rect = pygame.Rect(x, y, w, h)
        if card is None:
            pygame.draw.rect(surf, (25, 25, 42), rect, border_radius=5)
            pygame.draw.rect(surf, (40, 40, 65), rect, width=1, border_radius=5)
            return rect
        pygame.draw.rect(surf, (35, 28, 55), rect, border_radius=5)
        pygame.draw.rect(surf, (110, 80, 160), rect, width=2, border_radius=5)
        self.txt(surf, card["name"][:12], self.f_tiny, C.PURPLE, x+3, y+3, max_w=w-6)
        return rect
    def draw_hand_preview(self, surf, hand: list[dict], x: int, y: int, limit: int = 4, W: int = 0):
        if not hand:
            return
        card_w = min(80, (W - 20) // len(hand[:limit]))
        for i, c in enumerate(hand[:limit]):
            rect = pygame.Rect(x + i * (card_w + 6), y, card_w, 60)
            pygame.draw.rect(surf, (24, 24, 40), rect, border_radius=5)
            pygame.draw.rect(surf, C.BORDER, rect, width=1, border_radius=5)
            img = self.art.get_scaled_surface(c["name"], (card_w-10, 36))
            if img is not None:
                surf.blit(img, (rect.x + 5, rect.y + 4))
            else:
                self.txt(surf, c["name"][:8], self.f_tiny, C.GRAY, rect.x+5, rect.y+8)
            self.txt(surf, f"{c['cost']}", self.f_small, C.CYAN,
                     rect.x + rect.w - 8, rect.y + rect.h - 16, anchor="topright")
        if len(hand) > limit:
            self.txt(surf, f"+{len(hand)-limit}", self.f_small, C.GRAY,
                     x + limit * (card_w + 6) - 4, y + 30, anchor="topright")
    # â”€â”€ Painel do jogador â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def draw_player_header(self, surf, pdata: dict, is_active: bool,
                           x: int, y: int, w: int, h: int, color: tuple,
                           hand: list[dict] | None = None):
        bg = (34, 32, 66) if is_active else (20, 20, 35)
        pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=8)
        if is_active:
            pygame.draw.rect(surf, color, (x, y, w, h), width=2, border_radius=8)
            self.pill(surf, x+w-74, y+10, 62, 22, C.GREEN, radius=6)
            self.txt(surf, "ATIVO", self.f_small, C.PANEL_DARK,
                     x+w-42, y+21, anchor="center")

        cx, cy = x+12, y+8
        level_col = [C.GRAY, C.CYAN, C.YELLOW, C.ORANGE][pdata["hero_level"]]
        self.txt(surf, pdata["hero_name"], self.f_hero, color, cx, cy)
        self.txt(surf, f"  Nv{pdata['hero_level']}", self.f_name, level_col,
                 cx + self.f_hero.size(pdata["hero_name"])[0], cy+2)
        cy += 28

        # barra de vida
        life    = pdata["life"]
        lc      = self.life_color(life)
        bar_w   = max(0, min(w-24, int((life/30)*(w-24))))
        pygame.draw.rect(surf, (40, 40, 60), (cx, cy, w-24, 14), border_radius=4)
        if bar_w > 0:
            pygame.draw.rect(surf, lc, (cx, cy, bar_w, 14), border_radius=4)
        self.txt(surf, f"♥ {life}/30", self.f_small, lc,
                 cx+(w-24)//2, cy+1, anchor="midtop")
        cy += 18

        self.txt(surf,
                 f"⚡ {pdata['energy']}/{pdata['max_energy']}   +{pdata['reserve']}R",
                 self.f_small, C.CYAN, cx, cy)
        cy += 18

        self.txt(surf,
                 f"🃏 {pdata['hand_count']}   📚 {pdata['deck_count']}   ⚰ {pdata['gy_count']}",
                 self.f_tiny, C.GRAY, cx, cy)

    # â”€â”€ Campo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def draw_field(self, surf, pdata: dict, snap: Snapshot,
                   field_rect: tuple, is_bottom: bool, player_index: int) -> dict:
        x0, y0, fw, fh = field_rect
        label_col = C.P1 if not is_bottom else C.P2
        role = "Atacante" if snap.active_player == player_index and snap.phase == "Combate" else "Defensor" if snap.phase == "Combate" else ""
        side_txt = "Campo do Jogador 1" if not is_bottom else "Campo do Jogador 2"
        if role:
            side_txt = f"{side_txt} • {role}"
        self.txt(surf, side_txt, self.f_tiny, label_col,
                 x0+fw//2, y0+4, anchor="midtop")

        total_w  = MAX_SLOTS*CARD_W + (MAX_SLOTS-1)*CARD_GAP
        start_x  = x0 + (fw-total_w)//2
        card_y   = y0 + (fh - CARD_H)//2

        slot_map: dict[int, dict | None] = {i: None for i in range(MAX_SLOTS)}
        for c in pdata["field"]:
            if c and c["slot"] is not None:
                slot_map[c["slot"]] = c

        rects = {}
        for slot in range(MAX_SLOTS):
            cx = start_x + slot*(CARD_W+CARD_GAP)
            if slot_map[slot] is None:
                empty = pygame.Rect(cx, card_y, CARD_W, CARD_H)
                pygame.draw.rect(surf, (22, 22, 38), empty, border_radius=8)
                pygame.draw.rect(surf, (40, 40, 65), empty, width=1, border_radius=8)
                self.txt(surf, f"[{slot}]", self.f_tiny, C.GRAY_DARK,
                         cx+CARD_W//2, card_y+CARD_H//2, anchor="center")
            else:
                c   = slot_map[slot]
                iid = c["iid"]
                r   = self.draw_card(surf, c, cx, card_y,
                                     is_attacker=iid in snap.attackers,
                                     is_blocker=iid in snap.blockers,
                                     highlight=iid in snap.highlight_iids)
                rects[iid] = r

        return rects

    # â”€â”€ Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def draw_log(self, surf, snap: Snapshot, x, y, w, h):
        pygame.draw.rect(surf, C.PANEL_DARK, (x, y, w, h), border_radius=6)
        pygame.draw.rect(surf, C.BORDER,     (x, y, w, h), width=1, border_radius=6)
        line_h  = 15
        visible = h//line_h - 1
        shown   = snap.log_lines[-visible:] if len(snap.log_lines) > visible \
                  else snap.log_lines
        for i, ln in enumerate(shown):
            col = C.GRAY
            if "ðŸŒŸ" in ln or "NÃVEL" in ln:    col = C.YELLOW
            elif "ðŸ’€" in ln:                    col = C.RED
            elif "âš”ï¸" in ln or "ðŸ’¢" in ln:     col = C.ORANGE
            elif "ðŸ‰" in ln or "invoca" in ln:  col = C.GREEN
            elif "ðŸª„" in ln or "conjura" in ln: col = C.CYAN
            elif "ðŸ›¡ï¸" in ln or "bloqueia" in ln: col = C.P1
            self.txt(surf, ln.lstrip()[:80], self.f_tiny, col, x+6, y+4+i*line_h)

    def draw_effect_summary(self, surf, snap: Snapshot, x: int, y: int, w: int, h: int):
        pygame.draw.rect(surf, C.PANEL_DARK, (x, y, w, h), border_radius=6)
        pygame.draw.rect(surf, C.BORDER,     (x, y, w, h), width=1, border_radius=6)
        self.txt(surf, "Resumo de combate", self.f_small, C.WHITE, x+10, y+10)
        self.txt(surf, f"Jogador ativo: {'1' if snap.active_player == 0 else '2'}", self.f_tiny, C.CYAN, x+10, y+30)
        self.txt(surf, f"Fase: {snap.phase}", self.f_tiny, C.GRAY, x+10, y+44)

        attackers = [c for p in [snap.p1, snap.p2] for c in p['field']
                     if c and c['iid'] in snap.attackers]
        blockers  = [c for p in [snap.p1, snap.p2] for c in p['field']
                     if c and c['iid'] in snap.blockers]
        self.txt(surf, "Atacantes:", self.f_tiny, C.ORANGE, x+10, y+64)
        ay = y+78
        if attackers:
            for a in attackers[:3]:
                self.txt(surf, f"• {a['name']} ({a['off']}/{a['vit']})", self.f_tiny, C.WHITE, x+14, ay)
                ay += 14
        else:
            self.txt(surf, "• nenhum", self.f_tiny, C.GRAY, x+14, ay)
            ay += 14
        self.txt(surf, "Bloqueadores:", self.f_tiny, C.CYAN, x+10, ay)
        ay += 14
        if blockers:
            for b in blockers[:3]:
                self.txt(surf, f"• {b['name']} ({b['off']}/{b['vit']})", self.f_tiny, C.WHITE, x+14, ay)
                ay += 14
        else:
            self.txt(surf, "• nenhum", self.f_tiny, C.GRAY, x+14, ay)
            ay += 14

        self.txt(surf, "Efeitos em campo:", self.f_tiny, C.YELLOW, x+10, ay)
        ay += 14
        effects = []
        for p in [snap.p1, snap.p2]:
            for c in p['field']:
                if c and (c['status'] or any(v for v in c['markers'].values())):
                    desc = []
                    if c['status']:
                        desc.append("/".join(s[:5] for s in c['status'][:2]))
                    markers = [f"{v}×{k[:4]}" for k, v in c['markers'].items() if v]
                    if markers:
                        desc.append(" ".join(markers[:2]))
                    effects.append(f"{c['name']}: {' '.join(desc)}")
        if effects:
            for eff in effects[:4]:
                self.txt(surf, eff, self.f_tiny, C.WHITE, x+10, ay)
                ay += 14
        else:
            self.txt(surf, "• nenhum ativo", self.f_tiny, C.GRAY, x+10, ay)

    # â”€â”€ CabeÃ§alho â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def draw_header(self, surf, snap: Snapshot, idx: int, total: int,
                    auto_play: bool, auto_delay: float, W: int):
        pygame.draw.rect(surf, C.PANEL, (0, 0, W, HEADER_H))
        pygame.draw.line(surf, C.BORDER, (0, HEADER_H), (W, HEADER_H))
        self.txt(surf, f"TURNO {snap.turn}", self.f_title, C.WHITE, 16, 16)
        self.pill(surf, 120, 12, 110, 32, snap.phase_color, radius=8)
        self.txt(surf, snap.phase, self.f_name, C.PANEL_DARK, 175, 28, anchor="center")
        self.txt(surf, snap.event, self.f_event, C.WHITE,
                 W//2, 28, anchor="center", max_w=600)
        self.txt(surf, f"{idx+1}/{total}", self.f_small, C.GRAY_DARK,
                 W-80, 28, anchor="center")
        if auto_play:
            self.pill(surf, W-150, 14, 60, 26, C.GREEN, radius=6)
            self.txt(surf, f"▶ {auto_delay:.1f}s", self.f_small, C.PANEL_DARK,
                     W-120, 27, anchor="center")


    def draw_tooltip(self, surf, card: dict, mx: int, my: int, W: int, H: int):
        TW, TH = 220, 160
        tx = min(mx+10, W-TW-4)
        ty = min(my+10, H-TH-4)
        pygame.draw.rect(surf, (20, 20, 38), (tx, ty, TW, TH), border_radius=8)
        pygame.draw.rect(surf, C.BORDER_LIT, (tx, ty, TW, TH),
                         width=2, border_radius=8)
        cy = ty+6
        self.txt(surf, card["name"], self.f_name, C.WHITE, tx+6, cy, max_w=TW-12)
        cy += 20
        self.txt(surf, card["race"], self.f_tiny, C.GRAY_DARK, tx+6, cy)
        cy += 14
        self.txt(surf, f"Ofensividade: {card['off']} (base {card['base_off']})",
                 self.f_small, C.YELLOW, tx+6, cy); cy += 16
        self.txt(surf, f"Vitalidade:   {card['vit']} (base {card['base_vit']})",
                 self.f_small, C.GREEN, tx+6, cy);  cy += 16
        self.txt(surf, f"Custo: {card['cost']}", self.f_small, C.CYAN, tx+6, cy); cy += 14
        if card["keywords"]:
            for ln in textwrap.wrap(", ".join(card["keywords"]), width=28):
                self.txt(surf, ln, self.f_tiny, C.ORANGE, tx+6, cy); cy += 12
        if card["status"]:
            self.txt(surf, "Status: " + ", ".join(card["status"]),
                     self.f_tiny, C.RED, tx+6, cy); cy += 12
        for mk, val in card["markers"].items():
            self.txt(surf, f"+{val}x {mk}", self.f_tiny, C.GREEN, tx+6, cy); cy += 12

    def render_frame(self, snap: Snapshot, idx: int, total: int,
                     auto_play: bool, auto_delay: float):
        surf = self.screen
        surf.fill(C.BG)

        W, H = surf.get_size()

        # Header
        self.draw_header(surf, snap, idx, total, auto_play, auto_delay, W)

        # Player 1 (top)
        self.draw_player_header(
            surf, snap.p1, snap.active_player == 0,
            2, HEADER_H+2, W-4, PLAYER_H, C.P1
        )

        # Battle field
        battle_y = HEADER_H + PLAYER_H + 4
        pygame.draw.line(surf, C.BORDER, (0, battle_y), (W, battle_y), 2)
        rects_p1 = self.draw_field(
            surf, snap.p1, snap,
            (2, battle_y, W-4, BATTLE_H//2), is_bottom=False, player_index=0
        )

        mid_battle = battle_y + BATTLE_H//2
        pygame.draw.line(surf, C.BORDER, (0, mid_battle), (W, mid_battle), 2)
        rects_p2 = self.draw_field(
            surf, snap.p2, snap,
            (2, mid_battle, W-4, BATTLE_H//2), is_bottom=True, player_index=1
        )

        # Player 2 (bottom)
        player2_y = battle_y + BATTLE_H + 4
        self.draw_player_header(
            surf, snap.p2, snap.active_player == 1,
            2, player2_y, W-4, PLAYER_H, C.P2
        )

        # Hand preview for active player
        hand_y = player2_y + PLAYER_H + 4
        if snap.active_player == 0:
            self.draw_hand_preview(surf, snap.p1["hand"], 10, hand_y, limit=7, W=W)
        else:
            self.draw_hand_preview(surf, snap.p2["hand"], 10, hand_y, limit=7, W=W)

        # Footer
        fy = H - FOOTER_H
        pygame.draw.line(surf, C.BORDER, (0, fy), (W, fy))
        log_w = W - 400
        self.draw_log(surf, snap, 4, fy+4, log_w-8, FOOTER_H-8)
        self.draw_effect_summary(surf, snap, log_w+10, fy+4, 260, FOOTER_H-8)
        cx = W - 120
        self.txt(surf, "CONTROLES", self.f_name, C.GRAY, cx, fy+6)
        controls = [
            ("ESPAÇO / →", "Avançar"),
            ("←",          "Voltar"),
            ("A",          "Auto-play on/off"),
            ("+ / -",      "Velocidade"),
            ("R",          "Nova partida"),
            ("ESC / Q",    "Sair"),
        ]
        for i, (key, desc) in enumerate(controls):
            self.pill(surf, cx, fy+26+i*22, 70, 18, C.PANEL, radius=4)
            self.txt(surf, key,  self.f_ctrl, C.YELLOW, cx+4,  fy+27+i*22)
            self.txt(surf, desc, self.f_ctrl, C.GRAY,   cx+80, fy+27+i*22)

        # tooltip em hover
        mx, my = pygame.mouse.get_pos()
        for iid, r in {**rects_p1, **rects_p2}.items():
            if r.collidepoint(mx, my):
                for p in [snap.p1, snap.p2]:
                    for c in p["field"] + p["hand"]:
                        if c and c["iid"] == iid:
                            self.draw_tooltip(surf, c, mx, my, W, H)
                            break
                break

        pygame.display.flip()


