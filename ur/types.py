from dataclasses import dataclass


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
