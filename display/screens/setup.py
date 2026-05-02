"""
First-boot setup screen: display the 12 mnemonic words in a grid.

User must read and write them down, then tap the screen to confirm.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.theme import AMBER, BG, BG_SURFACE, BORDER, FOOTER_H, HEADER_H, TEXT, TEXT_SEC
from display.widgets import render_footer, render_header, render_text, render_text_centered


def render(surface, words: list[str]) -> None:
    import pygame

    surface.fill(BG)
    render_header(surface, "FIRST BOOT", "SETUP", accent=AMBER)

    warn_rect = pygame.Rect(12, HEADER_H + 8, DISPLAY_WIDTH - 24, 24)
    pygame.draw.rect(surface, AMBER, warn_rect, border_radius=5)
    render_text_centered(surface, "WRITE DOWN - NEVER SHARE", warn_rect.center, color=BG, size=11)

    # 2-column grid of numbered words
    panel_y = HEADER_H + 38
    panel_h = DISPLAY_HEIGHT - panel_y - FOOTER_H - 8
    panel = pygame.Rect(12, panel_y, DISPLAY_WIDTH - 24, panel_h)
    pygame.draw.rect(surface, BG_SURFACE, panel, border_radius=6)
    pygame.draw.rect(surface, BORDER, panel, width=1, border_radius=6)

    col_x = [24, DISPLAY_WIDTH // 2 + 6]
    y_start = panel_y + 12
    row_h = 20
    for i, word in enumerate(words):
        col = i // 6
        row = i % 6
        x = col_x[col]
        y = y_start + row * row_h
        render_text(surface, f"{i+1:>2}.", (x, y), color=TEXT_SEC, size=14)
        render_text(surface, word[:12], (x + 28, y), color=TEXT, size=15)

    render_footer(surface, "Tap anywhere when done")
