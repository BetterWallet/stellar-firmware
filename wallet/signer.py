"""
Backwards-compat shim: dispatches by request type to the per-chain signer.

New callers should use wallet.Wallet directly. This shim exists so existing
state-machine call sites continue to work during the migration.
"""
from ur.types import EthSignRequest, XlmSignRequest

from wallet import eth as _eth
from wallet import xlm as _xlm


def sign(account, request):
    """Legacy entry point. Dispatches by request type.

    For ETH paths, `account` is an eth_account LocalAccount.
    For XLM paths, `account` is a stellar_sdk.Keypair.
    """
    if isinstance(request, EthSignRequest):
        return _eth.sign(account, request)
    if isinstance(request, XlmSignRequest):
        return _xlm.sign(account, request)
    raise ValueError(f"unsupported sign request type: {type(request).__name__}")
