# cold-wallet

An air-gapped Ethereum hardware wallet running on a Raspberry Pi. Private keys never touch the internet. All communication with MetaMask / Rabby happens exclusively via QR codes — no USB, no WiFi, no Bluetooth.

Compatible with MetaMask and Rabby via the **Keystone** hardware wallet integration (EIP-4527).

---

## How it works

```
MetaMask displays animated QR  →  Pi camera scans it  →  Pi signs offline
         ↑                                                        |
         └──────────  Pi displays signed QR  ←────────────────────┘
```

1. Import your wallet address into MetaMask using the **xpub QR** shown at setup
2. MetaMask constructs a transaction and displays an animated QR (EIP-4527 format)
3. Point the Pi camera at the screen — the Pi decodes the request
4. Review the transaction details on the Pi display
5. Press the **Confirm** button (GPIO 17) to sign, or **Reject** (GPIO 27) to cancel
6. The Pi displays an animated QR of the signature
7. Scan it with MetaMask — it broadcasts the transaction

---

## Hardware

| Component | Details |
|---|---|
| Raspberry Pi 4 | CM4 no-wireless SKU recommended for production |
| Display | 3.5" SPI resistive touchscreen (tft35a / ADS7846) |
| Camera | Raspberry Pi Camera Module (libcamera stack) |
| Buttons | 2× momentary push button — confirm on GPIO 17, reject on GPIO 27 |
| Network | **None.** WiFi and Bluetooth disabled at OS level |

Disable wireless in `/boot/firmware/config.txt`:
```
dtoverlay=disable-wifi
dtoverlay=disable-bt
```

---

## Project layout

```
cold-wallet/
├── main.py                  # asyncio entry point
├── config.py                # all hardware constants
├── requirements.txt
│
├── wallet/                  # KEY MATERIAL BOUNDARY — only state/machine.py imports this
│   ├── keygen.py            # BIP-39 mnemonic generation
│   ├── keystore.py          # PIN-encrypted keystore (eth_account format)
│   ├── derive.py            # BIP-44 HD derivation
│   └── signer.py            # sign(account, request) → 65 bytes
│
├── ur/                      # EIP-4527 transport
│   ├── types.py             # EthSignRequest, EthSignature, CryptoHDKey
│   ├── decoder.py           # fountain-code UR fragments → EthSignRequest
│   └── encoder.py           # EthSignature → UR → animated QR frames
│
├── eip712/                  # EIP-712 typed data
│   ├── parser.py            # JSON bytes → TypedData
│   ├── encoder.py           # hashStruct, domainSeparator, signHash
│   └── display.py           # TypedData → flat DisplayField list for UI
│
├── state/
│   ├── states.py            # State enum + event types
│   └── machine.py           # asyncio state machine (sole wallet/ importer)
│
├── camera/
│   ├── capture.py           # picamera2 frame loop (Pi only)
│   └── scanner.py           # pyzbar QR decode → UR fragment strings
│
├── display/
│   ├── screen.py            # pygame framebuffer driver + touch PIN input
│   ├── widgets.py           # QR renderer, text helpers
│   └── screens/             # pin, setup, idle, confirm, result
│
├── gpio/
│   └── buttons.py           # GPIO interrupt handler (Pi only)
│
└── tests/
    ├── test_ur.py
    ├── test_eip712.py
    ├── test_wallet.py
    └── test_state_machine.py
```

---

## Development setup (macOS / Linux, no Pi required)

Steps 1–4 of the build order are fully testable on a dev machine.

### 1. Create a virtual environment

```bash
python3 -m venv virt
source virt/bin/activate
```

### 2. Install native dependencies

**macOS:**
```bash
brew install zbar      # required by pyzbar
```

