"""
PIN entry screen.

Renders a numeric keypad (0–9 + DEL + OK).
hit_test(pos) returns the key label at a touch position.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.widgets import get_font, render_text, render_text_centered

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
_PAD_Y = 100
_GAP = 8


def _key_rect(row: int, col: int) -> tuple[int, int, int, int]:
    x = _PAD_X + col * (_KEY_W + _GAP)
    y = _PAD_Y + row * (_KEY_H + _GAP)
    return x, y, _KEY_W, _KEY_H


def render(surface, digits: list[str], wrong: bool = False) -> None:
    import pygame

    # Title
    render_text_centered(surface, "Enter PIN", (DISPLAY_WIDTH // 2, 20), size=22)

    color = (255, 80, 80) if wrong else (255, 255, 255)
    # Draw circles instead of relying on font glyph support for bullet characters.
    dot_y = 60
    dot_radius = 8
    dot_gap = 26
    dot_count = 6
    dot_start_x = DISPLAY_WIDTH // 2 - ((dot_count - 1) * dot_gap) // 2
    for i in range(dot_count):
        center = (dot_start_x + i * dot_gap, dot_y)
        if i < len(digits):
            pygame.draw.circle(surface, color, center, dot_radius)
        else:
            pygame.draw.circle(surface, color, center, dot_radius, 2)
    if wrong:
        render_text_centered(surface, "Wrong PIN", (DISPLAY_WIDTH // 2, 80), color=(255, 80, 80), size=14)

    # Keypad buttons
    for row, row_keys in enumerate(_KEYS):
        for col, key in enumerate(row_keys):
            x, y, w, h = _key_rect(row, col)
            btn_color = (50, 50, 80) if key not in ("OK", "DEL") else (30, 80, 50) if key == "OK" else (80, 30, 30)
            pygame.draw.rect(surface, btn_color, (x, y, w, h), border_radius=6)
            pygame.draw.rect(surface, (120, 120, 180), (x, y, w, h), width=1, border_radius=6)
            render_text_centered(surface, key, (x + w // 2, y + h // 2), size=18)


def hit_test(pos: tuple[int, int]) -> str | None:
    """Return key label at touch position, or None if miss."""
    px, py = pos
    for row, row_keys in enumerate(_KEYS):
        for col, key in enumerate(row_keys):
            x, y, w, h = _key_rect(row, col)
            if x <= px < x + w and y <= py < y + h:
                return key
    return None
