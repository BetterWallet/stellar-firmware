"""
Stellar (XLM) signer tests.

Builds a real XDR transaction with stellar-sdk, wraps it in a SEP-7 URI,
hands it to wallet.xlm.sign, and verifies the resulting signed envelope
against the derived Ed25519 public key.
"""
from urllib.parse import quote

import pytest
from stellar_sdk import Account, Asset, Network, TransactionBuilder, TransactionEnvelope

from wallet import derive
from wallet import xlm as xlm_signer
from ur.types import XlmSignRequest


_TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
_DEST = "GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H"


def _build_tx_xdr(source_public: str, network_passphrase: str) -> str:
    src = Account(account=source_public, sequence=12345)
    tx = (
        TransactionBuilder(
            source_account=src,
            network_passphrase=network_passphrase,
            base_fee=100,
        )
        .append_payment_op(destination=_DEST, asset=Asset.native(), amount="42.5")
        .add_text_memo("xlm-test")
        .set_timeout(30)
        .build()
    )
    return tx.to_xdr()


def _make_request(xdr: str, network_passphrase: str) -> XlmSignRequest:
    uri = (
        f"web+stellar:tx"
        f"?xdr={quote(xdr, safe='')}"
        f"&network_passphrase={quote(network_passphrase, safe='')}"
    )
    return XlmSignRequest(request_id=b"\xab" * 16, sep7_uri=uri)


class TestXlmSign:
    def test_sign_returns_xdr_string(self):
        kp = derive.derive_xlm_keypair(_TEST_MNEMONIC)
        xdr = _build_tx_xdr(kp.public_key, Network.TESTNET_NETWORK_PASSPHRASE)
        req = _make_request(xdr, Network.TESTNET_NETWORK_PASSPHRASE)

        signed = xlm_signer.sign(kp, req)
        assert isinstance(signed, str)
        assert len(signed) > len(xdr)  # signed envelope adds the signature

    def test_signed_envelope_verifies(self):
        kp = derive.derive_xlm_keypair(_TEST_MNEMONIC)
        xdr = _build_tx_xdr(kp.public_key, Network.TESTNET_NETWORK_PASSPHRASE)
        req = _make_request(xdr, Network.TESTNET_NETWORK_PASSPHRASE)

        signed_xdr = xlm_signer.sign(kp, req)
        env = TransactionEnvelope.from_xdr(signed_xdr, Network.TESTNET_NETWORK_PASSPHRASE)

        assert len(env.signatures) == 1
        # Keypair.verify returns None on success and raises on a bad signature.
        kp.verify(env.hash(), env.signatures[0].signature)

    def test_sign_rejects_bad_uri(self):
        kp = derive.derive_xlm_keypair(_TEST_MNEMONIC)
        bad_req = XlmSignRequest(request_id=b"\x00" * 16, sep7_uri="https://example.com")
        with pytest.raises(ValueError):
            xlm_signer.sign(kp, bad_req)
