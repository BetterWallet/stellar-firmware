import os

DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 480
DISPLAY_FB = "/dev/fb1"
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
# OV5647 2x2 binned mode: 1296x972 @ ~46 fps, full FOV, no crop.
# Full-sensor 2592x1944 exceeds GPU memory on most Pi configs.
RIBBON_CAMERA_WIDTH = 1296
RIBBON_CAMERA_HEIGHT = 972
CAMERA_PREVIEW_ROTATION = 180
CAMERA_SCAN_ROTATION = 180
# Camera backend: "usb" for /dev/video* webcams, "ribbon" for the Pi CSI camera.
# The ribbon camera is the recommended production path for animated QR scanning.
CAMERA_BACKEND = "ribbon"
CAMERA_DEVICE_INDEX = 0
SCAN_PREVIEW_ENABLED = True
SCAN_PREVIEW_FPS = 8
SCAN_REGION_RATIO = 1.0
SCAN_DECODER_MODE = "pyzbar"   # "fast", "hybrid", "pyzbar", "opencv"
SCAN_DECODE_MAX_SIZE = 640     # downscale longest edge before QR decode
SCAN_FRAME_SKIP = 1            # decode every Nth captured frame
SCAN_AGGRESSIVE_AFTER_MISSES = 6
SCAN_LOG_INTERVAL = 2.0
GPIO_CONFIRM_PIN = 21
GPIO_REJECT_PIN = 16
GPIO_LED_GREEN = 20
GPIO_LED_RED = 26
KEYSTORE_PATH = os.path.expanduser("~/.cold-wallet/keystore.json")
XPUB_PATH     = os.path.expanduser("~/.cold-wallet/xpub.json")
PIN_SCRYPT_N = 2**15      # 2**18 exceeds OpenSSL memory limit on Pi 4; never below 2**14
PIN_SCRYPT_R = 8
PIN_SCRYPT_P = 1
BIP44_PATH = "m/44'/60'/0'/0/0"
BIP44_ACCOUNT_PATH = "m/44'/60'/0'"    # account-level path for xpub export

# Stellar (XLM): Ed25519 / SLIP-10. Hardened-only by spec.
# stellar-sdk derives via Keypair.from_mnemonic_phrase(mnemonic, index=0)
# which uses path m/44'/148'/{index}'.
XLM_DERIVATION_PATH    = "m/44'/148'/0'"
XLM_NETWORK_PASSPHRASE = "Public Global Stellar Network ; September 2015"
XLM_TESTNET_PASSPHRASE = "Test SDF Network ; September 2015"
QR_DISPLAY_FPS = 5        # animated QR frame rate on result screen
QR_DISPLAY_SIZE = 280     # pixel dimension for QR codes rendered on screen
MAX_FRAGMENT_LEN = 200    # max UR fragment length for fountain coding

# Show the yellow crosshair pointer when using the touchscreen (USB mouse always shows it when present).
SHOW_TOUCH_CURSOR = True
