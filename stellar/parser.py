"""
Decode a Stellar TransactionEnvelope XDR into human-readable DisplayFields
for the confirm screen.

Walks each operation and emits rows. Stroops are converted to XLM
(divide by 10⁷) for the user-facing amount; raw stroops are shown for
the network fee since users care about exact fee values.
"""
from stellar_sdk import TransactionEnvelope
from stellar_sdk.operation import (
    Payment,
    CreateAccount,
    PathPaymentStrictReceive,
    PathPaymentStrictSend,
    ChangeTrust,
    ManageData,
    SetOptions,
)

from eip712.display import DisplayField


_STROOPS_PER_XLM = 10**7


def parse(xdr: str, network_passphrase: str) -> list[DisplayField]:
    """Parse a signed-or-unsigned envelope XDR and return DisplayFields."""
    envelope = TransactionEnvelope.from_xdr(xdr, network_passphrase)
    tx = envelope.transaction

    fields: list[DisplayField] = []

    # Header — always shown
    fields.append(DisplayField("Chain", "Stellar"))
    fields.append(DisplayField("Network", _short_network(network_passphrase)))
    fields.append(DisplayField("Source", _shorten(tx.source.account_id)))
    fields.append(DisplayField("Sequence", str(tx.sequence)))
    fields.append(DisplayField("Fee", f"{tx.fee} stroops"))
    fields.append(DisplayField("Operations", str(len(tx.operations))))

    for i, op in enumerate(tx.operations):
        prefix = f"Op {i + 1}"
        fields.append(DisplayField(prefix, _op_type(op), indent=0))
        for label, value in _op_rows(op):
            fields.append(DisplayField(label, value, indent=1))

    if tx.memo and not _is_no_memo(tx.memo):
        fields.append(DisplayField("Memo", _format_memo(tx.memo)))

    return fields


# ---------------------------------------------------------------------------
# Operation walkers
# ---------------------------------------------------------------------------

def _op_rows(op) -> list[tuple[str, str]]:
    if isinstance(op, Payment):
        return [
            ("To",     _shorten(op.destination.account_id)),
            ("Asset",  _format_asset(op.asset)),
            ("Amount", _format_amount(op.amount, op.asset)),
        ]
    if isinstance(op, CreateAccount):
        return [
            ("To",      _shorten(op.destination)),
            ("Starting Balance", f"{op.starting_balance} XLM"),
        ]
    if isinstance(op, ChangeTrust):
        return [
            ("Asset", _format_asset(op.asset)),
            ("Limit", str(op.limit) if op.limit is not None else "(max)"),
        ]
    if isinstance(op, ManageData):
        return [
            ("Name",  op.data_name),
            ("Value", _format_data_value(op.data_value)),
        ]
    if isinstance(op, SetOptions):
        rows = []
        if op.home_domain is not None:
            rows.append(("Home Domain", op.home_domain))
        if op.master_weight is not None:
            rows.append(("Master Weight", str(op.master_weight)))
        if op.signer is not None:
            rows.append(("Signer", str(op.signer)))
        if not rows:
            rows.append(("(no displayable options)", ""))
        return rows
    if isinstance(op, (PathPaymentStrictReceive, PathPaymentStrictSend)):
        return [
            ("To",            _shorten(op.destination.account_id)),
            ("Send Asset",    _format_asset(op.send_asset)),
            ("Receive Asset", _format_asset(op.dest_asset)),
        ]
    return [("(operation type not pretty-printed)", _op_type(op))]


def _op_type(op) -> str:
    return type(op).__name__


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_asset(asset) -> str:
    if asset.is_native():
        return "XLM"
    issuer_short = _shorten(asset.issuer) if asset.issuer else "?"
    return f"{asset.code}:{issuer_short}"


def _format_amount(amount, asset) -> str:
    """amount is already a string from stellar-sdk in human XLM units."""
    suffix = "XLM" if asset.is_native() else asset.code
    return f"{amount} {suffix}"


def _format_data_value(v) -> str:
    if v is None:
        return "(delete)"
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.hex()
    return str(v)


def _format_memo(memo) -> str:
    cls = type(memo).__name__
    if hasattr(memo, "memo_text") and memo.memo_text is not None:
        text = memo.memo_text
        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8")
            except UnicodeDecodeError:
                text = text.hex()
        return f"text: {text}"
    if hasattr(memo, "memo_id") and memo.memo_id is not None:
        return f"id: {memo.memo_id}"
    return cls


def _is_no_memo(memo) -> bool:
    return type(memo).__name__ == "NoneMemo"


def _shorten(g_address: str) -> str:
    """Display G-strkey as G…XYZA so it fits the 480-px screen."""
    if not g_address:
        return ""
    if len(g_address) <= 16:
        return g_address
    return f"{g_address[:6]}…{g_address[-6:]}"


def _short_network(passphrase: str) -> str:
    if "Public" in passphrase:
        return "mainnet"
    if "Test" in passphrase:
        return "testnet"
    return passphrase[:24]
