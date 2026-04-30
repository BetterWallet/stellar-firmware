"""
Per-chain HD derivation from a single BIP-39 mnemonic.

Public surface:
    derive_eth_account(mnemonic, path=BIP44_PATH) -> eth_account.LocalAccount
    derive_eth_xpub(mnemonic, path=BIP44_ACCOUNT_PATH) -> dict
    derive_xlm_keypair(mnemonic, index=0)            -> stellar_sdk.Keypair

Both derivations consume the same mnemonic but walk different curves and
different SLIP-44 coin types:
    Ethereum: secp256k1, BIP-32, m/44'/60'/0'/0/0
    Stellar:  Ed25519,    SLIP-10, m/44'/148'/{index}'

We re-derive on every unlock rather than caching — this is the same pattern
the eth path used previously and avoids any long-lived keypair state.
"""
from bip32utils import BIP32Key, BIP32_HARDEN
from eth_account import Account
from mnemonic import Mnemonic
from stellar_sdk import Keypair

from config import BIP44_ACCOUNT_PATH, BIP44_PATH

_mnemo = Mnemonic("english")


# ---------------------------------------------------------------------------
# Ethereum (secp256k1, BIP-32)
# ---------------------------------------------------------------------------

def _seed(mnemonic: str, passphrase: str = "") -> bytes:
    return _mnemo.to_seed(mnemonic, passphrase)


def _parse_path(path: str) -> list[int]:
    """Convert "m/44'/60'/0'/0/0" or "44'/60'/0'/0/0" to a list of child indices."""
    parts = path.lstrip("m/").split("/")
    indices: list[int] = []
    for part in parts:
        if part.endswith("'"):
            indices.append(int(part[:-1]) + BIP32_HARDEN)
        else:
            indices.append(int(part))
    return indices


def derive_eth_account(mnemonic: str, path: str = BIP44_PATH):
    """Derive an eth_account LocalAccount from mnemonic + BIP-44 path."""
    seed = _seed(mnemonic)
    key = BIP32Key.fromEntropy(seed)
    for index in _parse_path(path):
        key = key.ChildKey(index)
    return Account.from_key(key.PrivateKey())


def derive_eth_xpub(mnemonic: str, path: str = BIP44_ACCOUNT_PATH) -> dict:
    """Public-key info at path. Used to build the CryptoHDKey for MetaMask import."""
    seed = _seed(mnemonic)
    root = BIP32Key.fromEntropy(seed)
    master_fingerprint = root.Fingerprint()

    key = root
    for index in _parse_path(path):
        key = key.ChildKey(index)

    return {
        "key_data":            key.PublicKey(),
        "chain_code":          key.C,
        "master_fingerprint":  master_fingerprint,
        "parent_fingerprint":  key.parent_fpr,
        "depth":               key.depth,
    }


# ---------------------------------------------------------------------------
# Stellar (Ed25519, SLIP-10)
# ---------------------------------------------------------------------------

def derive_xlm_keypair(mnemonic: str, index: int = 0, passphrase: str = ""):
    """
    Derive a Stellar Keypair from mnemonic at SLIP-10 path m/44'/148'/{index}'.

    stellar-sdk handles the PBKDF2 mnemonic→seed step and the SLIP-10 walk
    internally; we just hand it the phrase.
    """
    return Keypair.from_mnemonic_phrase(mnemonic, passphrase=passphrase, index=index)
