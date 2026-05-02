"""
Transaction confirmation screen.

Renders a scrollable list of DisplayField rows with confirm/reject labels at
the bottom. Physical GPIO buttons handle confirmation — no touch needed here.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, GPIO_CONFIRM_PIN, GPIO_REJECT_PIN
from display.widgets import render_text, render_text_centered

_ROW_H = 18
_FIELD_Y_START = 28
_FOOTER_H = 36
_MAX_ROWS = (DISPLAY_HEIGHT - _FIELD_Y_START - _FOOTER_H) // _ROW_H
_INDENT_PX = 12


def render(surface, fields: list) -> None:
    import pygame

    render_text_centered(surface, "Review & Confirm", (DISPLAY_WIDTH // 2, 10), size=17, color=(255, 220, 50))

    # Render visible window of fields
    visible = fields[:_MAX_ROWS]
    for i, field in enumerate(visible):
        y = _FIELD_Y_START + i * _ROW_H
        x = 8 + field.indent * _INDENT_PX
        label_color = (160, 200, 255) if not field.indent else (200, 200, 200)
        value_color = (255, 255, 255)

        if field.value:
            # label: value on one line, truncate to fit
            text = f"{field.label}: {field.value}"
            if len(text) > 52:
                text = text[:49] + "..."
            render_text(surface, text, (x, y), color=value_color, size=14)
        else:
            # Section header
            render_text(surface, field.label, (x, y), color=label_color, size=15)

    if len(fields) > _MAX_ROWS:
        render_text_centered(surface, f"↑ {len(fields) - _MAX_ROWS} more fields", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - _FOOTER_H - 4), size=12, color=(120, 120, 120))

    # Footer: confirm / reject button labels
    footer_y = DISPLAY_HEIGHT - _FOOTER_H
    pygame.draw.line(surface, (80, 80, 80), (0, footer_y), (DISPLAY_WIDTH, footer_y), 1)
    pygame.draw.rect(surface, (20, 80, 30), (0, footer_y + 1, DISPLAY_WIDTH // 2 - 1, _FOOTER_H - 1))
    pygame.draw.rect(surface, (80, 20, 20), (DISPLAY_WIDTH // 2 + 1, footer_y + 1, DISPLAY_WIDTH // 2 - 1, _FOOTER_H - 1))
    render_text_centered(surface, f"CONFIRM (GPIO {GPIO_CONFIRM_PIN})", (DISPLAY_WIDTH // 4, footer_y + _FOOTER_H // 2), size=13)
    render_text_centered(surface, f"REJECT  (GPIO {GPIO_REJECT_PIN})", (3 * DISPLAY_WIDTH // 4, footer_y + _FOOTER_H // 2), size=13)
