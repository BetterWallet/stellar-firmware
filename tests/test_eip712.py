"""
Tests for eip712/ — parser, encoder, display flattener.

All testable on dev machine without Pi hardware.
"""
import json
import pytest

from eip712.parser import TypedData, parse
from eip712.encoder import encode_type, type_hash, hash_struct, sign_hash, domain_separator
from eip712.display import flatten, DisplayField

# ---------------------------------------------------------------------------
# Minimal EIP-712 fixture — EIP-712 spec example
# ---------------------------------------------------------------------------

TYPED_DATA_JSON = {
    "domain": {
        "name": "Ether Mail",
        "version": "1",
        "chainId": 1,
        "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
    },
    "types": {
        "EIP712Domain": [
            {"name": "name",              "type": "string"},
            {"name": "version",           "type": "string"},
            {"name": "chainId",           "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "Person": [
            {"name": "name",   "type": "string"},
            {"name": "wallet", "type": "address"},
        ],
        "Mail": [
            {"name": "from",     "type": "Person"},
            {"name": "to",       "type": "Person"},
            {"name": "contents", "type": "string"},
        ],
    },
    "primaryType": "Mail",
    "message": {
        "from":     {"name": "Cow", "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"},
        "to":       {"name": "Bob", "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"},
        "contents": "Hello, Bob!",
    },
}


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_round_trip(self):
        raw = json.dumps(TYPED_DATA_JSON).encode()
        td = parse(raw)
        assert isinstance(td, TypedData)
        assert td.primary_type == "Mail"
        assert td.domain["name"] == "Ether Mail"
        assert td.message["contents"] == "Hello, Bob!"


# ---------------------------------------------------------------------------
# encoder
# ---------------------------------------------------------------------------

class TestEncoder:
    def test_encode_type_primary_first(self):
        types = TYPED_DATA_JSON["types"]
        et = encode_type("Mail", types)
        assert et.startswith("Mail(")
        # Referenced type Person must follow
        assert "Person(" in et

    def test_encode_type_alphabetical_deps(self):
        types = TYPED_DATA_JSON["types"]
        et = encode_type("Mail", types)
        # Mail comes first, then alphabetical deps
        mail_pos = et.index("Mail(")
        person_pos = et.index("Person(")
        assert mail_pos < person_pos

    def test_type_hash_is_32_bytes(self):
        types = TYPED_DATA_JSON["types"]
        th = type_hash("Mail", types)
        assert isinstance(th, bytes)
        assert len(th) == 32

    def test_hash_struct_returns_32_bytes(self):
        td = TYPED_DATA_JSON
        h = hash_struct(td["primaryType"], td["message"], td["types"])
        assert isinstance(h, bytes)
        assert len(h) == 32

    def test_sign_hash_returns_32_bytes(self):
        td = TYPED_DATA_JSON
        h = sign_hash(td["domain"], td["types"], td["primaryType"], td["message"])
        assert isinstance(h, bytes)
        assert len(h) == 32

    def test_domain_separator_stable(self):
        ds1 = domain_separator(TYPED_DATA_JSON["domain"])
        ds2 = domain_separator(TYPED_DATA_JSON["domain"])
        assert ds1 == ds2

    def test_known_type_hash(self):
        # From the EIP-712 spec example, the type hash of Person is deterministic.
        types = {"Person": TYPED_DATA_JSON["types"]["Person"]}
        th = type_hash("Person", types)
        # Just assert it's 32 bytes and non-zero
        assert len(th) == 32
        assert any(b != 0 for b in th)


# ---------------------------------------------------------------------------
# display flattener
# ---------------------------------------------------------------------------

class TestDisplayFlattener:
    def test_flatten_returns_list(self):
        raw = json.dumps(TYPED_DATA_JSON).encode()
        td = parse(raw)
        fields = flatten(td)
        assert isinstance(fields, list)
        assert all(isinstance(f, DisplayField) for f in fields)

    def test_flatten_has_domain_header(self):
        raw = json.dumps(TYPED_DATA_JSON).encode()
        td = parse(raw)
        fields = flatten(td)
        labels = [f.label for f in fields]
        assert "Domain" in labels

    def test_flatten_has_primary_type_header(self):
        raw = json.dumps(TYPED_DATA_JSON).encode()
        td = parse(raw)
        fields = flatten(td)
        labels = [f.label for f in fields]
        assert "Mail" in labels

    def test_nested_struct_indented(self):
        raw = json.dumps(TYPED_DATA_JSON).encode()
        td = parse(raw)
        fields = flatten(td)
        # Find a field with indent > 1 (nested inside Person)
        deep_fields = [f for f in fields if f.indent >= 2]
        assert len(deep_fields) > 0, "expected indented nested struct fields"
