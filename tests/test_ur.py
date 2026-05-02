"""
Tests for ur/ — decoder, encoder, types.

bc-ur is vendored in _bc_ur/ so these tests always run.
"""
import base64
import json

from ur.types import (
    BwStellarAccount,
    BwStellarAccountsPayload,
    BwStellarDevice,
    XlmSignature,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic payloads
# ---------------------------------------------------------------------------


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
    def test_receive_part_info_tracks_accept_reject_counts(self):
        from ur.decoder import URDecoder

        decoder = URDecoder()

        accepted, complete = decoder.receive_part_info("not-a-ur")
        assert accepted is False
        assert complete is False
        assert decoder.accepted_parts == 0
        assert decoder.rejected_parts == 1

        payload = _make_bw_stellar_sign_request_data()
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
        accepted, complete = decoder.receive_part_info(f"ur:bw-stellar-sign-request/{encoded}")
        assert accepted is True
        assert decoder.accepted_parts == 1
        assert decoder.rejected_parts == 1
        assert complete is True

    def test_reset_clears_receive_part_counters(self):
        from ur.decoder import URDecoder

        decoder = URDecoder()

        payload = _make_bw_stellar_sign_request_data()
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
        decoder.receive_part_info(f"ur:bw-stellar-sign-request/{encoded}")
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

    def test_parse_bw_stellar_sign_request_with_tx_xdr_only(self):
        from ur.decoder import _parse_bw_stellar_sign_request_data

        req = _parse_bw_stellar_sign_request_data(
            {
                "kind": "tx",
                "req_id": "req-xdr-only",
                "signer_pubkey": "GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX",
                "network_passphrase": "Test SDF Network ; September 2015",
                "tx_xdr": "AAAA",
            }
        )
        assert req.request_id == "req-xdr-only"
        assert req.tx_xdr == "AAAA"
        assert req.sep7_uri is None

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

    def test_ur_decoder_accepts_bare_sep7_tx_uri(self):
        from ur.decoder import URDecoder

        uri = (
            "web+stellar:tx"
            "?xdr=AAAA"
            "&network_passphrase=Test%20SDF%20Network%20%3B%20September%202015"
            "&pubkey=GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX"
            "&req_id=req-sep7-1"
        )
        decoder = URDecoder()
        accepted, complete = decoder.receive_part_info(uri)
        assert accepted is True
        assert complete is True
        req = decoder.result()
        assert req.request_id == "req-sep7-1"
        assert req.signer_pubkey.startswith("G")
        assert req.tx_xdr == "AAAA"


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
