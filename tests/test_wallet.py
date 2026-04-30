"""
Tests for wallet/ — keygen, keystore, derive, signer (eth + xlm), Wallet class.

All testable on dev machine. Uses a temp keystore file.
"""
import json
import pytest

from wallet import keygen
from wallet import keystore
from wallet import derive
from wallet import signer
from wallet import Wallet
from ur.types import EthSignRequest


# ---------------------------------------------------------------------------
# keygen
# ---------------------------------------------------------------------------

class TestKeygen:
    def test_generate_returns_12_words(self):
        phrase = keygen.generate()
        assert len(phrase.split()) == 12

    def test_validate_good_phrase(self):
        phrase = keygen.generate()
        assert keygen.validate(phrase) is True

    def test_validate_bad_phrase(self):
        assert keygen.validate("not a valid mnemonic phrase at all ever") is False

    def test_to_seed_length(self):
        phrase = keygen.generate()
        seed = keygen.to_seed(phrase)
        assert len(seed) == 64

    def test_to_seed_deterministic(self):
        phrase = keygen.generate()
        assert keygen.to_seed(phrase) == keygen.to_seed(phrase)

    def test_to_seed_rejects_bad_mnemonic(self):
        with pytest.raises(ValueError):
            keygen.to_seed("bad mnemonic")


# ---------------------------------------------------------------------------
# keystore — now stores the mnemonic, encrypted with AES-GCM
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _low_scrypt(monkeypatch):
    """macOS OpenSSL caps scrypt RAM. Patch to the minimum allowed for dev tests."""
    import wallet.keystore as _ks
    monkeypatch.setattr(_ks, "PIN_SCRYPT_N", 2**14)


class TestKeystore:
    def test_save_and_load_round_trip(self, tmp_path):
        phrase = keygen.generate()
        path = str(tmp_path / "keystore.json")
        pin = "123456"

        keystore.save(path, phrase, pin)
        assert keystore.exists(path)

        loaded = keystore.load(path, pin)
        assert loaded == phrase

    def test_round_trip_re_derives_same_addresses(self, tmp_path):
        """Saving + loading must preserve enough entropy to re-derive both chains."""
        phrase = keygen.generate()
        eth_before = derive.derive_eth_account(phrase).address
        xlm_before = derive.derive_xlm_keypair(phrase).public_key

        path = str(tmp_path / "keystore.json")
        keystore.save(path, phrase, "pin")
        loaded = keystore.load(path, "pin")

        assert derive.derive_eth_account(loaded).address == eth_before
        assert derive.derive_xlm_keypair(loaded).public_key == xlm_before

    def test_wrong_pin_raises(self, tmp_path):
        phrase = keygen.generate()
        path = str(tmp_path / "keystore.json")
        keystore.save(path, phrase, "correct-pin")
        with pytest.raises(ValueError):
            keystore.load(path, "wrong-pin")

    def test_keystore_blob_shape(self, tmp_path):
        """Verify the on-disk format is what we promise."""
        phrase = keygen.generate()
        path = str(tmp_path / "keystore.json")
        keystore.save(path, phrase, "pin")
        blob = json.loads(open(path).read())
        assert blob["version"] == 2
        assert blob["cipher"] == "aes-256-gcm"
        assert blob["kdf"] == "scrypt"
        assert len(bytes.fromhex(blob["nonce"])) == 12
        assert len(bytes.fromhex(blob["scrypt"]["salt"])) == 16

    def test_exists_false_for_missing_file(self, tmp_path):
        assert keystore.exists(str(tmp_path / "no-such-file.json")) is False


# ---------------------------------------------------------------------------
# Ethereum derivation (secp256k1 / BIP-32)
# ---------------------------------------------------------------------------

class TestDeriveEth:
    def test_derive_eth_account_has_address(self):
        phrase = keygen.generate()
        account = derive.derive_eth_account(phrase)
        assert account.address.startswith("0x")
        assert len(account.address) == 42

    def test_derive_eth_deterministic(self):
        phrase = keygen.generate()
        a1 = derive.derive_eth_account(phrase)
        a2 = derive.derive_eth_account(phrase)
        assert a1.address == a2.address

    def test_different_paths_different_addresses(self):
        phrase = keygen.generate()
        a0 = derive.derive_eth_account(phrase, "m/44'/60'/0'/0/0")
        a1 = derive.derive_eth_account(phrase, "m/44'/60'/0'/0/1")
        assert a0.address != a1.address

    def test_derive_eth_xpub_returns_bytes(self):
        phrase = keygen.generate()
        xpub = derive.derive_eth_xpub(phrase)
        assert len(xpub["key_data"]) == 33
        assert len(xpub["chain_code"]) == 32
        assert len(xpub["master_fingerprint"]) == 4
        assert len(xpub["parent_fingerprint"]) == 4
        assert xpub["depth"] == 3


# ---------------------------------------------------------------------------
# Stellar derivation (Ed25519 / SLIP-10)
# ---------------------------------------------------------------------------

