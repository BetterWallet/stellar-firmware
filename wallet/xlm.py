"""
Stellar (XLM) signing.

Wraps stellar-sdk for the air-gapped signing flow. Public surface:

    sign(keypair, request: XlmSignRequest) -> str       # signed envelope XDR

The signing path is:
    SEP-7 URI in request → extract XDR + network passphrase →
    TransactionEnvelope.from_xdr → envelope.sign(keypair) → envelope.to_xdr()

Key material flow:
    The keypair is held by the caller (state/machine.py) only during the
    SIGNING state and dereferenced afterward, mirroring the eth path.
"""
from stellar_sdk import TransactionEnvelope

from stellar import sep7
from ur.types import XlmSignRequest, XlmSignResult


def sign(keypair, request: XlmSignRequest) -> XlmSignResult:
    """
    Sign the SEP-7 transaction in request and return the signed envelope XDR.

    Raises:
        ValueError if the SEP-7 URI is malformed or doesn't carry a tx XDR.
    """
    tx_xdr = request.tx_xdr
    if tx_xdr is None:
        if not request.sep7_uri:
            raise ValueError("Stellar signing request missing tx_xdr and sep7_uri")
        sep = sep7.parse(request.sep7_uri)
        if sep.xdr is None:
            raise ValueError("SEP-7 URI does not carry a transaction XDR")

        if sep.network_passphrase != request.network_passphrase:
            raise ValueError("network passphrase mismatch for Stellar signing request")
        tx_xdr = sep.xdr

    envelope = TransactionEnvelope.from_xdr(tx_xdr, request.network_passphrase)
    envelope.sign(keypair)
    signatures = [bytes(sig.signature) for sig in envelope.signatures]
    return XlmSignResult(
        signed_xdr=envelope.to_xdr(),
        signatures=signatures,
    )
