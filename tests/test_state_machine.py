"""
Tests for state/machine.py — inject synthetic events, assert state transitions.

All queues are mocked with asyncio.Queue. No Pi hardware required.
"""
import asyncio
import json
import pytest

from state.states import ButtonEvent, PINEvent, RenderEvent, State


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _drain_renders(q: asyncio.Queue) -> list[RenderEvent]:
    renders = []
    while not q.empty():
        renders.append(q.get_nowait())
    return renders


def _make_sign_request(data_type: int = 3, sign_data: bytes = b"test"):
    """Build a minimal EthSignRequest for testing."""
    from ur.types import EthSignRequest
    return EthSignRequest(
        request_id=b"\xab" * 16,
        sign_data=sign_data,
        data_type=data_type,
        chain_id=1,
        derivation_path="44'/60'/0'/0/0",
        address=None,
    )


# ---------------------------------------------------------------------------
# Unit tests for individual handlers (import directly)
# ---------------------------------------------------------------------------

class TestHandlers:
    @pytest.mark.asyncio
    async def test_handle_await_confirm_confirm(self):
        from state.machine import _handle_await_confirm
        from ur.decoder import URDecoder

        event_queue = asyncio.Queue()
        await event_queue.put(ButtonEvent.CONFIRM)
        decoder = URDecoder()
        sign_request = _make_sign_request()

        state, new_decoder, req = await _handle_await_confirm(event_queue, decoder, sign_request)
        assert state == State.SIGNING
        assert req is sign_request

    @pytest.mark.asyncio
    async def test_handle_await_confirm_reject(self):
        from state.machine import _handle_await_confirm
        from ur.decoder import URDecoder

        event_queue = asyncio.Queue()
        await event_queue.put(ButtonEvent.REJECT)
        decoder = URDecoder()
        sign_request = _make_sign_request()

        state, new_decoder, req = await _handle_await_confirm(event_queue, decoder, sign_request)
        assert state == State.IDLE
        assert req is None

    @pytest.mark.asyncio
    async def test_format_eth_fields_smoke(self):
        from wallet import eth as eth_mod
        req = _make_sign_request(data_type=3, sign_data=b"hello")
        # data_type 3 falls into the rlp.decode branch and triggers fallback;
        # the fallback path always yields a hex dump + path row.
        fields = eth_mod.format_fields(req)
        assert isinstance(fields, list)
        assert any(f.label == "Path" for f in fields)

    @pytest.mark.asyncio
    async def test_handle_parsed_personal_sign(self):
        from state.machine import _handle_parsed
        from wallet import Wallet

        render_queue = asyncio.Queue()
        req = _make_sign_request(data_type=3, sign_data=b"test message")
        state = await _handle_parsed(Wallet("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"), req, render_queue)
        assert state == State.AWAIT_CONFIRM
        renders = await _drain_renders(render_queue)
        assert any(r.screen == "confirm" for r in renders)

    @pytest.mark.asyncio
    async def test_handle_parsed_typed_data(self):
        from state.machine import _handle_parsed
        from wallet import Wallet

        render_queue = asyncio.Queue()
        typed_data = {
            "domain": {"name": "Test", "version": "1", "chainId": 1},
            "types": {"Msg": [{"name": "x", "type": "string"}]},
            "primaryType": "Msg",
            "message": {"x": "hello"},
        }
        req = _make_sign_request(
            data_type=2,
            sign_data=json.dumps(typed_data).encode(),
        )
        state = await _handle_parsed(
            Wallet("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"),
            req,
            render_queue,
        )
        assert state == State.AWAIT_CONFIRM


# ---------------------------------------------------------------------------
# Integration: full sign flow (mocked wallet)
# ---------------------------------------------------------------------------

class TestSignFlow:
    @pytest.mark.asyncio
    async def test_eth_signing_produces_result_render(self, monkeypatch):
        """_handle_signing must produce a 'signing' then 'result' RenderEvent for ETH."""
        from state.machine import _handle_signing
        from wallet import keygen, Wallet

        wallet = Wallet(keygen.generate())

        render_queue = asyncio.Queue()
        sign_request = _make_sign_request(data_type=3, sign_data=b"sign me")

        state, _decoder, req = await _handle_signing(wallet, sign_request, render_queue)
        assert state == State.DISPLAY_RESULT
        assert req is None

        renders = await _drain_renders(render_queue)
        screens = [r.screen for r in renders]
        assert "signing" in screens
        assert "result" in screens

        result_event = next(r for r in renders if r.screen == "result")
        assert isinstance(result_event.data["qr_frames"], list)
        assert len(result_event.data["qr_frames"]) >= 1

    @pytest.mark.asyncio
    async def test_xlm_signing_produces_result_render(self):
        """A SEP-7 URI must drive _handle_signing through to a result QR."""
        from urllib.parse import quote
        from stellar_sdk import Account, Asset, Network, TransactionBuilder

        from state.machine import _handle_signing
        from wallet import Wallet
        from ur.types import XlmSignRequest

        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        wallet = Wallet(mnemonic)

        # Build a real testnet payment XDR
        src = Account(account=wallet.xlm_address, sequence=42)
        tx = (
            TransactionBuilder(
                source_account=src,
                network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .append_payment_op(
                destination="GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H",
                asset=Asset.native(),
                amount="1.0",
            )
            .set_timeout(30)
            .build()
        )
        uri = (
            f"web+stellar:tx"
            f"?xdr={quote(tx.to_xdr(), safe='')}"
            f"&network_passphrase={quote(Network.TESTNET_NETWORK_PASSPHRASE, safe='')}"
        )
        sign_request = XlmSignRequest(
            request_id="req-test-1",
            signer_pubkey=wallet.xlm_address,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            sep7_uri=uri,
            kind="tx",
        )

        render_queue = asyncio.Queue()
        state, _decoder, req = await _handle_signing(wallet, sign_request, render_queue)
        assert state == State.DISPLAY_RESULT
        assert req is None

        renders = await _drain_renders(render_queue)
        screens = [r.screen for r in renders]
        assert "signing" in screens and "result" in screens
        result = next(r for r in renders if r.screen == "result")
        assert len(result.data["qr_frames"]) >= 1
        # XLM result is a UR fragment, not raw XDR
        assert result.data["qr_frames"][0].startswith("ur:bw-stellar-signature")
