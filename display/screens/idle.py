"""Idle and scanning screens."""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.theme import AMBER, BG, BORDER, CYAN, GREEN, HEADER_H, TEXT, TEXT_SEC
from display.widgets import render_footer, render_header, render_qr, render_stellar_logo, render_text, render_text_centered, truncate_text


def render(surface, address: str) -> None:
    import pygame

    surface.fill(BG)
    render_header(surface, "AIR-GAPPED", "BW · PI", accent=CYAN)
    # render_stellar_logo(surface, (DISPLAY_WIDTH // 2 - 62, HEADER_H + 24), size=14, color=CYAN)
    render_text_centered(surface, "STELLAR", (DISPLAY_WIDTH // 2, HEADER_H + 24), size=17, color=CYAN)

    qr_size = 200
    qr_center = (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 - 10)
    qr_rect = pygame.Rect(0, 0, qr_size + 10, qr_size + 10)
    qr_rect.center = qr_center
    pygame.draw.rect(surface, BORDER, qr_rect, width=1, border_radius=6)
    render_qr(surface, address, center=qr_center, size=qr_size, border=2, error_correction="H")

    short = address
    if len(address) > 24:
        short = f"{address[:8]}...{address[-8:]}"
    short = truncate_text(short, 12, DISPLAY_WIDTH - 24)
    render_text_centered(surface, short, (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 64), size=12, color=TEXT_SEC)
    render_footer(surface, "SCAN TX", "QR EXPORT", left_color=GREEN, right_color=AMBER)


def render_scanning(surface, progress: float, overlay: bool = False, preview_enabled: bool = True) -> None:
    import pygame

    if not overlay:
        surface.fill(BG)
        if preview_enabled:
            render_text_centered(surface, "Waiting for camera...", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2), size=16, color=TEXT_SEC)
        else:
            render_text_centered(surface, "Point at Stellar QR", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2), size=15, color=TEXT)

    render_header(surface, "Cancel", "SCANNING", accent=CYAN, alpha=180)

    pct = max(0, min(100, int(progress * 100)))
    status = f"Scanning... {pct}%" if progress > 0 else "Point at Stellar QR"
    render_stellar_logo(surface, (DISPLAY_WIDTH // 2 - 74, DISPLAY_HEIGHT - 68), size=12, color=CYAN)
    render_text_centered(surface, status, (DISPLAY_WIDTH // 2 + 6, DISPLAY_HEIGHT - 68), size=15, color=CYAN if progress > 0 else TEXT)

    # Targeting reticle in center
    cx, cy = DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2
    size = 80
    color = CYAN
    # Corner brackets
    pygame.draw.line(surface, color, (cx - size, cy - size), (cx - size + 24, cy - size), 3)
    pygame.draw.line(surface, color, (cx - size, cy - size), (cx - size, cy - size + 24), 3)
    pygame.draw.line(surface, color, (cx + size, cy - size), (cx + size - 24, cy - size), 3)
    pygame.draw.line(surface, color, (cx + size, cy - size), (cx + size, cy - size + 24), 3)
    pygame.draw.line(surface, color, (cx - size, cy + size), (cx - size + 24, cy + size), 3)
    pygame.draw.line(surface, color, (cx - size, cy + size), (cx - size, cy + size - 24), 3)
    pygame.draw.line(surface, color, (cx + size, cy + size), (cx + size - 24, cy + size), 3)
    pygame.draw.line(surface, color, (cx + size, cy + size), (cx + size, cy + size - 24), 3)

    footer_y = DISPLAY_HEIGHT - 36
    footer = pygame.Surface((DISPLAY_WIDTH, 36), pygame.SRCALPHA)
    footer.fill((0, 0, 0, 170))
    surface.blit(footer, (0, footer_y))
    bar_x = 14
    bar_y = footer_y + 10
    bar_w = DISPLAY_WIDTH - 86
    bar_h = 8
    pygame.draw.rect(surface, BORDER, (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=4)
    filled = int((bar_w - 2) * min(progress, 1.0))
    if filled > 0:
        pygame.draw.rect(surface, GREEN, (bar_x + 1, bar_y + 1, filled, bar_h - 2), border_radius=3)
    render_text(surface, f"{pct}%", (DISPLAY_WIDTH - 56, footer_y + 6), color=TEXT, size=13)
