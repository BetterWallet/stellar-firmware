"""
Decode EIP-712 TypedData from the raw bytes in an EthSignRequest.

For data_type=2, MetaMask encodes the TypedData as UTF-8 JSON.
"""
import json
from dataclasses import dataclass


@dataclass
class TypedData:
    domain: dict
    types: dict
    primary_type: str
    message: dict


def parse(sign_data: bytes) -> TypedData:
    """Parse EIP-712 typed data from raw bytes (UTF-8 JSON)."""
    raw = json.loads(sign_data.decode("utf-8"))
    return TypedData(
        domain=raw["domain"],
        types=raw["types"],
        primary_type=raw["primaryType"],
        message=raw["message"],
    )
