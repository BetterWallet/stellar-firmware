"""
Tests for state/machine.py — inject synthetic events, assert state transitions.

All queues are mocked with asyncio.Queue. No Pi hardware required.
"""
import asyncio
import pytest
from urllib.parse import quote

from stellar_sdk import Account, Asset, Network, TransactionBuilder

from state.states import ButtonEvent, PINEvent, RenderEvent, State


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _drain_renders(q: asyncio.Queue) -> list[RenderEvent]:
    renders = []
    while not q.empty():
        renders.append(q.get_nowait())
    return renders


def _make_xlm_sign_request(wallet, signer_pubkey: str, network_passphrase: str, sep7_pubkey: str | None = None):
    from ur.types import XlmSignRequest

    src = Account(account=wallet.xlm_address, sequence=42)
    tx = (
        TransactionBuilder(
            source_account=src,
            network_passphrase=network_passphrase,
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
        f"&network_passphrase={quote(network_passphrase, safe='')}"
    )
    if sep7_pubkey:
        uri += f"&pubkey={quote(sep7_pubkey, safe='')}"

    return XlmSignRequest(
        request_id="req-test-1",
        signer_pubkey=signer_pubkey,
        network_passphrase=network_passphrase,
        sep7_uri=uri,
        kind="tx",
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
        sign_request = object()

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
        sign_request = object()

        state, new_decoder, req = await _handle_await_confirm(event_queue, decoder, sign_request)
        assert state == State.IDLE
        assert req is None

    @pytest.mark.asyncio
    async def test_handle_parsed_rejects_unknown_stellar_signer(self):
        from state.machine import _handle_parsed
        from wallet import Wallet

        wallet = Wallet("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
        req = _make_xlm_sign_request(
            wallet,
            signer_pubkey="GAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
        )
        with pytest.raises(ValueError, match="does not match any local Stellar account"):
            await _handle_parsed(wallet, req, asyncio.Queue())

    @pytest.mark.asyncio
    async def test_handle_parsed_rejects_network_mismatch(self):
        from state.machine import _handle_parsed
        from wallet import Wallet

        wallet = Wallet("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
        req = _make_xlm_sign_request(
            wallet,
            signer_pubkey=wallet.xlm_address,
            network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
        )
        req.network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
        with pytest.raises(ValueError, match="network passphrase mismatch"):
            await _handle_parsed(wallet, req, asyncio.Queue())

    @pytest.mark.asyncio
    async def test_handle_parsed_rejects_sep7_pubkey_mismatch(self):
        from state.machine import _handle_parsed
        from wallet import Wallet

        wallet = Wallet("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
        req = _make_xlm_sign_request(
            wallet,
            signer_pubkey=wallet.xlm_address,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
            sep7_pubkey="GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H",
        )
        with pytest.raises(ValueError, match="SEP-7 pubkey does not match"):
            await _handle_parsed(wallet, req, asyncio.Queue())

    def test_load_or_create_device_metadata_recovers_from_bad_json(self, tmp_path, monkeypatch):
        from state import machine

        bad_metadata = tmp_path / "device.json"
        bad_metadata.write_text("{not-valid-json")
        monkeypatch.setattr(machine, "DEVICE_METADATA_PATH", str(bad_metadata))

        metadata = machine._load_or_create_device_metadata()
        assert metadata["id"]
        assert metadata["label"]

    @pytest.mark.asyncio
    async def test_handle_show_import_emits_bw_stellar_accounts_qr(self):
        from state.machine import _handle_show_import
        from wallet import Wallet

        wallet = Wallet("abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about")
        event_queue = asyncio.Queue()
        render_queue = asyncio.Queue()
        await event_queue.put(ButtonEvent.CONFIRM)

        next_state = await _handle_show_import(wallet, event_queue, render_queue)
        assert next_state == State.IDLE

        renders = await _drain_renders(render_queue)
        result = next(r for r in renders if r.screen == "result")
        assert result.data["qr_frames"][0].startswith("ur:bw-stellar-accounts")


# ---------------------------------------------------------------------------
# Integration: full sign flow (mocked wallet)
# ---------------------------------------------------------------------------

class TestSignFlow:
    @pytest.mark.asyncio
    async def test_xlm_signing_produces_result_render(self):
        """A SEP-7 URI must drive _handle_signing through to a result QR."""
        from state.machine import _handle_signing
        from wallet import Wallet

        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        wallet = Wallet(mnemonic)
        sign_request = _make_xlm_sign_request(
            wallet,
            signer_pubkey=wallet.xlm_address,
            network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
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
