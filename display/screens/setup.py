"""
First-boot setup screen: display the 12 mnemonic words in a grid.

User must read and write them down, then tap the screen to confirm.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.widgets import render_text, render_text_centered


def render(surface, words: list[str]) -> None:
    render_text_centered(surface, "Write down your seed phrase", (DISPLAY_WIDTH // 2, 14), size=16, color=(255, 220, 50))
    render_text_centered(surface, "NEVER share these words with anyone", (DISPLAY_WIDTH // 2, 32), size=12, color=(255, 100, 100))

    # 2-column grid of numbered words
    col_x = [20, DISPLAY_WIDTH // 2 + 10]
    y_start = 56
    row_h = 20
    for i, word in enumerate(words):
        col = i // 6
        row = i % 6
        x = col_x[col]
        y = y_start + row * row_h
        render_text(surface, f"{i+1:>2}. {word}", (x, y), size=16)

    render_text_centered(
        surface,
        "Tap anywhere when written down  →",
        (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 20),
        color=(180, 180, 180),
        size=13,
    )
