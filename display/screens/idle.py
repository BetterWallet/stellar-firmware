"""
Idle screen: show the wallet address as a QR code with instructions.
Scanning screen: camera preview with progress overlay.
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, GPIO_CONFIRM_PIN, GPIO_REJECT_PIN
from display.widgets import render_qr, render_text_centered


def render(surface, address: str) -> None:
    render_text_centered(surface, "Cold Wallet — Ready", (DISPLAY_WIDTH // 2, 12), size=16, color=(100, 200, 255))
    render_qr(
        surface,
        address,
        center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 - 5),
        size=180,
        error_correction="H",
    )
    # Truncated address
    short = address[:10] + "..." + address[-8:]
    render_text_centered(surface, short, (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 38), size=12, color=(160, 160, 160))
    # Instructions
    render_text_centered(surface, f"[CONFIRM] Start scanning", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 22), size=11, color=(120, 200, 120))
    render_text_centered(surface, f"[REJECT]  Show import QR", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 8), size=11, color=(180, 120, 120))


def render_scanning(surface, progress: float, overlay: bool = False, preview_enabled: bool = True) -> None:
    import pygame

    if not overlay:
        # No preview frame — keep the scan UI usable even when preview is disabled.
        surface.fill((0, 0, 0))
        if preview_enabled:
            render_text_centered(surface, "Waiting for camera...", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2), size=16, color=(150, 150, 150))
        else:
            render_text_centered(surface, "Point at MetaMask QR", (DISPLAY_WIDTH // 2, 12), size=15, color=(255, 255, 255))

    # --- Overlay on top of camera preview ---

    # Semi-transparent header bar
    header = pygame.Surface((DISPLAY_WIDTH, 28), pygame.SRCALPHA)
    header.fill((0, 0, 0, 160))
    surface.blit(header, (0, 0))

    # Scanning indicator
    if progress > 0:
        render_text_centered(surface, f"Scanning... {int(progress * 100)}%", (DISPLAY_WIDTH // 2, 12), size=15, color=(100, 255, 150))
    else:
        render_text_centered(surface, "Point at MetaMask QR", (DISPLAY_WIDTH // 2, 12), size=15, color=(255, 255, 255))

    # Targeting reticle in center
    cx, cy = DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2
    size = 80
    color = (100, 255, 150) if progress > 0 else (255, 255, 255)
    # Corner brackets
    pygame.draw.line(surface, color, (cx - size, cy - size), (cx - size + 20, cy - size), 2)
    pygame.draw.line(surface, color, (cx - size, cy - size), (cx - size, cy - size + 20), 2)
    pygame.draw.line(surface, color, (cx + size, cy - size), (cx + size - 20, cy - size), 2)
    pygame.draw.line(surface, color, (cx + size, cy - size), (cx + size, cy - size + 20), 2)
    pygame.draw.line(surface, color, (cx - size, cy + size), (cx - size + 20, cy + size), 2)
    pygame.draw.line(surface, color, (cx - size, cy + size), (cx - size, cy + size - 20), 2)
    pygame.draw.line(surface, color, (cx + size, cy + size), (cx + size - 20, cy + size), 2)
    pygame.draw.line(surface, color, (cx + size, cy + size), (cx + size, cy + size - 20), 2)

    # Progress bar at bottom
    if progress > 0:
        bar_h = 6
        bar_y = DISPLAY_HEIGHT - bar_h
        filled = int(DISPLAY_WIDTH * min(progress, 1.0))
        pygame.draw.rect(surface, (50, 200, 100), (0, bar_y, filled, bar_h))

    # Footer hint
    footer = pygame.Surface((DISPLAY_WIDTH, 20), pygame.SRCALPHA)
    footer.fill((0, 0, 0, 140))
    surface.blit(footer, (0, DISPLAY_HEIGHT - 24))
    render_text_centered(surface, "[REJECT] Cancel", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 16), size=10, color=(200, 150, 150))
