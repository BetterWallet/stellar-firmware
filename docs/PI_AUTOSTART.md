# Raspberry Pi Autostart

Stellar Firmware runs as a **user-level systemd service** under the `pi` account. No root access is needed.

## Service file

Location: `~/.config/systemd/user/stellar-firmware.service`

```ini
[Unit]
Description=Stellar Firmware
After=default.target

[Service]
Type=simple
WorkingDirectory=/home/pi/stellar-firmware
ExecStartPre=/home/pi/stellar-firmware/.venv/bin/python /home/pi/stellar-firmware/splash.py
ExecStart=/home/pi/stellar-firmware/.venv/bin/python /home/pi/stellar-firmware/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

`ExecStartPre` runs `splash.py` first, which writes the boot logo directly to `/dev/fb1` while `main.py` is still loading.

## Setup

```bash
# 1. Create the service file
mkdir -p ~/.config/systemd/user
# paste the service file above to ~/.config/systemd/user/stellar-firmware.service

# 2. Allow the service to start at boot without a login session
loginctl enable-linger pi

# 3. Enable and start the service
systemctl --user daemon-reload
systemctl --user enable stellar-firmware
systemctl --user start stellar-firmware
```

## Useful commands

```bash
# Start / stop
systemctl --user start stellar-firmware
systemctl --user stop stellar-firmware

# Check status
systemctl --user status stellar-firmware

# Live logs
journalctl --user -u stellar-firmware -f

# Reload after editing the service file
systemctl --user daemon-reload && systemctl --user restart stellar-firmware
```

## Boot splash

`splash.py` converts `assets/better_wallet_logo.png` to RGB565 and writes it directly to `/dev/fb1` before `main.py` starts. To test it in isolation:

```bash
/home/pi/stellar-firmware/.venv/bin/python /home/pi/stellar-firmware/splash.py
```
