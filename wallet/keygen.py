"""
BIP-39 mnemonic generation and validation.

Never logs or persists the mnemonic — caller is responsible for secure handling.
"""
from mnemonic import Mnemonic

_mnemo = Mnemonic("english")


def generate() -> str:
    """Generate a fresh 12-word BIP-39 mnemonic."""
    return _mnemo.generate(strength=128)


def validate(phrase: str) -> bool:
    """Return True if phrase is a valid BIP-39 mnemonic."""
    return _mnemo.check(phrase)


def to_seed(phrase: str, passphrase: str = "") -> bytes:
    """Derive a 64-byte seed from a mnemonic. Passphrase defaults to empty."""
    if not validate(phrase):
        raise ValueError("invalid BIP-39 mnemonic")
    return _mnemo.to_seed(phrase, passphrase)
