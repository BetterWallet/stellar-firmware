"""
SEP-7 (web+stellar) URI parser.

Spec: https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0007.md

Supported operations:
  - tx       : sign an arbitrary transaction. We extract the XDR.
  - pay      : payment shortcut. We construct it would-be operationally,
               but the device's airgap path expects a fully-built XDR.
               Reject pay URIs at the boundary — the host must build the
               envelope and re-emit as ?tx URI.

URI shape:
  web+stellar:tx?xdr=<URL-encoded-XDR>&network_passphrase=<...>&callback=<...>

We do NOT chase the callback or verify the optional `signature` /
`origin_domain` fields — verification belongs to the air-gapped device's
own confirm screen, which shows the human-readable contents of the XDR.
"""
from dataclasses import dataclass
from urllib.parse import unquote, urlparse, parse_qs

from config import XLM_NETWORK_PASSPHRASE


_SCHEME = "web+stellar"


@dataclass
class Sep7Request:
    operation: str                # "tx" or "pay"
    xdr: str | None               # transaction envelope XDR (only for tx)
    network_passphrase: str       # defaults to mainnet if omitted
    callback: str | None          # SEP-7 'callback' param, if any
    origin_domain: str | None     # SEP-7 'origin_domain' param, if any
    req_id: str | None            # Better Wallet custom param
    pubkey: str | None            # Better Wallet custom param


def parse(uri: str) -> Sep7Request:
    """Parse a SEP-7 URI. Raises ValueError on malformed input."""
    if not uri.startswith(_SCHEME + ":"):
        raise ValueError(f"not a SEP-7 URI: scheme is not {_SCHEME!r}")

    # urllib doesn't handle non-standard schemes uniformly; do it manually.
    # Format after scheme: <operation>?<query>
    rest = uri[len(_SCHEME) + 1:]
    if "?" in rest:
        operation, raw_query = rest.split("?", 1)
    else:
        operation, raw_query = rest, ""

    if operation not in ("tx", "pay"):
        raise ValueError(f"unsupported SEP-7 operation: {operation!r}")

    if operation == "pay":
        # Air-gapped device cannot build the XDR itself; require a tx URI.
        raise ValueError(
            "SEP-7 'pay' URIs are not supported on the air-gapped path; "
            "the host must build the transaction envelope and emit as ?tx"
        )

    params = parse_qs(raw_query, keep_blank_values=False)

    xdr_list = params.get("xdr")
    if not xdr_list or not xdr_list[0]:
        raise ValueError("SEP-7 tx URI missing required 'xdr' parameter")
    xdr = unquote(xdr_list[0])

    network_passphrase = unquote(params["network_passphrase"][0]) \
        if "network_passphrase" in params else XLM_NETWORK_PASSPHRASE

    callback      = unquote(params["callback"][0])      if "callback"      in params else None
    origin_domain = unquote(params["origin_domain"][0]) if "origin_domain" in params else None
    req_id        = unquote(params["req_id"][0])        if "req_id"        in params else None
    pubkey        = unquote(params["pubkey"][0])        if "pubkey"        in params else None

    return Sep7Request(
        operation="tx",
        xdr=xdr,
        network_passphrase=network_passphrase,
        callback=callback,
        origin_domain=origin_domain,
        req_id=req_id,
        pubkey=pubkey,
    )


def is_sep7(s: str) -> bool:
    """Cheap prefix-check used by the QR-scan layer to detect bare URIs."""
    return s.startswith(_SCHEME + ":")