**Ubuntu/Debian:**
```bash
sudo apt install libzbar0
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the tests

```bash
pytest tests/ -v
```

`test_ur.py` auto-skips if `foundation-ur` fails to import. Everything else runs on any machine.

---

## Raspberry Pi setup

### OS

Raspberry Pi OS Lite (64-bit, Bookworm). No desktop environment.

### System packages

```bash
sudo apt update
sudo apt install -y \
    python3-pip python3-venv \
    libzbar0 \
    python3-picamera2 \
    libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev   # pygame framebuffer deps
```

### Python environment

```bash
cd ~
git clone <this-repo> cold-wallet
cd cold-wallet
python3 -m venv virt
source virt/bin/activate
pip install -r requirements.txt
pip install RPi.GPIO          # Pi only, not in requirements.txt
```

### Enable the camera and SPI display

In `/boot/firmware/config.txt`:
```
# Camera
camera_auto_detect=1

# 3.5" SPI display (tft35a)
dtoverlay=tft35a

# Disable wireless
dtoverlay=disable-wifi
dtoverlay=disable-bt
```

Reboot after editing.

### Camera backend notes

- The **ribbon camera** (`CAMERA_BACKEND = "ribbon"`) is the recommended production path for scanning MetaMask animated QR on the Pi.
- The **USB camera** backend is kept as a fallback for setup/testing, but it is less reliable for dense animated UR QR because of lower effective optical quality and higher capture overhead on the Pi.
- The scanner is tuned to prefer the newest frame, use a center ROI, and throttle preview rendering so the Pi spends CPU on QR decoding instead of stale frames.

### Run

```bash
source virt/bin/activate
python main.py
```

To run on boot, create `/etc/systemd/system/cold-wallet.service`:

```ini
[Unit]
Description=Cold Wallet
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/cold-wallet
ExecStart=/home/pi/cold-wallet/virt/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cold-wallet
sudo systemctl start cold-wallet
```

---

## First boot

1. Power on — the setup screen displays your **12 seed words**
2. Write them down on paper — this is the only backup of your wallet
3. Tap the screen to confirm you've recorded them
4. Enter a PIN on the numeric keypad (touchscreen)
5. The idle screen appears showing your Ethereum address as a QR code

### Import into MetaMask

1. In MetaMask: **Add account → Hardware wallet → Keystone**
2. Scan the address QR shown on the idle screen
3. Select the account and confirm

---

## Signing a transaction

1. In MetaMask, initiate any transaction as normal
2. MetaMask shows an animated QR — hold it up to the Pi camera
3. The Pi scans all fragments (progress bar on screen)
4. Review the decoded transaction details
5. Press **Confirm** (GPIO 17) to sign or **Reject** (GPIO 27) to cancel
6. Scan the resulting animated QR with MetaMask
7. MetaMask broadcasts the signed transaction

---

## Security model

- Private keys are stored in an `eth_account`-encrypted keystore at `/home/pi/.cold-wallet/keystore.json`
- The PIN is stretched with scrypt (N=2¹⁸) before being used as the keystore password
- The decrypted key exists in memory only during the **Signing** state and is immediately dereferenced
- `wallet/` is the only package that ever holds key material — no other module imports it
- WiFi and Bluetooth are disabled at the OS level (not just software)
- The Pi never initiates any network connection

---

## State machine

```
SETUP ──► LOCKED ──► IDLE ──► SCANNING ──► PARSED ──► AWAIT_CONFIRM
                      ▲                                   │         │
                      │                               CONFIRM    REJECT
                      │                                   │         │
                      └──── DISPLAY_RESULT ◄── SIGNING  ◄ ┘         │
                      └─────────────────────────────────────────────┘
```

---

## Build order / test coverage

| Step | Modules | Needs Pi |
|---|---|---|
| 1 | `ur/` | No |
| 2 | `eip712/` | No |
| 3 | `wallet/` | No |
| 4 | `state/` | No |
| 5 | `camera/` | Yes |
| 6 | `display/` | Yes |
| 7 | `gpio/` | Yes |
| 8 | `main.py` end-to-end | Yes |
