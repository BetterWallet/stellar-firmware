"""
Accumulates UR fountain-code fragments until the full payload is received,
then decodes the CBOR into a chain-specific sign request.

Uses foundation-ur (bc-ur) for the UR layer and cbor2 for CBOR parsing.

Two transports are supported:
  - Animated UR fragments  → bw-stellar-sign-request (Stellar)
"""
import base64
import json
import re

import cbor2
from _bc_ur.ur_decoder import URDecoder as _URDecoder

from stellar import sep7
from ur.types import XlmSignRequest


class URDecoder:
    """Wraps foundation-ur URDecoder. Feed string fragments, call result() when done.
    """

    def __init__(self):
        self._decoder = _URDecoder()
        self._sep7_uri: str | None = None
        self._simple_bw_payload: str | None = None
        self._simple_bw_type: str | None = None
        self._simple_bw_parts: dict[str, dict] = {}
        self.accepted_parts = 0
        self.rejected_parts = 0
        self.last_part_accepted = False

    def receive_part(self, part: str) -> bool:
        _accepted, complete = self.receive_part_info(part)
        return complete

    def receive_part_info(self, part: str) -> tuple[bool, bool]:
        """Feed one QR payload (UR fragment). Returns (accepted, complete)."""
        if sep7.is_sep7(part):
            self._sep7_uri = part
            self.last_part_accepted = True
            self.accepted_parts += 1
            return True, True

        simple_accepted, simple_complete = self._receive_simple_bw_part(part)
        if simple_accepted:
            self.last_part_accepted = True
            self.accepted_parts += 1
            return True, simple_complete

        accepted = self._decoder.receive_part(part)
        self.last_part_accepted = accepted
        if accepted:
            self.accepted_parts += 1
        else:
            self.rejected_parts += 1
        return accepted, self._decoder.is_complete()

    def is_complete(self) -> bool:
        return (
            self._sep7_uri is not None
            or self._simple_bw_payload is not None
            or self._decoder.is_complete()
        )

    def progress(self) -> float:
        if self._sep7_uri is not None:
            return 1.0
        if self._simple_bw_payload is not None:
            return 1.0
        if self._simple_bw_parts:
            first = next(iter(self._simple_bw_parts.values()))
            return len(first["chunks"]) / max(1, first["total"])
        try:
            return self._decoder.estimated_percent_complete()
        except AttributeError:
            return 1.0 if self._decoder.is_complete() else 0.0

    def result(self):
        """Return the decoded Stellar sign request. Call only when complete."""
        if self._sep7_uri is not None:
            return _parse_sep7_sign_request_uri(self._sep7_uri)

        if self._simple_bw_payload is not None and self._simple_bw_type is not None:
            return _parse_bw_stellar_sign_request_payload(
                self._simple_bw_type,
                self._simple_bw_payload,
            )

        ur = self._decoder.result_ur()
        if ur.type == "bw-stellar-sign-request":
            return _parse_bw_stellar_sign_request(ur.cbor)
        raise ValueError(f"unexpected UR type: {ur.type!r}")

    def reset(self):
        self._decoder = _URDecoder()
        self._sep7_uri = None
        self._simple_bw_payload = None
        self._simple_bw_type = None
        self._simple_bw_parts = {}
        self.accepted_parts = 0
        self.rejected_parts = 0
        self.last_part_accepted = False

    def _receive_simple_bw_part(self, part: str) -> tuple[bool, bool]:
        if not part.startswith("ur:bw-stellar-"):
            return False, False

        fragments = part.split("/")
        if len(fragments) < 2:
            return False, False

        prefix = fragments[0]
        ur_type = prefix.removeprefix("ur:")
        if ur_type != "bw-stellar-sign-request":
            return False, False

        if len(fragments) == 2:
            self._simple_bw_type = ur_type
            self._simple_bw_payload = fragments[1]
            self._simple_bw_parts = {}
            return True, True

        if len(fragments) == 3:
            index_total = fragments[1]
            chunk = fragments[2]
            match = re.match(r"^(\d+)-(\d+)$", index_total)
            if not match:
                return False, False
            index = int(match.group(1))
            total = int(match.group(2))
            if index <= 0 or total <= 0 or index > total:
                return False, False

            current = self._simple_bw_parts.setdefault(
                prefix,
                {"total": total, "chunks": {}},
            )
            current["total"] = total
            current["chunks"][index] = chunk
            if len(current["chunks"]) < total:
                return True, False

            assembled = []
            for i in range(1, total + 1):
                piece = current["chunks"].get(i)
                if piece is None:
                    return True, False
                assembled.append(piece)

            self._simple_bw_type = ur_type
            self._simple_bw_payload = "".join(assembled)
            self._simple_bw_parts = {}
            return True, True

        return False, False


