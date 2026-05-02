"""
PIN entry screen.

Renders a numeric keypad (0–9 + DEL + OK).
hit_test(pos) returns the key label at a touch position.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.theme import AMBER, BG, BG_RAISED, BORDER, BORDER_DIM, CYAN, GREEN, RED, TEXT
from display.widgets import render_header, render_text_centered

# Keypad layout: 3 columns × 4 rows
_KEYS = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["DEL", "0", "OK"],
]

_KEY_W = 80
_KEY_H = 48
_PAD_X = (DISPLAY_WIDTH - _KEY_W * 3) // 2
_PAD_Y = 142
_GAP = 8


def _key_rect(row: int, col: int) -> tuple[int, int, int, int]:
    x = _PAD_X + col * (_KEY_W + _GAP)
    y = _PAD_Y + row * (_KEY_H + _GAP)
    return x, y, _KEY_W, _KEY_H


def render(surface, digits: list[str], wrong: bool = False) -> None:
    import pygame

    surface.fill(BG)
    render_header(surface, "LOCKED", "UNLOCK", accent=AMBER)
    render_text_centered(surface, "ENTER PIN", (DISPLAY_WIDTH // 2, 62), color=TEXT, size=20)

    color = RED if wrong else CYAN
    # Draw circles instead of relying on font glyph support for bullet characters.
    dot_y = 96
    dot_radius = 9
    dot_gap = 24
    dot_count = 6
    dot_start_x = DISPLAY_WIDTH // 2 - ((dot_count - 1) * dot_gap) // 2
    for i in range(dot_count):
        center = (dot_start_x + i * dot_gap, dot_y)
        if i < len(digits):
            pygame.draw.circle(surface, color, center, dot_radius)
        else:
            pygame.draw.circle(surface, BORDER_DIM, center, dot_radius, 2)
    if wrong:
        render_text_centered(surface, "Wrong PIN", (DISPLAY_WIDTH // 2, 120), color=RED, size=14)

    # Keypad buttons
    for row, row_keys in enumerate(_KEYS):
        for col, key in enumerate(row_keys):
            x, y, w, h = _key_rect(row, col)
            pygame.draw.rect(surface, BG_RAISED, (x, y, w, h), border_radius=6)
            pygame.draw.rect(surface, BORDER, (x, y, w, h), width=1, border_radius=6)
            key_color = TEXT
            if key == "DEL":
                key_color = RED
            elif key == "OK":
                key_color = GREEN
            render_text_centered(surface, key, (x + w // 2, y + h // 2), color=key_color, size=18)


def hit_test(pos: tuple[int, int]) -> str | None:
    """Return key label at touch position, or None if miss."""
    px, py = pos
    for row, row_keys in enumerate(_KEYS):
        for col, key in enumerate(row_keys):
            x, y, w, h = _key_rect(row, col)
            if x <= px < x + w and y <= py < y + h:
                return key
    return None
