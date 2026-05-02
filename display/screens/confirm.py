"""
Transaction confirmation screen.

Renders a scrollable list of DisplayField rows with confirm/reject labels at
the bottom. Physical GPIO buttons handle confirmation — no touch needed here.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.theme import BG, BG_RAISED, BG_SURFACE, BORDER, CYAN, FOOTER_H, GREEN, HEADER_H, PURPLE, RED, TEXT, TEXT_MUTED, TEXT_SEC
from display.widgets import render_footer, render_header, render_stellar_logo, render_text, truncate_text

_ROW_H = 22
_FIELD_Y_START = HEADER_H + 14
_MAX_ROWS = (DISPLAY_HEIGHT - _FIELD_Y_START - FOOTER_H - 26) // _ROW_H
_INDENT_PX = 12
_LABEL_WIDTH = 90


def render(surface, fields: list) -> None:
    import pygame

    surface.fill(BG)
    chain = "XLM"
    for field in fields:
        if getattr(field, "label", "").lower() == "chain":
            chain = str(getattr(field, "value", "XLM")).upper()
            break
    accent = PURPLE if "ETH" in chain else CYAN
    render_header(surface, chain, "REVIEW TX", accent=accent)
    if accent == CYAN:
        render_stellar_logo(surface, (DISPLAY_WIDTH // 2 - 58, 16), size=12, color=CYAN)

    panel_x = 8
    panel_y = HEADER_H + 8
    panel_w = DISPLAY_WIDTH - 16
    panel_h = DISPLAY_HEIGHT - panel_y - FOOTER_H - 8
    pygame.draw.rect(surface, BG_SURFACE, (panel_x, panel_y, panel_w, panel_h), border_radius=6)
    pygame.draw.rect(surface, BORDER, (panel_x, panel_y, panel_w, panel_h), width=1, border_radius=6)

    # Render visible fields in panel
    visible = fields[:_MAX_ROWS]
    for i, field in enumerate(visible):
        y = _FIELD_Y_START + i * _ROW_H
        row_bg = BG if i % 2 == 0 else BG_RAISED
        pygame.draw.rect(surface, row_bg, (panel_x + 4, y - 2, panel_w - 8, _ROW_H), border_radius=3)
        x = panel_x + 10 + field.indent * _INDENT_PX
        label_color = accent if not field.indent and not field.value else TEXT_SEC
        value_color = TEXT

        if field.value:
            label = truncate_text(f"{field.label}:", 13, _LABEL_WIDTH)
            value = truncate_text(str(field.value), 14, panel_w - (x + _LABEL_WIDTH + 18))
            render_text(surface, label, (x, y), color=label_color, size=13)
            render_text(surface, value, (x + _LABEL_WIDTH + 4, y), color=value_color, size=14)
        else:
            render_text(surface, truncate_text(field.label, 15, panel_w - 26), (x, y), color=label_color, size=15)

    if len(fields) > _MAX_ROWS:
        render_text(surface, f"More fields: {len(fields) - _MAX_ROWS}", (12, DISPLAY_HEIGHT - FOOTER_H - 18), color=TEXT_MUTED, size=12)

    render_footer(surface, "CONFIRM", "REJECT", left_color=GREEN, right_color=RED)