def _parse_bw_stellar_sign_request(cbor_bytes: bytes) -> XlmSignRequest:
    data = cbor2.loads(cbor_bytes)
    return _parse_bw_stellar_sign_request_data(data)


def _parse_bw_stellar_sign_request_payload(ur_type: str, encoded_payload: str) -> XlmSignRequest:
    if ur_type != "bw-stellar-sign-request":
        raise ValueError(f"unexpected simple UR type: {ur_type!r}")
    json_bytes = _decode_base64url(encoded_payload)
    data = json.loads(json_bytes.decode("utf-8"))
    return _parse_bw_stellar_sign_request_data(data)


def _parse_bw_stellar_sign_request_data(data: dict) -> XlmSignRequest:
    kind = data.get("kind")
    if kind != "tx":
        raise ValueError(f"unsupported bw-stellar-sign-request kind: {kind!r}")

    req_id = data.get("req_id")
    signer_pubkey = data.get("signer_pubkey")
    network_passphrase = data.get("network_passphrase")
    sep7_uri = data.get("sep7_uri")
    tx_xdr = data.get("tx_xdr")

    if not isinstance(req_id, str) or not req_id:
        raise ValueError("bw-stellar-sign-request missing req_id")
    if not isinstance(signer_pubkey, str) or not signer_pubkey:
        raise ValueError("bw-stellar-sign-request missing signer_pubkey")
    if not isinstance(network_passphrase, str) or not network_passphrase:
        raise ValueError("bw-stellar-sign-request missing network_passphrase")
    if (not isinstance(sep7_uri, str) or not sep7_uri) and (
        not isinstance(tx_xdr, str) or not tx_xdr
    ):
        raise ValueError("bw-stellar-sign-request missing sep7_uri or tx_xdr")

    return XlmSignRequest(
        request_id=req_id,
        signer_pubkey=signer_pubkey,
        network_passphrase=network_passphrase,
        sep7_uri=sep7_uri if isinstance(sep7_uri, str) and sep7_uri else None,
        tx_xdr=tx_xdr if isinstance(tx_xdr, str) and tx_xdr else None,
        kind=kind,
    )


def _decode_base64url(data: str) -> bytes:
    padding = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _parse_sep7_sign_request_uri(uri: str) -> XlmSignRequest:
    parsed = sep7.parse(uri)
    if parsed.xdr is None:
        raise ValueError("SEP-7 URI does not carry a transaction XDR")
    if not parsed.pubkey:
        raise ValueError("SEP-7 URI missing required pubkey parameter")

    req_id = parsed.req_id
    if not req_id:
        req_id = "sep7-" + base64.urlsafe_b64encode(parsed.xdr.encode("utf-8"))[:12].decode("ascii")

    return XlmSignRequest(
        request_id=req_id,
        signer_pubkey=parsed.pubkey,
        network_passphrase=parsed.network_passphrase,
        sep7_uri=uri,
        tx_xdr=parsed.xdr,
        kind="tx",
    )
