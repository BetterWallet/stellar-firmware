"""
Mnemonic-at-rest keystore with PIN-derived encryption.

The keystore stores the BIP-39 mnemonic phrase, encrypted with a key derived
from the user's PIN via scrypt + AES-GCM. The mnemonic is the single source
of truth — Stellar Ed25519 keypairs are re-derived from it on unlock.

Flow:
  PIN → scrypt → 32-byte key
  mnemonic.encode("utf-8") + AES-GCM (random 12-byte nonce) → ciphertext + tag
  written as JSON: {version, kdf, scrypt, nonce, ciphertext, tag}

We use a fresh random salt per keystore (stored in the JSON), unlike the
historical fixed _SCRYPT_SALT, so two keystores with the same PIN don't
share derived keys.
"""
import hashlib
import json
import os
from pathlib import Path

from Crypto.Cipher import AES

from config import PIN_SCRYPT_N, PIN_SCRYPT_P, PIN_SCRYPT_R

_KEYSTORE_VERSION = 2  # bump from legacy private-key-only keystore format


def _derive_key(pin: str, salt: bytes) -> bytes:
    """Stretch PIN into a 32-byte AES key with scrypt."""
    return hashlib.scrypt(
        pin.encode("utf-8"),
        salt=salt,
        n=PIN_SCRYPT_N,
        r=PIN_SCRYPT_R,
        p=PIN_SCRYPT_P,
        dklen=32,
        maxmem=PIN_SCRYPT_N * PIN_SCRYPT_R * 256,
    )


def save(path: str, mnemonic: str, pin: str) -> None:
    """Encrypt mnemonic with PIN and write keystore JSON to path."""
    salt  = os.urandom(16)
    nonce = os.urandom(12)
    key   = _derive_key(pin, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(mnemonic.encode("utf-8"))

    blob = {
        "version": _KEYSTORE_VERSION,
        "kdf":     "scrypt",
        "scrypt": {
            "n":    PIN_SCRYPT_N,
            "r":    PIN_SCRYPT_R,
            "p":    PIN_SCRYPT_P,
            "salt": salt.hex(),
            "dklen": 32,
        },
        "cipher":     "aes-256-gcm",
        "nonce":      nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "tag":        tag.hex(),
    }
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(blob))


def load(path: str, pin: str) -> str:
    """Decrypt and return the BIP-39 mnemonic. Raises ValueError on wrong PIN."""
    blob = json.loads(Path(path).read_text())
    if blob.get("version") != _KEYSTORE_VERSION:
        raise ValueError(
            f"unsupported keystore version: {blob.get('version')!r} "
            f"(expected {_KEYSTORE_VERSION}); regenerate the wallet"
        )

    salt  = bytes.fromhex(blob["scrypt"]["salt"])
    nonce = bytes.fromhex(blob["nonce"])
    ct    = bytes.fromhex(blob["ciphertext"])
    tag   = bytes.fromhex(blob["tag"])

    key = _derive_key(pin, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ct, tag)
    except (ValueError, KeyError) as exc:
        raise ValueError("wrong PIN or corrupt keystore") from exc
    return plaintext.decode("utf-8")


def exists(path: str) -> bool:
    return Path(path).exists()
