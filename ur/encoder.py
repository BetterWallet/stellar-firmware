"""
Encode EthSignature and CryptoHDKey into UR fountain-code strings for QR display.

Each call to next_part() returns one string to render as a QR code frame.
"""
import cbor2
from _bc_ur.ur import UR
from _bc_ur.ur_encoder import UREncoder as _UREncoder

from config import MAX_FRAGMENT_LEN
from ur.types import (
    BwStellarAccountsPayload,
    CryptoHDKey,
    EthSignature,
    XlmSignature,
)


def encode_eth_signature(sig: EthSignature, max_fragment_len: int = MAX_FRAGMENT_LEN) -> list[str]:
    """
    Encode EthSignature → list of UR fragment strings for animated QR.

    For small payloads this will be a single-element list.
    For larger payloads, fountain coding produces multiple parts.
    """
    cbor_bytes = cbor2.dumps({
        1: sig.request_id,
        2: sig.signature,
    })
    ur = UR("eth-signature", cbor_bytes)
    return _encode_to_parts(ur, max_fragment_len)


def encode_xlm_signature(sig: XlmSignature, max_fragment_len: int = MAX_FRAGMENT_LEN) -> list[str]:
    """
    Encode XlmSignature → list of UR fragment strings for animated QR.
    """
    cbor_bytes = cbor2.dumps({
        "request_id": sig.request_id,
        "signer_pubkey": sig.signer_pubkey,
        "signed_xdr": sig.signed_xdr,
        "signatures": sig.signatures,
    })
    ur = UR("bw-stellar-signature", cbor_bytes)
    return _encode_to_parts(ur, max_fragment_len)


def encode_bw_stellar_accounts(
    payload: BwStellarAccountsPayload,
    max_fragment_len: int = MAX_FRAGMENT_LEN,
) -> list[str]:
    cbor_bytes = cbor2.dumps({
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
    })
    ur = UR("bw-stellar-accounts", cbor_bytes)
    return _encode_to_parts(ur, max_fragment_len)


def _build_keypath(path_str: str, source_fingerprint: bytes | None = None) -> cbor2.CBORTag:
    """Build a tagged crypto-keypath (CBOR tag 304).

    Path components are a flat alternating array: [index, hardened, index, hardened, ...]
    """
    components = []
    for part in path_str.split("/"):
        if not part:
            continue
        hardened = part.endswith("'")
        index = int(part.rstrip("'"))
        components.append(index)
        components.append(hardened)
    keypath = {1: components}
    if source_fingerprint is not None:
        keypath[2] = int.from_bytes(source_fingerprint, "big")
    return cbor2.CBORTag(304, keypath)


def _build_children_keypath() -> cbor2.CBORTag:
    """Build a tagged crypto-keypath for children: 0/* (non-hardened index 0 + wildcard).

    In the Blockchain Commons spec, a wildcard child is represented as an
    empty list [] in the components array.  The flat alternating encoding is:
      [child_index, hardened_flag, [], hardened_flag]
    Keystone uses [0, False, [], False] for "0/*".
    """
    return cbor2.CBORTag(304, {1: [0, False, [], False]})


def _build_hdkey_cbor(hdkey: CryptoHDKey) -> dict:
    """Build the CBOR map for a single crypto-hdkey."""
    return {
        2: False,                                                      # is_private
        3: hdkey.key_data,                                             # compressed pubkey
        4: hdkey.chain_code,                                           # chain code
        6: _build_keypath(hdkey.origin_path, hdkey.master_fingerprint),  # origin
        7: _build_children_keypath(),                                  # children: 0/*
        8: int.from_bytes(hdkey.parent_fingerprint, "big"),            # parent fingerprint (uint32)
        9: "Cold Wallet",                                              # name
        10: "account.standard",                                        # note
    }


def encode_crypto_hdkey(hdkey: CryptoHDKey, max_fragment_len: int = MAX_FRAGMENT_LEN) -> list[str]:
    """
    Encode CryptoHDKey → ur:crypto-hdkey UR fragment strings.
    No outer tag 303 — UR type string serves as type identifier.
    """
    cbor_bytes = cbor2.dumps(_build_hdkey_cbor(hdkey))
    ur = UR("crypto-hdkey", cbor_bytes)
    return _encode_to_parts(ur, max_fragment_len)


def encode_crypto_multi_accounts(hdkey: CryptoHDKey, max_fragment_len: int = MAX_FRAGMENT_LEN) -> list[str]:
    """
    Encode CryptoHDKey → ur:crypto-multi-accounts UR fragment strings.

    This is what MetaMask/Rabby Keystone integration expects.
    The hdkey is wrapped in CBOR tag 303 when embedded inside multi-accounts.
    """
    master_fp_uint = int.from_bytes(hdkey.master_fingerprint, "big")

    cbor_bytes = cbor2.dumps({
        1: master_fp_uint,                                   # master fingerprint
        2: [cbor2.CBORTag(303, _build_hdkey_cbor(hdkey))],   # array of tagged hdkeys
        3: "Cold Wallet",                                    # device name
    })
    ur = UR("crypto-multi-accounts", cbor_bytes)
    return _encode_to_parts(ur, max_fragment_len)


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
