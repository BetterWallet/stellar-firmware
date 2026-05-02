"""
Tests for wallet/ — keygen, keystore, derive, Wallet class.

All testable on dev machine. Uses a temp keystore file.
"""
import json
import pytest

from wallet import keygen
from wallet import keystore
from wallet import derive
from wallet import Wallet


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
        """Saving + loading must preserve enough entropy to re-derive Stellar keys."""
        phrase = keygen.generate()
        xlm_before = derive.derive_xlm_keypair(phrase).public_key

        path = str(tmp_path / "keystore.json")
        keystore.save(path, phrase, "pin")
        loaded = keystore.load(path, "pin")

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
# Wallet
# ---------------------------------------------------------------------------

class TestWalletClass:
    def test_holds_mnemonic_and_exposes_xlm_address(self):
        w = Wallet(_TEST_MNEMONIC)
        assert w.xlm_address == _TEST_MNEMONIC_XLM_PUBLIC

    def test_unknown_request_type_raises(self):
        w = Wallet(_TEST_MNEMONIC)
        with pytest.raises(ValueError):
            w.sign(object())
