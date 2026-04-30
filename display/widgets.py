"""
Shared rendering primitives used by screen modules.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, QR_DISPLAY_SIZE
from display.qr import QR

_FONT_CACHE: dict = {}


def get_font(size: int = 16):
    if size not in _FONT_CACHE:
        import pygame
        try:
            _FONT_CACHE[size] = pygame.font.SysFont("monospace", size)
        except Exception:
            _FONT_CACHE[size] = pygame.font.Font(None, size)
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


def render_error(surface, message: str):
    import pygame
    surface.fill((80, 0, 0))
    render_text_centered(surface, "ERROR", (DISPLAY_WIDTH // 2, 60), color=(255, 80, 80), size=28)
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
    y = 110
    for l in lines:
        render_text_centered(surface, l, (DISPLAY_WIDTH // 2, y), size=14)
        y += 20
    render_text_centered(surface, "Press any button to restart", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 30), color=(180, 180, 180), size=13)
