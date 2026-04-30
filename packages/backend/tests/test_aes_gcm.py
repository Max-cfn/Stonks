"""Tests for AES-256-GCM encryption."""
import base64

import pytest

from stonks_backend.infrastructure.security.aes_gcm import (
    AESCipher,
    DecryptionError,
    create_aes_cipher,
)

# Exact 32-byte keys
_KEY_32 = b"0123456789abcdef0123456789abcdef"  # 32 bytes exactly
_KEY2_32 = b"zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"  # 32 bytes exactly


class TestAESCipher:
    """Round-trip and tampering tests."""

    @pytest.fixture
    def key(self) -> bytes:
        return _KEY_32

    @pytest.fixture
    def cipher(self, key: bytes) -> AESCipher:
        return AESCipher(key)

    def test_key_from_base64(self) -> None:
        """Accept a base64-encoded key."""
        b64_key = base64.b64encode(_KEY_32).decode()
        cipher = AESCipher(b64_key)
        enc = cipher.encrypt(b"test")
        assert cipher.decrypt(enc) == b"test"

    def test_key_too_short(self) -> None:
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            AESCipher(b"short")

    def test_key_too_long(self) -> None:
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            AESCipher(b"x" * 33)

    def test_encrypt_decrypt_bytes(self, cipher: AESCipher) -> None:
        plaintext = b"Hello, Stonks! This is sensitive data."
        encrypted = cipher.encrypt(plaintext)
        assert encrypted != plaintext
        assert cipher.decrypt(encrypted) == plaintext

    def test_encrypt_decrypt_string(self, cipher: AESCipher) -> None:
        plain = "Hello, Stonks with Unicode: emoji rocket"
        enc = cipher.encrypt_string(plain)
        assert enc != plain
        assert cipher.decrypt_string(enc) == plain

    def test_different_nonces_produce_different_ciphertexts(self, cipher: AESCipher) -> None:
        plain = b"same data"
        enc1 = cipher.encrypt(plain)
        enc2 = cipher.encrypt(plain)
        assert enc1 != enc2, "Same plaintext should produce different ciphertexts"

    def test_tampered_ciphertext_raises(self, cipher: AESCipher) -> None:
        encrypted = cipher.encrypt(b"sensitive stuff")
        raw = bytearray(base64.b64decode(encrypted))

        # Tamper with the ciphertext (after nonce)
        raw[15] ^= 0xFF
        tampered = base64.b64encode(raw).decode()

        with pytest.raises(DecryptionError, match="tampered"):
            cipher.decrypt(tampered)

    def test_tampered_nonce_raises(self, cipher: AESCipher) -> None:
        encrypted = cipher.encrypt(b"sensitive stuff")
        raw = bytearray(base64.b64decode(encrypted))

        # Tamper with nonce
        raw[0] ^= 0xFF
        tampered = base64.b64encode(raw).decode()

        with pytest.raises(DecryptionError, match="tampered"):
            cipher.decrypt(tampered)

    def test_wrong_key_fails(self) -> None:
        c1 = AESCipher(_KEY_32)
        c2 = AESCipher(_KEY2_32)

        enc = c1.encrypt(b"hello")
        with pytest.raises(DecryptionError, match="tampered"):
            c2.decrypt(enc)

    def test_empty_plaintext(self, cipher: AESCipher) -> None:
        """Empty payload should work."""
        enc = cipher.encrypt(b"")
        assert cipher.decrypt(enc) == b""

    def test_large_plaintext(self, cipher: AESCipher) -> None:
        """1 MB of data should encrypt/decrypt correctly."""
        plain = b"x" * (1024 * 1024)
        enc = cipher.encrypt(plain)
        assert cipher.decrypt(enc) == plain

    def test_ciphertext_too_short(self, cipher: AESCipher) -> None:
        with pytest.raises(DecryptionError, match="too short"):
            cipher.decrypt(base64.b64encode(b"short").decode())

    def test_create_aes_cipher_factory(self) -> None:
        cipher = create_aes_cipher(_KEY_32)
        assert isinstance(cipher, AESCipher)
