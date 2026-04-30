"""
Result screen: animated QR code loop showing the signed EthSignature UR.

The display_loop cycles through qr_frames at QR_DISPLAY_FPS.
This module only renders a single frame (the frame selection is in screen.py).
"""
from config import DISPLAY_HEIGHT, DISPLAY_WIDTH, QR_DISPLAY_SIZE
from display.widgets import render_qr, render_text_centered


def render(surface, qr_part: str) -> None:
    render_text_centered(surface, "Scan with MetaMask", (DISPLAY_WIDTH // 2, 12), size=17, color=(100, 255, 150))
    render_qr(
        surface,
        qr_part,
        center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2 + 8),
        size=QR_DISPLAY_SIZE,
        error_correction="M",
        border=2,
    )
    render_text_centered(surface, "Press any button when done", (DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 14), size=12, color=(150, 150, 150))
