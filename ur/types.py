from dataclasses import dataclass


@dataclass
class EthSignRequest:
    request_id: bytes       # UUID bytes (16 bytes)
    sign_data: bytes        # RLP tx or EIP-712 encoded bytes
    data_type: int          # 1=legacy tx, 2=typed data, 3=personal sign, 4=typed transaction
    chain_id: int
    derivation_path: str    # e.g. "44'/60'/0'/0/0"
    address: str | None     # optional origin address for verification


@dataclass
class EthSignature:
    request_id: bytes
    signature: bytes        # 65 bytes r+s+v


@dataclass
class CryptoHDKey:
    key_data: bytes             # compressed public key (33 bytes)
    chain_code: bytes           # 32 bytes
    origin_path: str            # e.g. "44'/60'/0'/0/0"
    address: str                # checksummed Ethereum address
    master_fingerprint: bytes = b'\x00\x00\x00\x00'   # root key fingerprint (4 bytes)
    parent_fingerprint: bytes = b'\x00\x00\x00\x00'   # parent key fingerprint (4 bytes)


# ---------------------------------------------------------------------------
# Stellar (XLM)
# ---------------------------------------------------------------------------

@dataclass
class XlmSignRequest:
    """Stellar sign request.

    The transport carries a SEP-7 URI rather than a bare XDR — SEP-7 is the
    Stellar ecosystem's de-facto signing-request format, and packaging the
    XDR + network passphrase together avoids ambiguity at the air gap.
    """
    request_id: bytes       # 16-byte UUID; synthesized for bare-SEP-7 inputs
    sep7_uri: str           # web+stellar:tx?xdr=...&network_passphrase=...


@dataclass
class XlmSignature:
    request_id: bytes
    signed_envelope_xdr: str
