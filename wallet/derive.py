"""
Stellar HD derivation from a BIP-39 mnemonic.

Public surface:
    derive_xlm_keypair(mnemonic, index=0) -> stellar_sdk.Keypair
    derive_xlm_accounts(mnemonic, count=5) -> list[dict]
"""
from stellar_sdk import Keypair

def derive_xlm_keypair(mnemonic: str, index: int = 0, passphrase: str = ""):
    """
    Derive a Stellar Keypair from mnemonic at SLIP-10 path m/44'/148'/{index}'.

    stellar-sdk handles the PBKDF2 mnemonic→seed step and the SLIP-10 walk
    internally; we just hand it the phrase.
    """
    return Keypair.from_mnemonic_phrase(mnemonic, passphrase=passphrase, index=index)


def derive_xlm_accounts(mnemonic: str, count: int = 5, passphrase: str = "") -> list[dict]:
    accounts = []
    for index in range(count):
        keypair = derive_xlm_keypair(mnemonic, index=index, passphrase=passphrase)
        accounts.append(
            {
                "index": index,
                "public_key": keypair.public_key,
                "bip_path": f"m/44'/148'/{index}'",
            }
        )
    return accounts
