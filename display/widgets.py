"""
Shared rendering primitives used by screen modules.
"""
import os

from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, QR_DISPLAY_SIZE
from display.qr import QR
from display.theme import (
    BG,
    BG_SURFACE,
    BORDER,
    BORDER_DIM,
    CYAN,
    FOOTER_H,
    GREEN,
    HEADER_H,
    RED,
    TEXT_SEC,
    TEXT,
    TEXT_MUTED,
)

_FONT_CACHE: dict = {}
_IMAGE_CACHE: dict = {}


def get_font(size: int = 16):
    if size not in _FONT_CACHE:
        import pygame
        candidates = ("DejaVu Sans", "Liberation Sans", "FreeSans")
        selected = None
        for name in candidates:
            try:
                path = pygame.font.match_font(name)
                if path:
                    selected = pygame.font.Font(path, size)
                    break
            except Exception:
                continue
        if selected is None:
            try:
                selected = pygame.font.SysFont("monospace", size)
            except Exception:
                selected = pygame.font.Font(None, size)
        _FONT_CACHE[size] = selected
    return _FONT_CACHE[size]


def render_text(surface, text: str, pos: tuple[int, int], color=(255, 255, 255), size: int = 16):
    import pygame
    font = get_font(size)
    surf = font.render(text, True, color)
    surface.blit(surf, pos)


def render_text_centered(surface, text: str, center: tuple[int, int], color=(255, 255, 255), size: int = 20):
    import pygame
    font = get_font(size)
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=center)
    surface.blit(surf, rect)


def truncate_text(text: str, size: int, max_px: int, suffix: str = "...") -> str:
    """Trim text to fit pixel width for the current font."""
    font = get_font(size)
    if font.size(text)[0] <= max_px:
        return text
    if font.size(suffix)[0] >= max_px:
        return suffix
    trimmed = text
    while trimmed and font.size(trimmed + suffix)[0] > max_px:
        trimmed = trimmed[:-1]
    return (trimmed + suffix) if trimmed else suffix


_QR = QR()


def render_qr(
    surface,
    data: str,
    center: tuple[int, int],
    size: int = QR_DISPLAY_SIZE,
    *,
    style: int = QR.STYLE__DEFAULT,
    background_color: str = "white",
    border: int = 3,
    error_correction: str = "M",
):
    """Render a QR code (from a UR string or any string) centered at `center`."""
    import pygame

    img = _QR.qrimage(
        data,
        width=size,
        height=size,
        border=border,
        style=style,
        background_color=background_color,
        error_correction=error_correction,
    ).convert("RGB")

    pg_surf = pygame.image.fromstring(img.tobytes(), img.size, "RGB")
    rect = pg_surf.get_rect(center=center)
    surface.blit(pg_surf, rect)


def _get_image(path: str):
    if path in _IMAGE_CACHE:
        return _IMAGE_CACHE[path]
    if not os.path.exists(path):
        _IMAGE_CACHE[path] = None
        return None
    import pygame

    try:
        img = pygame.image.load(path).convert_alpha()
    except Exception:
        img = None
    _IMAGE_CACHE[path] = img
    return img


def render_stellar_logo(surface, center: tuple[int, int], size: int = 16, color=CYAN):
    """
    Render a Stellar mark.
    Uses assets/stellar_logo.png or assets/stellar.png when present, otherwise a vector fallback.
    """
    import pygame

    for path in (
        "/home/pi/stellar-firmware/assets/stellar_logo.png",
        "/home/pi/stellar-firmware/assets/stellar.png",
    ):
        img = _get_image(path)
        if img is not None:
            scaled = pygame.transform.smoothscale(img, (size, size))
            rect = scaled.get_rect(center=center)
            surface.blit(scaled, rect)
            return

    # Vector fallback: circular ring + orbital slash (stylized Stellar-like mark).
    cx, cy = center
    r = max(5, size // 2)
    pygame.draw.circle(surface, color, center, r, width=2)
    x1, y1 = cx - int(r * 0.95), cy + int(r * 0.35)
    x2, y2 = cx + int(r * 0.95), cy - int(r * 0.35)
    pygame.draw.line(surface, color, (x1, y1), (x2, y2), 2)
    pygame.draw.circle(surface, color, (x1, y1), 1)
    pygame.draw.circle(surface, color, (x2, y2), 1)


def render_header(surface, left_label: str, right_label: str, accent=CYAN, alpha: int = 255):
    import pygame

    header = pygame.Surface((DISPLAY_WIDTH, HEADER_H), pygame.SRCALPHA)
    header.fill((*BG_SURFACE, alpha))
    surface.blit(header, (0, 0))
    pygame.draw.line(surface, BORDER_DIM, (0, HEADER_H - 1), (DISPLAY_WIDTH, HEADER_H - 1), 1)

    dot_y = HEADER_H // 2
    pygame.draw.circle(surface, accent, (14, dot_y), 4)
    render_text(surface, left_label, (24, 8), color=TEXT, size=13)
    right = truncate_text(right_label, 13, 132)
    right_w = get_font(13).size(right)[0]
    render_text(surface, right, (DISPLAY_WIDTH - 12 - right_w, 8), color=accent, size=13)


def render_footer(
    surface,
    left_label: str,
    right_label: str | None = None,
    left_color=GREEN,
    right_color=RED,
):
    import pygame

    y = DISPLAY_HEIGHT - FOOTER_H
    pygame.draw.line(surface, BORDER, (0, y), (DISPLAY_WIDTH, y), 1)

    if right_label is None:
        pygame.draw.rect(surface, BG_SURFACE, (0, y + 1, DISPLAY_WIDTH, FOOTER_H - 1))
        render_text_centered(surface, left_label, (DISPLAY_WIDTH // 2, y + FOOTER_H // 2), color=TEXT_MUTED, size=13)
        return

    half = DISPLAY_WIDTH // 2
    pygame.draw.rect(surface, left_color, (0, y + 1, half - 1, FOOTER_H - 1))
    pygame.draw.rect(surface, right_color, (half + 1, y + 1, DISPLAY_WIDTH - half - 1, FOOTER_H - 1))
    render_text_centered(surface, left_label, (half // 2, y + FOOTER_H // 2), color=TEXT, size=13)
    render_text_centered(surface, right_label, (half + half // 2, y + FOOTER_H // 2), color=TEXT, size=13)


def render_error(surface, message: str):
    surface.fill(BG)
    render_header(surface, "ERROR", "BW · PI", accent=RED)
    render_text_centered(surface, "ERROR", (DISPLAY_WIDTH // 2, 118), color=RED, size=32)
    # Word-wrap message
    words = message.split()
    line, lines = [], []
    for w in words:
        if len(" ".join(line + [w])) > 38:
            lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))
    y = 180
    for l in lines:
        render_text_centered(surface, l, (DISPLAY_WIDTH // 2, y), color=TEXT, size=14)
        y += 20
    render_text_centered(surface, "Review request and try again", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 62), color=TEXT_SEC, size=12)
    render_footer(surface, "Press any button to restart")
