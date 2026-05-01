"""
Tests for ur/ — decoder, encoder, types.

These tests use cbor2 directly to build synthetic UR payloads and verify
that the decoder extracts the right EthSignRequest fields.

bc-ur is vendored in _bc_ur/ so these tests always run.
"""
import pytest
import cbor2
from _bc_ur.ur_decoder import URDecoder as BCURDecoder

from ur.types import (
    BwStellarAccount,
    BwStellarAccountsPayload,
    BwStellarDevice,
    CryptoHDKey,
    EthSignRequest,
    EthSignature,
    XlmSignature,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic UR payloads
# ---------------------------------------------------------------------------

def _make_keypath_cbor(path_str: str) -> cbor2.CBORTag:
    components = []
    for part in path_str.split("/"):
        if not part:
            continue
        hardened = part.endswith("'")
        index = int(part.rstrip("'"))
        components.append([index, hardened])
    return cbor2.CBORTag(304, {1: components})


def _make_eth_sign_request_cbor(
    request_id: bytes = b"\xab" * 16,
    sign_data: bytes = b"hello",
    data_type: int = 3,
    chain_id: int = 1,
    path: str = "44'/60'/0'/0/0",
) -> bytes:
    return cbor2.dumps({
        1: request_id,
        2: sign_data,
        3: data_type,
        4: chain_id,
        5: _make_keypath_cbor(path),
    })


def _make_bw_stellar_sign_request_cbor(
    req_id: str = "req-123",
    signer_pubkey: str = "GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX",
    network_passphrase: str = "Test SDF Network ; September 2015",
    sep7_uri: str = "web+stellar:tx?xdr=AAAA&network_passphrase=Test%20SDF",
) -> bytes:
    return cbor2.dumps(
        {
            "kind": "tx",
            "req_id": req_id,
            "signer_pubkey": signer_pubkey,
            "network_passphrase": network_passphrase,
            "sep7_uri": sep7_uri,
        }
    )


# ---------------------------------------------------------------------------
# decoder
# ---------------------------------------------------------------------------

class TestDecoder:
    def test_parse_eth_sign_request_personal(self):
        from ur.decoder import _parse_eth_sign_request

        cbor_bytes = _make_eth_sign_request_cbor(data_type=3)
        req = _parse_eth_sign_request(cbor_bytes)

        assert isinstance(req, EthSignRequest)
        assert req.request_id == b"\xab" * 16
        assert req.sign_data == b"hello"
        assert req.data_type == 3
        assert req.chain_id == 1
        assert req.derivation_path == "44'/60'/0'/0/0"
        assert req.address is None

    def test_parse_eth_sign_request_with_address(self):
        from ur.decoder import _parse_eth_sign_request

        addr_bytes = bytes.fromhex("abcdef1234567890abcdef1234567890abcdef12")
        cbor_bytes = cbor2.dumps({
            1: b"\x00" * 16,
            2: b"data",
            3: 1,
            4: 1,
            5: _make_keypath_cbor("44'/60'/0'/0/0"),
            6: addr_bytes,
        })
        req = _parse_eth_sign_request(cbor_bytes)
        assert req.address == "0x" + addr_bytes.hex()

    def test_keypath_roundtrip(self):
        from ur.decoder import _decode_keypath

        kp = _make_keypath_cbor("44'/60'/0'/0/5")
        result = _decode_keypath(kp)
        assert result == "44'/60'/0'/0/5"

    def test_receive_part_info_tracks_accept_reject_counts(self):
        from _bc_ur.ur import UR
        from _bc_ur.ur_encoder import UREncoder
        from ur.decoder import URDecoder

        payload = _make_eth_sign_request_cbor(sign_data=b"a" * 64)
        encoder = UREncoder(UR("eth-sign-request", payload), 10)
        decoder = URDecoder()

        accepted, complete = decoder.receive_part_info("not-a-ur")
        assert accepted is False
        assert complete is False
        assert decoder.accepted_parts == 0
        assert decoder.rejected_parts == 1

        accepted, complete = decoder.receive_part_info(encoder.next_part())
        assert accepted is True
        assert decoder.accepted_parts == 1
        assert decoder.rejected_parts == 1
        assert complete in (False, True)

    def test_reset_clears_receive_part_counters(self):
        from _bc_ur.ur import UR
        from _bc_ur.ur_encoder import UREncoder
        from ur.decoder import URDecoder

        payload = _make_eth_sign_request_cbor(sign_data=b"b" * 64)
        encoder = UREncoder(UR("eth-sign-request", payload), 10)
        decoder = URDecoder()

        decoder.receive_part_info(encoder.next_part())
        decoder.receive_part_info("invalid")
        assert decoder.accepted_parts >= 1
        assert decoder.rejected_parts >= 1

        decoder.reset()
        assert decoder.accepted_parts == 0
        assert decoder.rejected_parts == 0
        assert decoder.last_part_accepted is False

    def test_parse_bw_stellar_sign_request(self):
        from ur.decoder import _parse_bw_stellar_sign_request

        cbor_bytes = _make_bw_stellar_sign_request_cbor()
        req = _parse_bw_stellar_sign_request(cbor_bytes)

        assert req.kind == "tx"
        assert req.request_id == "req-123"
        assert req.signer_pubkey.startswith("G")
        assert "Network" in req.network_passphrase
        assert req.sep7_uri.startswith("web+stellar:tx")


# ---------------------------------------------------------------------------
# encoder
# ---------------------------------------------------------------------------

class TestEncoder:
    @staticmethod
    def _decode_ur_payload(part: str):
        decoder = BCURDecoder()
        assert decoder.receive_part(part) is True
        assert decoder.is_complete() is True
        return decoder.result_ur()

    def test_encode_eth_signature_single_part(self):
        from ur.encoder import encode_eth_signature

        sig = EthSignature(
            request_id=b"\xab" * 16,
            signature=b"\xff" * 65,
        )
        parts = encode_eth_signature(sig)
        assert isinstance(parts, list)
        assert len(parts) >= 1
        # Every part should be a UR string
        for part in parts:
            assert part.lower().startswith("ur:eth-signature")

    def test_encode_crypto_hdkey(self):
        from ur.encoder import encode_crypto_hdkey

        hdkey = CryptoHDKey(
            key_data=b"\x02" + b"\xaa" * 32,   # fake compressed pubkey
            chain_code=b"\xbb" * 32,
            origin_path="44'/60'/0'/0/0",
            address="0xDeadBeef" + "0" * 32,
        )
        parts = encode_crypto_hdkey(hdkey)
        assert isinstance(parts, list)
        assert len(parts) >= 1
        for part in parts:
            assert part.lower().startswith("ur:crypto-hdkey")

    def test_encode_bw_stellar_signature(self):
        from ur.encoder import encode_xlm_signature

        sig = XlmSignature(
            request_id="request-1",
            signer_pubkey="GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX",
            signed_xdr="AAAA",
            signatures=[{"bytes": "YWJj"}],
        )
        parts = encode_xlm_signature(sig)
        assert isinstance(parts, list)
        assert len(parts) >= 1
        for part in parts:
            assert part.lower().startswith("ur:bw-stellar-signature")

        ur = self._decode_ur_payload(parts[0])
        payload = cbor2.loads(ur.cbor)
        assert sorted(payload.keys()) == [
            "request_id",
            "signed_xdr",
            "signatures",
            "signer_pubkey",
        ]

    def test_encode_bw_stellar_accounts(self):
        from ur.encoder import encode_bw_stellar_accounts

        payload = BwStellarAccountsPayload(
            device=BwStellarDevice(id="device-1", label="Better Wallet"),
            accounts=[
                BwStellarAccount(
                    publicKey="GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX",
                    bipPath="m/44'/148'/0'",
                    label="Account #1",
                )
            ],
        )
        parts = encode_bw_stellar_accounts(payload)
        assert isinstance(parts, list)
        assert len(parts) >= 1
        for part in parts:
            assert part.lower().startswith("ur:bw-stellar-accounts")

        ur = self._decode_ur_payload(parts[0])
        payload = cbor2.loads(ur.cbor)
        assert sorted(payload.keys()) == ["accounts", "device"]
        assert sorted(payload["accounts"][0].keys()) == ["bipPath", "label", "publicKey"]
