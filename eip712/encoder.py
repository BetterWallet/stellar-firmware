"""
EIP-712 structured data hashing.

Implements encodeType, encodeData, hashStruct per the EIP-712 specification.
https://eips.ethereum.org/EIPS/eip-712
"""
import re
import struct

from eth_hash.auto import keccak

# ---------------------------------------------------------------------------
# Type string encoding
# ---------------------------------------------------------------------------

def encode_type(primary_type: str, types: dict) -> str:
    """
    Build the EIP-712 type string, e.g.:
    "Mail(Person from,Person to,string contents)Person(string name,address wallet)"
    """
    result = _encode_single_type(primary_type, types)
    # Append referenced types in alphabetical order (excluding primary)
    deps = sorted(_collect_deps(primary_type, types) - {primary_type})
    for dep in deps:
        result += _encode_single_type(dep, types)
    return result


def _encode_single_type(type_name: str, types: dict) -> str:
    fields = types[type_name]
    params = ",".join(f"{f['type']} {f['name']}" for f in fields)
    return f"{type_name}({params})"


def _collect_deps(type_name: str, types: dict, seen: set | None = None) -> set:
    if seen is None:
        seen = set()
    if type_name in seen or type_name not in types:
        return seen
    seen.add(type_name)
    for field in types[type_name]:
        base = _base_type(field["type"])
        _collect_deps(base, types, seen)
    return seen


def _base_type(type_str: str) -> str:
    """Strip array suffix: 'Person[]' → 'Person', 'Person[3]' → 'Person'."""
    return re.sub(r"\[.*\]$", "", type_str)


def type_hash(primary_type: str, types: dict) -> bytes:
    return keccak(encode_type(primary_type, types).encode("utf-8"))


# ---------------------------------------------------------------------------
# Data encoding
# ---------------------------------------------------------------------------

_ATOMIC_TYPES = {
    "address", "bool", "bytes",
    *(f"uint{8*i}" for i in range(1, 33)),
    *(f"int{8*i}"  for i in range(1, 33)),
    *(f"bytes{i}"  for i in range(1, 33)),
    "string",
}


def encode_data(primary_type: str, message: dict, types: dict) -> bytes:
    """
    Encode structured data per EIP-712 §Definition of encodeData.
    Returns the concatenated encoded fields (typeHash is NOT prepended here).
    """
    encoded = b""
    for field in types[primary_type]:
        fname = field["name"]
        ftype = field["type"]
        value = message[fname]
        encoded += _encode_value(ftype, value, types)
    return encoded


def _encode_value(ftype: str, value, types: dict) -> bytes:
    # Array types
    if ftype.endswith("]"):
        base = _base_type(ftype)
        inner = b"".join(_encode_value(base, v, types) for v in value)
        return keccak(inner)

    # Struct types (reference types)
    if ftype in types:
        return hash_struct(ftype, value, types)

    # Atomic / dynamic types
    if ftype == "string":
        return keccak(value.encode("utf-8"))
    if ftype == "bytes":
        data = bytes.fromhex(value[2:]) if isinstance(value, str) and value.startswith("0x") else bytes(value)
        return keccak(data)
    if ftype == "address":
        addr = value.lower().removeprefix("0x")
        return bytes.fromhex(addr).rjust(32, b"\x00")
    if ftype == "bool":
        return (1 if value else 0).to_bytes(32, "big")
    if ftype.startswith("uint"):
        bits = int(ftype[4:]) if ftype[4:] else 256
        return int(value, 16).to_bytes(32, "big") if isinstance(value, str) and value.startswith("0x") else int(value).to_bytes(32, "big")
    if ftype.startswith("int"):
        n = int(value, 16) if isinstance(value, str) and value.startswith("0x") else int(value)
        return n.to_bytes(32, "big", signed=True)
    if ftype.startswith("bytes") and ftype[5:].isdigit():
        # bytesN — right-padded to 32 bytes
        data = bytes.fromhex(value[2:]) if isinstance(value, str) and value.startswith("0x") else bytes(value)
        return data.ljust(32, b"\x00")

    raise ValueError(f"unsupported EIP-712 type: {ftype!r}")


def hash_struct(primary_type: str, message: dict, types: dict) -> bytes:
    """keccak256(typeHash ‖ encodeData)"""
    th = type_hash(primary_type, types)
    ed = encode_data(primary_type, message, types)
    return keccak(th + ed)


# ---------------------------------------------------------------------------
# Domain separator
# ---------------------------------------------------------------------------

_DOMAIN_FIELDS = [
    {"name": "name",              "type": "string"},
    {"name": "version",           "type": "string"},
    {"name": "chainId",           "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
    {"name": "salt",              "type": "bytes32"},
]


def domain_separator(domain: dict) -> bytes:
    """Compute the EIP-712 domain separator hash."""
    # Build a types dict that only includes the fields present in domain
    present_fields = [f for f in _DOMAIN_FIELDS if f["name"] in domain]
    domain_types = {"EIP712Domain": present_fields}
    return hash_struct("EIP712Domain", domain, domain_types)


def sign_hash(domain: dict, types: dict, primary_type: str, message: dict) -> bytes:
    """
    Compute the final EIP-712 hash:
    keccak256("\\x19\\x01" ‖ domainSeparator ‖ hashStruct(message))
    """
    ds = domain_separator(domain)
    ms = hash_struct(primary_type, message, types)
    return keccak(b"\x19\x01" + ds + ms)
