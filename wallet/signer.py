"""
Backwards-compat shim for Stellar signing.

New callers should use wallet.Wallet directly. This shim exists so existing
call sites continue to work.
"""
from ur.types import XlmSignRequest

from wallet import xlm as _xlm


def sign(account, request):
    """Legacy entry point for Stellar requests.

    `account` is a stellar_sdk.Keypair.
    """
    if isinstance(request, XlmSignRequest):
        return _xlm.sign(account, request)
    raise ValueError(f"unsupported sign request type: {type(request).__name__}")
