"""
Public wallet surface.

Holds the unlocked mnemonic and exposes both chain keypairs as cached
properties. Dispatches signing to the appropriate per-chain module based
on the request type.

Architectural rule: only state/machine.py imports from this package.
"""
from functools import cached_property

from ur.types import EthSignRequest, XlmSignRequest

from wallet import eth as _eth
from wallet import xlm as _xlm
from wallet import derive as _derive


class Wallet:
    """Unlocked wallet holding the BIP-39 mnemonic in memory.

    Both the Ethereum LocalAccount and the Stellar Keypair are derived
    lazily and cached for the lifetime of this object — typically the
    SIGNING state's local scope.
    """

    def __init__(self, mnemonic: str):
        self._mnemonic = mnemonic

    # ── chain accounts ──────────────────────────────────────────────────
    @cached_property
    def eth_account(self):
        return _derive.derive_eth_account(self._mnemonic)

    @cached_property
    def xlm_keypair(self):
        return _derive.derive_xlm_keypair(self._mnemonic)

    # ── public addresses ────────────────────────────────────────────────
    @property
    def eth_address(self) -> str:
        return self.eth_account.address

    @property
    def xlm_address(self) -> str:
        return self.xlm_keypair.public_key

    # ── signing ─────────────────────────────────────────────────────────
    def sign(self, request):
        """Dispatch a sign request to the right chain. Returns chain-specific bytes/str."""
        if isinstance(request, EthSignRequest):
            return _eth.sign(self.eth_account, request)
        if isinstance(request, XlmSignRequest):
            return _xlm.sign(self.xlm_keypair, request)
        raise ValueError(f"unsupported sign request type: {type(request).__name__}")
