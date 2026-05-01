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
    """Stellar tx sign request from `ur:bw-stellar-sign-request`."""
    request_id: str
    signer_pubkey: str
    network_passphrase: str
    sep7_uri: str | None = None
    tx_xdr: str | None = None
    kind: str = "tx"


@dataclass
class XlmSignature:
    request_id: str
    signer_pubkey: str
    signed_xdr: str
    signatures: list[dict]


@dataclass
class XlmSignResult:
    signed_xdr: str
    signatures: list[bytes]


@dataclass
class BwStellarAccount:
    publicKey: str
    bipPath: str
    label: str | None = None


@dataclass
class BwStellarDevice:
    id: str
    label: str
    fwVersion: str | None = None


@dataclass
class BwStellarAccountsPayload:
    device: BwStellarDevice
    accounts: list[BwStellarAccount]