# Standard BIP-39 test vector mnemonic
_TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
# Verified live against stellar-sdk 13.2.1 in the dev session.
_TEST_MNEMONIC_XLM_PUBLIC = "GB3JDWCQJCWMJ3IILWIGDTQJJC5567PGVEVXSCVPEQOTDN64VJBDQBYX"


class TestDeriveXlm:
    def test_derive_xlm_returns_g_address(self):
        kp = derive.derive_xlm_keypair(_TEST_MNEMONIC)
        assert kp.public_key.startswith("G")
        assert len(kp.public_key) == 56

    def test_xlm_test_vector(self):
        """SEP-5 default index-0 derivation must match the known address."""
        kp = derive.derive_xlm_keypair(_TEST_MNEMONIC)
        assert kp.public_key == _TEST_MNEMONIC_XLM_PUBLIC

    def test_xlm_index_changes_address(self):
        kp0 = derive.derive_xlm_keypair(_TEST_MNEMONIC, index=0)
        kp1 = derive.derive_xlm_keypair(_TEST_MNEMONIC, index=1)
        assert kp0.public_key != kp1.public_key


# ---------------------------------------------------------------------------
# eth signer (via the back-compat shim)
# ---------------------------------------------------------------------------

class TestEthSigner:
    def _account(self):
        return derive.derive_eth_account(keygen.generate())

    def test_personal_sign_returns_65_bytes(self):
        account = self._account()
        req = EthSignRequest(
            request_id=b"\x00" * 16,
            sign_data=b"Hello cold wallet",
            data_type=3, chain_id=1,
            derivation_path="44'/60'/0'/0/0", address=None,
        )
        sig = signer.sign(account, req)
        assert len(sig) == 65 and sig[64] in (0, 1)

    def test_typed_data_sign_returns_65_bytes(self):
        account = self._account()
        typed_data = {
            "domain": {"name": "Test", "version": "1", "chainId": 1},
            "types": {"Msg": [{"name": "content", "type": "string"}]},
            "primaryType": "Msg",
            "message": {"content": "hello"},
        }
        req = EthSignRequest(
            request_id=b"\x01" * 16,
            sign_data=json.dumps(typed_data).encode(),
            data_type=2, chain_id=1,
            derivation_path="44'/60'/0'/0/0", address=None,
        )
        sig = signer.sign(account, req)
        assert len(sig) == 65 and sig[64] in (0, 1)

    def test_personal_sign_verifiable(self):
        from eth_account import Account
        from eth_account.messages import encode_defunct

        account = self._account()
        message = b"test message for verification"
        req = EthSignRequest(
            request_id=b"\x02" * 16,
            sign_data=message, data_type=3, chain_id=1,
            derivation_path="44'/60'/0'/0/0", address=None,
        )
        sig_bytes = signer.sign(account, req)
        r = int.from_bytes(sig_bytes[:32], "big")
        s = int.from_bytes(sig_bytes[32:64], "big")
        v = sig_bytes[64]
        recovered = Account.recover_message(encode_defunct(message), vrs=(v, r, s))
        assert recovered.lower() == account.address.lower()

    def test_legacy_transaction(self):
        import rlp
        account = self._account()
        unsigned = rlp.encode([
            (0).to_bytes(0, "big"),
            (1_000_000_000).to_bytes(4, "big"),
            (21_000).to_bytes(2, "big"),
            bytes.fromhex("1111111111111111111111111111111111111111"),
            (123).to_bytes(1, "big"),
            b"",
        ])
        req = EthSignRequest(
            request_id=b"\x04" * 16,
            sign_data=unsigned, data_type=1, chain_id=1,
            derivation_path="44'/60'/0'/0/0", address=None,
        )
        sig = signer.sign(account, req)
        assert len(sig) == 65 and sig[64] in (0, 1)

    def test_unsupported_data_type_raises(self):
        account = self._account()
        req = EthSignRequest(
            request_id=b"\x03" * 16,
            sign_data=b"data", data_type=99, chain_id=1,
            derivation_path="44'/60'/0'/0/0", address=None,
        )
        with pytest.raises(ValueError):
            signer.sign(account, req)


# ---------------------------------------------------------------------------
# Wallet — multi-chain dispatcher
# ---------------------------------------------------------------------------

class TestWalletClass:
    def test_holds_mnemonic_and_exposes_addresses(self):
        w = Wallet(_TEST_MNEMONIC)
        assert w.eth_address.startswith("0x") and len(w.eth_address) == 42
        assert w.xlm_address == _TEST_MNEMONIC_XLM_PUBLIC

    def test_dispatches_eth_request(self):
        w = Wallet(_TEST_MNEMONIC)
        req = EthSignRequest(
            request_id=b"\x00" * 16,
            sign_data=b"hi", data_type=3, chain_id=1,
            derivation_path="44'/60'/0'/0/0", address=None,
        )
        sig = w.sign(req)
        assert isinstance(sig, bytes) and len(sig) == 65

    def test_unknown_request_type_raises(self):
        w = Wallet(_TEST_MNEMONIC)
        with pytest.raises(ValueError):
            w.sign(object())
