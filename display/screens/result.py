"""Result screen: animated QR loop for export/sign responses."""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, QR_DISPLAY_SIZE
from display.theme import BG, BORDER, CYAN, FOOTER_H, PURPLE, TEXT_SEC
from display.widgets import render_footer, render_header, render_qr, render_stellar_logo, render_text_centered


def render(
    surface,
    qr_part: str,
    *,
    part_index: int = 1,
    total_parts: int = 1,
    chain: str = "XLM",
) -> None:
    import pygame

    surface.fill(BG)
    chain_label = chain.upper() if chain else "XLM"
    accent = PURPLE if "ETH" in chain_label else CYAN
    render_header(surface, chain_label, "SIGNED OUTPUT", accent=accent)
    if accent == CYAN:
        render_stellar_logo(surface, (DISPLAY_WIDTH // 2 - 56, 16), size=12, color=CYAN)

    qr_center = (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 + 6)
    frame_rect = pygame.Rect(0, 0, QR_DISPLAY_SIZE + 12, QR_DISPLAY_SIZE + 12)
    frame_rect.center = qr_center
    pygame.draw.rect(surface, BORDER, frame_rect, width=1, border_radius=6)
    render_qr(surface, qr_part, center=qr_center, size=QR_DISPLAY_SIZE, error_correction="M", border=2)

    render_text_centered(
        surface,
        f"Part {part_index} / {max(1, total_parts)}",
        (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - FOOTER_H - 16),
        size=13,
        color=TEXT_SEC,
    )
    render_footer(surface, "Press any button when done")
