"""
QR code scanning tuned for Raspberry Pi.

The scanner prioritizes a cheap, low-latency path first, then escalates to a
heavier set of preprocessing passes only after repeated misses. This keeps the
Pi focused on the newest animated UR frames instead of over-processing stale
ones.
"""
from dataclasses import dataclass
import logging

import cv2
import numpy as np

log = logging.getLogger(__name__)

_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
_qr_detector = cv2.QRCodeDetector()


@dataclass(slots=True)
class ScanResult:
    fragments: list[str]
    strategy: str
    qr_seen: bool


def _rotate_frame(frame: np.ndarray, rotation: int) -> np.ndarray:
    turns = ((rotation // 90) % 4) if rotation % 90 == 0 else 0
    if turns == 0:
        return frame
    return np.rot90(frame, k=turns)


def _normalize_fragment(text: str) -> str | None:
    text = text.strip()
    if text.lower().startswith("ur:"):
        return text
    return None


def _crop_center(frame: np.ndarray, ratio: float) -> np.ndarray:
    if ratio >= 0.999:
        return frame
    h, w = frame.shape[:2]
    crop_w = max(1, int(w * ratio))
    crop_h = max(1, int(h * ratio))
    x0 = max(0, (w - crop_w) // 2)
    y0 = max(0, (h - crop_h) // 2)
    return frame[y0:y0 + crop_h, x0:x0 + crop_w]


def _downscale(frame: np.ndarray, max_size: int) -> np.ndarray:
    """Shrink so the longest edge is at most *max_size* pixels."""
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= max_size:
        return frame
    scale = max_size / longest
    return cv2.resize(frame, (int(w * scale), int(h * scale)),
                      interpolation=cv2.INTER_AREA)


def _candidate_images(gray: np.ndarray, aggressive: bool):
    """Yield preprocessed grayscale variants lazily — cheapest first."""
    yield ("gray", gray)
    if aggressive:
        contrast = _clahe.apply(gray)
        yield ("contrast", contrast)
        _, otsu = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        yield ("otsu", otsu)


def _decode_pyzbar(image: np.ndarray) -> tuple[list[str], bool]:
    try:
        from pyzbar.pyzbar import decode, ZBarSymbol
    except ImportError:
        log.warning("pyzbar not available — scanner returning empty results")
        return [], False

    decoded_any = False
    fragments: list[str] = []
    for result in decode(image, symbols=[ZBarSymbol.QRCODE]):
        decoded_any = True
        try:
            text = result.data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        normalized = _normalize_fragment(text)
        if normalized:
            fragments.append(normalized)
    return fragments, decoded_any


def _decode_opencv(image: np.ndarray) -> tuple[list[str], bool]:
    fragments: list[str] = []
    qr_seen = False

    try:
        ok, decoded_info, points, _ = _qr_detector.detectAndDecodeMulti(image)
    except Exception:
        ok, decoded_info, points = False, [], None

    qr_seen = qr_seen or bool(ok) or points is not None
    if ok:
        for text in decoded_info:
            normalized = _normalize_fragment(text)
            if normalized:
                fragments.append(normalized)
    if fragments:
        return fragments, qr_seen

    try:
        text, points, _ = _qr_detector.detectAndDecode(image)
    except Exception:
        text, points = "", None
    qr_seen = qr_seen or points is not None
    normalized = _normalize_fragment(text)
    return ([normalized] if normalized else []), qr_seen


def scan_frame(
    frame: np.ndarray,
    *,
    rotation: int = 0,
    roi_ratio: float = 1.0,
    decoder_mode: str = "hybrid",
    aggressive: bool = False,
    decode_max_size: int = 640,
) -> ScanResult:
    """
    Decode all QR codes in a camera frame.

    Two-pass strategy:
      1. Fast pass at *decode_max_size* — handles simple QR codes cheaply.
      2. Quality pass at 2× resolution (aggressive only) — catches dense
         animated-UR QR codes that need more pixels per module.
    """
    frame = _rotate_frame(frame, rotation)
    frame = _crop_center(frame, roi_ratio)

    mode = decoder_mode.lower()
    if mode == "pyzbar":
        decoders = (("pyzbar", _decode_pyzbar),)
    elif mode == "opencv":
        decoders = (("opencv", _decode_opencv),)
    elif mode == "fast":
        decoders = (("pyzbar", _decode_pyzbar),)
    else:
        decoders = (("pyzbar", _decode_pyzbar), ("opencv", _decode_opencv))

    seen: set[str] = set()
    fragments: list[str] = []
    qr_seen = False

    # --- fast pass at target decode size ---
    small = _downscale(frame, decode_max_size)
    gray_sm = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)

    for decoder_name, decoder in decoders:
        decoded, saw_qr = decoder(gray_sm)
        qr_seen = qr_seen or saw_qr
        for text in decoded:
            if text not in seen:
                seen.add(text)
                fragments.append(text)
        if fragments:
            return ScanResult(
                fragments=fragments,
                strategy=f"fast:{decoder_name}:gray",
                qr_seen=qr_seen,
            )

    # --- quality pass at higher resolution (aggressive mode) ---
    if aggressive or mode == "hybrid":
        full_h, full_w = frame.shape[:2]
        quality_size = min(max(full_h, full_w), decode_max_size * 2)
        upscaled = quality_size > decode_max_size * 1.3

        if upscaled:
            large = _downscale(frame, quality_size)
            gray_lg = cv2.cvtColor(large, cv2.COLOR_RGB2GRAY)
        else:
            gray_lg = gray_sm

        for image_name, image in _candidate_images(gray_lg, aggressive=True):
            if not upscaled and image_name == "gray":
                continue
            for decoder_name, decoder in decoders:
                decoded, saw_qr = decoder(image)
                qr_seen = qr_seen or saw_qr
                for text in decoded:
                    if text not in seen:
                        seen.add(text)
                        fragments.append(text)
                if fragments:
                    return ScanResult(
                        fragments=fragments,
                        strategy=f"quality:{decoder_name}:{image_name}",
                        qr_seen=qr_seen,
                    )

    strategy = "aggressive" if aggressive else "fast"
    return ScanResult(fragments=[], strategy=strategy, qr_seen=qr_seen)
