"""Signing in-progress screen."""

from config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from display.theme import BG, CYAN, PURPLE, TEXT_SEC
from display.widgets import render_header, render_stellar_logo, render_text_centered


def render(surface, chain: str = "XLM", tick: int = 0, algorithm: str | None = None) -> None:
    import pygame

    surface.fill(BG)
    chain_label = (chain or "XLM").upper()
    accent = PURPLE if "ETH" in chain_label else CYAN
    render_header(surface, "SIGNING", "BW · PI", accent=accent)
    if accent == CYAN:
        render_stellar_logo(surface, (DISPLAY_WIDTH // 2 - 52, 16), size=12, color=CYAN)

    render_text_centered(surface, "BW·PI", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 - 62), color=TEXT_SEC, size=20)
    render_text_centered(surface, "Signing...", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 - 18), color=accent, size=26)

    if not algorithm:
        algorithm = "Ed25519" if chain_label == "XLM" else "secp256k1"
    render_text_centered(surface, f"{algorithm} · {chain_label}", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 + 14), color=TEXT_SEC, size=14)

    center_x = DISPLAY_WIDTH // 2
    center_y = DISPLAY_HEIGHT // 2 + 52
    for idx in range(7):
        x = center_x - 48 + idx * 16
        if idx == tick % 7:
            pygame.draw.circle(surface, accent, (x, center_y), 4)
        else:
            pygame.draw.circle(surface, TEXT_SEC, (x, center_y), 2)
