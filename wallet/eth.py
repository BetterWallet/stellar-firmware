"""
Ethereum-specific signing + display formatting.

Extracted from wallet/signer.py and state/machine.py so the chain-specific
logic lives in one place. Public surface:

    sign(account, request: EthSignRequest) -> bytes        # 65-byte r||s||v
    format_fields(request: EthSignRequest) -> list[DisplayField]
"""
import rlp
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address

from eip712.display import DisplayField
from ur.types import EthSignRequest


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------

def sign(account, request: EthSignRequest) -> bytes:
    """
    Sign request.sign_data with account. Returns 65 bytes: r (32) + s (32) + v (1).

    data_type values (per EIP-4527):
        1 = legacy transaction (RLP encoded)
        2 = EIP-712 typed data (JSON bytes)
        3 = personal_sign (raw message bytes)
        4 = typed transaction / EIP-1559 (RLP with type prefix)
    """
    dtype = request.data_type
    if dtype == 3:
        return _sign_personal(account, request.sign_data)
    if dtype == 2:
        return _sign_typed_data(account, request.sign_data)
    if dtype in (1, 4):
        return _sign_transaction(account, request.sign_data, request.chain_id, dtype)
    raise ValueError(f"unsupported data_type: {dtype}")


def _sign_personal(account, data: bytes) -> bytes:
    msg = encode_defunct(data)
    signed = account.sign_message(msg)
    return _to_rsv(signed.r, signed.s, _normalize_recovery_id(signed.v))


def _sign_typed_data(account, data: bytes) -> bytes:
    import json
    raw = json.loads(data.decode("utf-8"))
    domain       = raw["domain"]
    types        = {k: v for k, v in raw["types"].items() if k != "EIP712Domain"}
    primary_type = raw["primaryType"]
    message      = raw["message"]
    signed = account.sign_typed_data(
        domain_data=domain,
        message_types=types,
        message_data=message,
    )
    return _to_rsv(signed.r, signed.s, _normalize_recovery_id(signed.v))


def _sign_transaction(account, data: bytes, chain_id: int, dtype: int) -> bytes:
    """Sign a raw RLP-encoded unsigned transaction."""
    if dtype == 4 and data[0] == 0x02:
        # EIP-1559: strip type byte, decode RLP
        decoded = rlp.decode(data[1:])
        tx = {
            "type":                 "0x2",
            "chainId":              int.from_bytes(decoded[0], "big") if decoded[0] else chain_id,
            "nonce":                int.from_bytes(decoded[1], "big") if decoded[1] else 0,
            "maxPriorityFeePerGas": int.from_bytes(decoded[2], "big") if decoded[2] else 0,
            "maxFeePerGas":         int.from_bytes(decoded[3], "big") if decoded[3] else 0,
            "gas":                  int.from_bytes(decoded[4], "big") if decoded[4] else 0,
            "to":                   to_checksum_address("0x" + decoded[5].hex()) if decoded[5] else None,
            "value":                int.from_bytes(decoded[6], "big") if decoded[6] else 0,
            "data":                 "0x" + decoded[7].hex() if decoded[7] else "0x",
        }
    else:
        # Legacy: RLP([nonce, gasPrice, gas, to, value, data])
        decoded = rlp.decode(data)
        tx = {
            "nonce":    int.from_bytes(decoded[0], "big") if decoded[0] else 0,
            "gasPrice": int.from_bytes(decoded[1], "big") if decoded[1] else 0,
            "gas":      int.from_bytes(decoded[2], "big") if decoded[2] else 0,
            "to":       to_checksum_address("0x" + decoded[3].hex()) if decoded[3] else None,
            "value":    int.from_bytes(decoded[4], "big") if decoded[4] else 0,
            "data":     "0x" + decoded[5].hex() if decoded[5] else "0x",
            "chainId":  chain_id,
        }
    signed = account.sign_transaction(tx)
    return _to_rsv(signed.r, signed.s, _normalize_recovery_id(signed.v))


def _to_rsv(r: int, s: int, v: int) -> bytes:
    return r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([v % 256])


def _normalize_recovery_id(v: int) -> int:
    """Normalize Ethereum-style v values into a 0/1 recovery id."""
    if v >= 35:
        return (v - 35) % 2
    if v >= 27:
        return v - 27
    return v


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------

def format_fields(request: EthSignRequest) -> list[DisplayField]:
    """Format a legacy or EIP-1559 transaction for the confirm screen.

    On any decode error, falls back to a hex dump of sign_data so the user
    can still verify the request manually.
    """
    data = request.sign_data
    fields: list[DisplayField] = []

    try:
        if request.data_type == 4 and data[0] == 0x02:
            decoded = rlp.decode(data[1:])
            chain_id = int.from_bytes(decoded[0], "big") if decoded[0] else request.chain_id
            fields.append(DisplayField("Type", "EIP-1559"))
            fields.append(DisplayField("Chain ID", str(chain_id)))
            fields.append(DisplayField("To", "0x" + decoded[5].hex() if decoded[5] else "(none)"))
            value = int.from_bytes(decoded[6], "big") if decoded[6] else 0
            fields.append(DisplayField("Value", f"{value / 1e18:.8f} ETH"))
            max_fee = int.from_bytes(decoded[3], "big") if decoded[3] else 0
            fields.append(DisplayField("Max Fee (Gwei)", str(max_fee // 10**9)))
        else:
            decoded = rlp.decode(data)
            fields.append(DisplayField("Type", "Legacy"))
            fields.append(DisplayField("Chain ID", str(request.chain_id)))
            fields.append(DisplayField("To", "0x" + decoded[3].hex() if decoded[3] else "(none)"))
            value = int.from_bytes(decoded[4], "big") if decoded[4] else 0
            fields.append(DisplayField("Value", f"{value / 1e18:.8f} ETH"))
            gas_price = int.from_bytes(decoded[1], "big") if decoded[1] else 0
            fields.append(DisplayField("Gas Price (Gwei)", str(gas_price // 10**9)))
    except Exception:
        fields.append(DisplayField("Sign Data", request.sign_data.hex()))

    fields.append(DisplayField("Path", request.derivation_path))
    return fields
