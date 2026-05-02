"""
Public wallet surface.

Holds the unlocked mnemonic and exposes Stellar keypairs as cached
properties. Dispatches signing based on Stellar request types.

Architectural rule: only state/machine.py imports from this package.
"""
from functools import cached_property

from ur.types import XlmSignRequest

from wallet import xlm as _xlm
from wallet import derive as _derive


class Wallet:
    """Unlocked wallet holding the BIP-39 mnemonic in memory.

    The Stellar Keypair is derived lazily and cached for the lifetime of this
    object — typically the
    SIGNING state's local scope.
    """

    def __init__(self, mnemonic: str):
        self._mnemonic = mnemonic

    # ── chain accounts ──────────────────────────────────────────────────
    @cached_property
    def xlm_keypair(self):
        return _derive.derive_xlm_keypair(self._mnemonic)

    @cached_property
    def xlm_accounts(self):
        return _derive.derive_xlm_accounts(self._mnemonic, count=5)

    @cached_property
    def _xlm_keypairs_by_public_key(self):
        keypairs = {}
        for account in self.xlm_accounts:
            keypair = _derive.derive_xlm_keypair(self._mnemonic, index=account["index"])
            keypairs[keypair.public_key] = {
                "keypair": keypair,
                "index": account["index"],
                "bip_path": account["bip_path"],
            }
        return keypairs

    # ── public addresses ────────────────────────────────────────────────
    @property
    def xlm_address(self) -> str:
        return self.xlm_keypair.public_key

    def find_xlm_account(self, public_key: str):
        return self._xlm_keypairs_by_public_key.get(public_key)

    # ── signing ─────────────────────────────────────────────────────────
    def sign(self, request):
        """Dispatch a sign request to the right chain. Returns chain-specific bytes/str."""
        if isinstance(request, XlmSignRequest):
            account = self.find_xlm_account(request.signer_pubkey)
            if account is None:
                raise ValueError("requested signer pubkey is not available on this device")
            return _xlm.sign(account["keypair"], request)
        raise ValueError(f"unsupported sign request type: {type(request).__name__}")
