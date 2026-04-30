"""
QR code image generation with optional styled variants.

Provides three styles:
    STYLE__DEFAULT  — solid black squares on configurable background
    STYLE__ROUNDED  — circle module drawer with corrected registration block
    STYLE__GRID     — gapped-square module drawer

Resizing strategy (for scan reliability):
- DEFAULT style snaps to an integer multiple of the natural QR pixel size
  using `Image.NEAREST` to keep module edges crisp. Final downscale to the
  requested dimensions also uses NEAREST.
- ROUNDED / GRID styles upscale using `Image.LANCZOS` so circles stay smooth.

Falls back to the `qrencode` CLI for `qrimage_io` when present; otherwise
delegates to `qrimage`.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    CircleModuleDrawer,
    GappedSquareModuleDrawer,
)


_ERROR_CORRECTIONS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


def _resolve_ec(level) -> int:
    if isinstance(level, int):
        return level
    return _ERROR_CORRECTIONS.get(str(level).upper(), qrcode.constants.ERROR_CORRECT_M)


def _build_qr(data, *, error_correction, border, box_size):
    qr = qrcode.QRCode(
        error_correction=_resolve_ec(error_correction),
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr


def _crisp_resize(img, width, height):
    """Snap to an integer scale factor where possible, then NEAREST-resize.

    This preserves module edges. If the source is larger than the requested
    output (e.g. very dense QRs), we still downscale with NEAREST.
    """
    src_w, src_h = img.size
    if src_w == 0 or src_h == 0:
        return img.resize((width, height), Image.NEAREST)

    scale = min(width // src_w, height // src_h)
    if scale >= 1:
        snapped = img.resize((src_w * scale, src_h * scale), Image.NEAREST)
        if snapped.size != (width, height):
            canvas = Image.new(snapped.mode, (width, height), color="white")
            offset = (
                (width - snapped.size[0]) // 2,
                (height - snapped.size[1]) // 2,
            )
            canvas.paste(snapped, offset)
            return canvas
        return snapped

    return img.resize((width, height), Image.NEAREST)


class QR:
    STYLE__DEFAULT = 1
    STYLE__ROUNDED = 2
    STYLE__GRID = 3

    def __init__(self) -> None:
        return

    def qrimage(
        self,
        data,
        width=240,
        height=240,
        border=3,
        style=None,
        background_color="white",
        error_correction="M",
    ):
        """Render a QR for *data* into a `width x height` RGBA image.

        - DEFAULT style is recommended for actual on-screen scanning.
        - ROUNDED / GRID are decorative; scanability depends on the host scanner.
        """
        box_size = 10  # large natural module size keeps detail before resize
        qr = _build_qr(
            data,
            error_correction=error_correction,
            border=border,
            box_size=box_size,
        )

        if not style or style == QR.STYLE__DEFAULT:
            img = qr.make_image(fill_color="black", back_color=background_color).convert("RGBA")
            return _crisp_resize(img, width, height)

        if style == QR.STYLE__ROUNDED:
            qr_image = qr.make_image(
                fill_color="black",
                back_color=background_color,
                image_factory=StyledPilImage,
                module_drawer=CircleModuleDrawer(),
            )

            qr_image_width, _ = qr_image.size
            qr_code_dims = int(qr_image_width / box_size) - 2 * border

            if qr_code_dims > 21:
                # The ROUNDED style mis-renders the small lower-right registration
                # box in 25x25 and 29x29 codes, so we square it off manually.
                draw = ImageDraw.Draw(qr_image)
                if qr_code_dims == 25:
                    starting_point = 16 + border
                elif qr_code_dims == 29:
                    starting_point = 20 + border
                else:
                    raise Exception(f"Unrecognized qrimage size: {qr_code_dims}")

                lines = [
                    (
                        (starting_point * box_size, starting_point * box_size),
                        (
                            starting_point * box_size + 5 * box_size - 1,
                            starting_point * box_size + box_size - 1,
                        ),
                    ),
                    (
                        (
                            starting_point * box_size + 4 * box_size,
                            starting_point * box_size,
                        ),
                        (
                            starting_point * box_size + 5 * box_size - 1,
                            starting_point * box_size + 5 * box_size - 1,
                        ),
                    ),
                    (
                        (starting_point * box_size, starting_point * box_size),
                        (
                            starting_point * box_size + box_size - 1,
                            starting_point * box_size + 5 * box_size - 1,
                        ),
                    ),
                    (
                        (
                            starting_point * box_size + box_size,
                            starting_point * box_size + 4 * box_size,
                        ),
                        (
                            starting_point * box_size + 5 * box_size - 1,
                            starting_point * box_size + 5 * box_size - 1,
                        ),
                    ),
                    (
                        (
                            starting_point * box_size + 2 * box_size,
                            starting_point * box_size + 2 * box_size,
                        ),
                        (
                            starting_point * box_size + 3 * box_size - 1,
                            starting_point * box_size + 3 * box_size - 1,
                        ),
                    ),
                ]

                for line in lines:
                    draw.rectangle(line, fill="black")

            return qr_image.resize((width, height), Image.LANCZOS).convert("RGBA")

        if style == QR.STYLE__GRID:
            return (
                qr.make_image(
                    fill_color="black",
                    back_color=background_color,
                    image_factory=StyledPilImage,
                    module_drawer=GappedSquareModuleDrawer(),
                )
                .resize((width, height), Image.LANCZOS)
                .convert("RGBA")
            )

        raise ValueError(f"unsupported QR style: {style!r}")

    def qrimage_io(
        self,
        data,
        width=240,
        height=240,
        border=3,
        background_color="ffffff",
        error_correction="M",
    ):
        """Render via `qrencode` CLI when present; falls back to `qrimage`."""
        if shutil.which("qrencode") is None:
            return self.qrimage(
                data,
                width=width,
                height=height,
                border=border,
                background_color="#" + background_color if not background_color.startswith("#") else background_color,
                error_correction=error_correction,
            )

        border_str = str(border) if 1 <= border <= 10 else "3"
        ec = str(error_correction).upper() if str(error_correction).upper() in {"L", "M", "Q", "H"} else "M"

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            cmd = [
                "qrencode",
                "-m", border_str,
                "-s", "6",
                "-l", ec,
                "--foreground=000000",
                f"--background={background_color}",
                "-t", "PNG",
                "-o", str(tmp_path),
                str(data),
            ]
            rv = subprocess.call(cmd)
            if rv != 0:
                return self.qrimage(
                    data,
                    width=width,
                    height=height,
                    border=border,
                    error_correction=error_correction,
                )

            with Image.open(tmp_path) as img:
                return _crisp_resize(img.convert("RGBA"), width, height)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
