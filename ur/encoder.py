"""
Encode Stellar payloads into UR fountain-code strings for QR display.

Each call to next_part() returns one string to render as a QR code frame.
"""
import base64
import json

from _bc_ur.ur import UR
from _bc_ur.ur_encoder import UREncoder as _UREncoder

from config import MAX_FRAGMENT_LEN
from ur.types import (
    BwStellarAccountsPayload,
    XlmSignature,
)


def encode_xlm_signature(sig: XlmSignature, max_fragment_len: int = MAX_FRAGMENT_LEN) -> list[str]:
    """
    Encode XlmSignature → list of UR fragment strings for animated QR.
    """
    payload = {
        "request_id": sig.request_id,
        "signer_pubkey": sig.signer_pubkey,
        "signed_xdr": sig.signed_xdr,
        "signatures": sig.signatures,
    }
    return _encode_simple_json_ur("bw-stellar-signature", payload, max_fragment_len)


def encode_bw_stellar_accounts(
    payload: BwStellarAccountsPayload,
    max_fragment_len: int = MAX_FRAGMENT_LEN,
) -> list[str]:
    payload_dict = {
        "device": {
            "id": payload.device.id,
            "label": payload.device.label,
            **({"fwVersion": payload.device.fwVersion} if payload.device.fwVersion else {}),
        },
        "accounts": [
            {
                "publicKey": account.publicKey,
                "bipPath": account.bipPath,
                **({"label": account.label} if account.label else {}),
            }
            for account in payload.accounts
        ],
    }
    return _encode_simple_json_ur("bw-stellar-accounts", payload_dict, max_fragment_len)


def _encode_to_parts(ur: UR, max_fragment_len: int) -> list[str]:
    """
    Collect enough parts from the fountain encoder for one full cycle.
    For single-part URs, returns one element.
    For multi-part URs, returns encoder.expected_part_count() parts.
    """
    encoder = _UREncoder(ur, max_fragment_len)
    if encoder.is_single_part():
        return [encoder.next_part()]

    count = encoder.expected_part_count()
    return [encoder.next_part() for _ in range(count)]


def _encode_simple_json_ur(ur_type: str, payload: dict, max_fragment_len: int) -> list[str]:
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(json_bytes).decode("ascii").rstrip("=")
    prefix = f"ur:{ur_type}"
    if len(encoded_payload) <= max_fragment_len:
        return [f"{prefix}/{encoded_payload}"]

    total = (len(encoded_payload) + max_fragment_len - 1) // max_fragment_len
    parts = []
    for i in range(total):
        chunk = encoded_payload[i * max_fragment_len: (i + 1) * max_fragment_len]
        parts.append(f"{prefix}/{i + 1}-{total}/{chunk}")
    return parts
