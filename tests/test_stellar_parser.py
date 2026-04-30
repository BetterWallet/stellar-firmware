"""
Stellar XDR → DisplayField parser tests.

Builds known transaction shapes and asserts the parser yields the expected
human-readable rows.
"""
from stellar_sdk import Account, Asset, Network, TransactionBuilder

from stellar import parser as xlm_parser


_TEST_PUBLIC = "GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX"
_DEST = "GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H"
_TESTNET = Network.TESTNET_NETWORK_PASSPHRASE


def _payment_xdr(amount: str = "42.5", memo: str = "test") -> str:
    src = Account(account=_TEST_PUBLIC, sequence=12345)
    tx = (
        TransactionBuilder(source_account=src, network_passphrase=_TESTNET, base_fee=100)
        .append_payment_op(destination=_DEST, asset=Asset.native(), amount=amount)
        .add_text_memo(memo)
        .set_timeout(30)
        .build()
    )
    return tx.to_xdr()


def _fields_to_dict(fields):
    return {f.label: f.value for f in fields}


class TestParser:
    def test_parses_header(self):
        fields = xlm_parser.parse(_payment_xdr(), _TESTNET)
        d = _fields_to_dict(fields)
        assert d["Chain"] == "Stellar"
        assert d["Network"] == "testnet"
        assert d["Source"].startswith("GB3JDW") and d["Source"].endswith("QBYX")
        assert d["Sequence"] == "12346"   # build() increments by 1
        assert d["Fee"] == "100 stroops"
        assert d["Operations"] == "1"

    def test_parses_payment_op(self):
        # stellar-sdk canonicalizes "100.0" -> "100"; just check the prefix.
        fields = xlm_parser.parse(_payment_xdr(amount="100.5"), _TESTNET)
        d = _fields_to_dict(fields)
        # Op header
        assert d["Op 1"] == "Payment"
        # Op rows
        assert d["To"].startswith("GBRPYH") and d["To"].endswith("X2H")
        assert d["Asset"] == "XLM"
        assert d["Amount"] == "100.5 XLM"

    def test_parses_text_memo(self):
        fields = xlm_parser.parse(_payment_xdr(memo="hello"), _TESTNET)
        d = _fields_to_dict(fields)
        assert d.get("Memo") == "text: hello"

    def test_mainnet_label(self):
        src = Account(account=_TEST_PUBLIC, sequence=1)
        tx = (
            TransactionBuilder(
                source_account=src,
                network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .append_payment_op(destination=_DEST, asset=Asset.native(), amount="1")
            .set_timeout(30)
            .build()
        )
        fields = xlm_parser.parse(tx.to_xdr(), Network.PUBLIC_NETWORK_PASSPHRASE)
        d = _fields_to_dict(fields)
        assert d["Network"] == "mainnet"
