# stellar-firmware

An air-gapped Stellar hardware signer running on a Raspberry Pi. Private keys never touch the internet. Communication happens through QR codes only (no USB, no WiFi, no Bluetooth).

---

## How it works

1. A Stellar wallet app displays a signing request QR (`web+stellar:` or `ur:bw-stellar-sign-request`).
2. The Pi camera scans the request.
3. The device parses the transaction details and shows a confirmation screen.
4. You confirm or reject using hardware buttons.
5. If confirmed, the Pi signs offline and displays a Stellar signature QR (`ur:bw-stellar-signature`).

---

## Project layout

```
stellar-firmware/
├── main.py
├── config.py
├── requirements.txt
│
├── wallet/
│   ├── keygen.py
│   ├── keystore.py
│   ├── derive.py
│   ├── signer.py
│   └── xlm.py
│
├── stellar/
│   ├── sep7.py
│   └── parser.py
│
├── ur/
│   ├── types.py
│   ├── decoder.py
│   └── encoder.py
│
├── state/
│   ├── states.py
│   └── machine.py
│
├── camera/
│   ├── capture.py
│   └── scanner.py
│
├── display/
│   ├── screen.py
│   ├── widgets.py
│   └── screens/
│
├── gpio/
│   └── buttons.py
│
└── tests/
```

---

## Development setup

### 1) Create a virtual environment

```bash
python3 -m venv virt
source virt/bin/activate
```

### 2) Install native dependency

Ubuntu/Debian:

```bash
sudo apt install libzbar0
```

macOS:

```bash
brew install zbar
```

### 3) Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4) Run tests

```bash
pytest tests/ -v
```

---

## Raspberry Pi setup

### System packages

```bash
sudo apt update
sudo apt install -y \
    python3-pip python3-venv \
    libzbar0 \
    python3-picamera2 \
    libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev
```

### Python environment

```bash
cd ~
git clone <this-repo> stellar-firmware
cd stellar-firmware
python3 -m venv virt
source virt/bin/activate
pip install -r requirements.txt
pip install RPi.GPIO
```

### Camera/display and wireless config

In `/boot/firmware/config.txt`:

```ini
camera_auto_detect=1
dtoverlay=tft35a
dtoverlay=disable-wifi
dtoverlay=disable-bt
```

Then reboot.

---

## Security model

- Private keys are stored in an encrypted keystore at `~/.cold-wallet/keystore.json`.
- PIN is stretched with scrypt before decrypting mnemonic material.
- Decrypted key material exists only while signing in memory.
- The Pi never initiates network connections.
- WiFi and Bluetooth are disabled at OS level.

---

## State machine

```
SETUP -> LOCKED -> IDLE -> SCANNING -> PARSED -> AWAIT_CONFIRM
                 ^                               |         |
                 |                           CONFIRM    REJECT
                 |                               |         |
                 +---- DISPLAY_RESULT <- SIGNING +---------+
```
