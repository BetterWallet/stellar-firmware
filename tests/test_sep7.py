"""SEP-7 URI parser tests."""
import pytest

from stellar import sep7


_SAMPLE_XDR = (
    "AAAAAgAAAAB2kdhQSKzE7QhdkGHOCUi7333mqSt5Cq8kHTG33KpCOAAAAGQAAAAA"
    "AAAwOgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAQAAAABi%2BB0L"
)


class TestSep7:
    def test_is_sep7_true(self):
        assert sep7.is_sep7("web+stellar:tx?xdr=foo") is True

    def test_is_sep7_false(self):
        assert sep7.is_sep7("https://example.com") is False
        assert sep7.is_sep7("web+ethereum:0x...") is False

    def test_parse_minimal_tx(self):
        uri = f"web+stellar:tx?xdr={_SAMPLE_XDR}"
        req = sep7.parse(uri)
        assert req.operation == "tx"
        assert req.xdr is not None
        assert "%2" not in req.xdr  # URL-decoded
        assert "Public" in req.network_passphrase  # default mainnet

    def test_parse_with_network_passphrase(self):
        uri = (
            "web+stellar:tx"
            f"?xdr={_SAMPLE_XDR}"
            "&network_passphrase=Test%20SDF%20Network%20%3B%20September%202015"
        )
        req = sep7.parse(uri)
        assert "Test" in req.network_passphrase
        assert ";" in req.network_passphrase

    def test_parse_with_callback_and_origin(self):
        uri = (
            "web+stellar:tx"
            f"?xdr={_SAMPLE_XDR}"
            "&callback=url%3Ahttps%3A%2F%2Fexample.com%2Fcb"
            "&origin_domain=example.com"
        )
        req = sep7.parse(uri)
        assert req.callback is not None
        assert req.origin_domain == "example.com"

    def test_parse_rejects_pay_operation(self):
        with pytest.raises(ValueError, match="not supported"):
            sep7.parse("web+stellar:pay?destination=GABC&amount=10")

    def test_parse_rejects_unknown_operation(self):
        with pytest.raises(ValueError, match="unsupported"):
            sep7.parse("web+stellar:bogus?foo=bar")

    def test_parse_rejects_wrong_scheme(self):
        with pytest.raises(ValueError, match="not a SEP-7"):
            sep7.parse("https://stellar.org")

    def test_parse_rejects_missing_xdr(self):
        with pytest.raises(ValueError, match="missing required"):
            sep7.parse("web+stellar:tx?foo=bar")
