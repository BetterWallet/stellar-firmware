"""
Accumulates UR fountain-code fragments until the full payload is received,
then decodes the CBOR into a chain-specific sign request.

Uses foundation-ur (bc-ur) for the UR layer and cbor2 for CBOR parsing.

Two transports are supported:
  - Animated UR fragments  → eth-sign-request (Ethereum / EIP-4527)
                          → bw-stellar-sign-request (Stellar)
"""

import cbor2
from _bc_ur.ur_decoder import URDecoder as _URDecoder

from ur.types import EthSignRequest, XlmSignRequest

# CBOR tag for crypto-keypath (EIP-4527 / bc-ur spec)
_KEYPATH_TAG = 304


def _decode_keypath(value) -> str:
    """Decode a crypto-keypath CBOR structure into a string like "44'/60'/0'/0/0"."""
    if isinstance(value, cbor2.CBORTag):
        value = value.value
    components = value.get(1, [])
    parts = []
    for comp in components:
        if isinstance(comp, list) and len(comp) == 2:
            index, hardened = comp
            parts.append(f"{index}'" if hardened else str(index))
    return "/".join(parts)


class URDecoder:
    """Wraps foundation-ur URDecoder. Feed string fragments, call result() when done.
    """

    def __init__(self):
        self._decoder = _URDecoder()
        self.accepted_parts = 0
        self.rejected_parts = 0
        self.last_part_accepted = False

    def receive_part(self, part: str) -> bool:
        _accepted, complete = self.receive_part_info(part)
        return complete

    def receive_part_info(self, part: str) -> tuple[bool, bool]:
        """Feed one QR payload (UR fragment). Returns (accepted, complete)."""
        accepted = self._decoder.receive_part(part)
        self.last_part_accepted = accepted
        if accepted:
            self.accepted_parts += 1
        else:
            self.rejected_parts += 1
        return accepted, self._decoder.is_complete()

    def is_complete(self) -> bool:
        return self._decoder.is_complete()

    def progress(self) -> float:
        try:
            return self._decoder.estimated_percent_complete()
        except AttributeError:
            return 1.0 if self._decoder.is_complete() else 0.0

    def result(self):
        """Return the decoded sign request (Eth or Xlm). Call only when complete."""
        ur = self._decoder.result_ur()
        if ur.type == "eth-sign-request":
            return _parse_eth_sign_request(ur.cbor)
        if ur.type == "bw-stellar-sign-request":
            return _parse_bw_stellar_sign_request(ur.cbor)
        raise ValueError(f"unexpected UR type: {ur.type!r}")

    def reset(self):
        self._decoder = _URDecoder()
        self.accepted_parts = 0
        self.rejected_parts = 0
        self.last_part_accepted = False


def _parse_eth_sign_request(cbor_bytes: bytes) -> EthSignRequest:
    data = cbor2.loads(cbor_bytes)

    request_id: bytes = data[1]
    sign_data: bytes  = data[2]
    data_type: int    = data[3]
    chain_id: int     = data.get(4, 1)

    raw_path = data[5]
    derivation_path = _decode_keypath(raw_path)

    address: str | None = None
    if 6 in data:
        addr_bytes: bytes = data[6]
        address = "0x" + addr_bytes.hex()

    return EthSignRequest(
        request_id=request_id,
        sign_data=sign_data,
        data_type=data_type,
        chain_id=chain_id,
        derivation_path=derivation_path,
        address=address,
    )


def _parse_bw_stellar_sign_request(cbor_bytes: bytes) -> XlmSignRequest:
    data = cbor2.loads(cbor_bytes)
    kind = data.get("kind")
    if kind != "tx":
        raise ValueError(f"unsupported bw-stellar-sign-request kind: {kind!r}")

    req_id = data.get("req_id")
    signer_pubkey = data.get("signer_pubkey")
    network_passphrase = data.get("network_passphrase")
    sep7_uri = data.get("sep7_uri")

    if not isinstance(req_id, str) or not req_id:
        raise ValueError("bw-stellar-sign-request missing req_id")
    if not isinstance(signer_pubkey, str) or not signer_pubkey:
        raise ValueError("bw-stellar-sign-request missing signer_pubkey")
    if not isinstance(network_passphrase, str) or not network_passphrase:
        raise ValueError("bw-stellar-sign-request missing network_passphrase")
    if not isinstance(sep7_uri, str) or not sep7_uri:
        raise ValueError("bw-stellar-sign-request missing sep7_uri")

    return XlmSignRequest(
        request_id=req_id,
        signer_pubkey=signer_pubkey,
        network_passphrase=network_passphrase,
        sep7_uri=sep7_uri,
        kind=kind,
    )
