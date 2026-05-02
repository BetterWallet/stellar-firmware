"""Write the boot splash image to the framebuffer."""
from PIL import Image
import numpy as np

FB   = "/dev/fb1"
W, H = 320, 480

img = Image.open("/home/pi/stellar-firmware/assets/better_wallet_logo.png").convert("RGB")
img.thumbnail((W, H), Image.LANCZOS)

canvas = Image.new("RGB", (W, H))
canvas.paste(img, ((W - img.width) // 2, (H - img.height) // 2))

a = np.array(canvas, dtype=np.uint16)
rgb565 = ((a[:, :, 0] >> 3) << 11 | (a[:, :, 1] >> 2) << 5 | a[:, :, 2] >> 3).astype(np.uint16)

with open(FB, "rb+") as fb:
    fb.write(rgb565.tobytes())
