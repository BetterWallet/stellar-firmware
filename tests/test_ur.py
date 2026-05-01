"""
Tests for ur/ — decoder, encoder, types.

These tests use cbor2 directly to build synthetic UR payloads and verify
that the decoder extracts the right EthSignRequest fields.

bc-ur is vendored in _bc_ur/ so these tests always run.
"""
import base64
import json

import cbor2
import pytest

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


def _make_bw_stellar_sign_request_data(
    req_id: str = "req-123",
    signer_pubkey: str = "GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX",
    network_passphrase: str = "Test SDF Network ; September 2015",
    sep7_uri: str = "web+stellar:tx?xdr=AAAA&network_passphrase=Test%20SDF",
) -> dict:
    return {
        "kind": "tx",
        "req_id": req_id,
        "signer_pubkey": signer_pubkey,
        "network_passphrase": network_passphrase,
        "sep7_uri": sep7_uri,
    }


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
        from ur.decoder import _parse_bw_stellar_sign_request_data

        req = _parse_bw_stellar_sign_request_data(_make_bw_stellar_sign_request_data())

        assert req.kind == "tx"
        assert req.request_id == "req-123"
        assert req.signer_pubkey.startswith("G")
        assert "Network" in req.network_passphrase
        assert req.sep7_uri.startswith("web+stellar:tx")

    def test_ur_decoder_accepts_simple_bw_stellar_payload(self):
        from ur.decoder import URDecoder

        payload = _make_bw_stellar_sign_request_data()
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
        ur = f"ur:bw-stellar-sign-request/{encoded}"
        decoder = URDecoder()

        accepted, complete = decoder.receive_part_info(ur)
        assert accepted is True
        assert complete is True

        req = decoder.result()
        assert req.request_id == payload["req_id"]

    def test_ur_decoder_reassembles_simple_bw_stellar_multipart(self):
        from ur.decoder import URDecoder

        payload = _make_bw_stellar_sign_request_data(sep7_uri="web+stellar:tx?xdr=" + ("A" * 600))
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
        chunk_size = 120
        chunks = [encoded[i:i + chunk_size] for i in range(0, len(encoded), chunk_size)]
        total = len(chunks)

        decoder = URDecoder()
        for index, chunk in enumerate(chunks, start=1):
            accepted, complete = decoder.receive_part_info(
                f"ur:bw-stellar-sign-request/{index}-{total}/{chunk}"
            )
            assert accepted is True
            if index < total:
                assert complete is False
            else:
                assert complete is True

        req = decoder.result()
        assert req.request_id == payload["req_id"]


# ---------------------------------------------------------------------------
# encoder
# ---------------------------------------------------------------------------

class TestEncoder:
    @staticmethod
    def _decode_simple_ur_json(parts: list[str]) -> dict:
        assert parts
        first = parts[0].split("/")
        assert first[0].startswith("ur:")

        if len(first) == 2:
            payload = first[1]
        else:
            prefix = first[0]
            total = int(first[1].split("-")[1])
            chunks = {}
            for part in parts:
                fragment = part.split("/")
                assert fragment[0] == prefix
                index, current_total = fragment[1].split("-")
                assert int(current_total) == total
                chunks[int(index)] = fragment[2]
            payload = "".join(chunks[i] for i in range(1, total + 1))

        padded = payload + "=" * ((4 - (len(payload) % 4)) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        return json.loads(decoded.decode("utf-8"))

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

        payload = self._decode_simple_ur_json(parts)
        assert set(payload.keys()) == {
            "request_id",
            "signed_xdr",
            "signatures",
            "signer_pubkey",
        }

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

        payload = self._decode_simple_ur_json(parts)
        assert sorted(payload.keys()) == ["accounts", "device"]
        assert sorted(payload["accounts"][0].keys()) == ["bipPath", "label", "publicKey"]
