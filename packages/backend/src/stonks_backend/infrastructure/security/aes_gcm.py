"""AES-256-GCM encryption/decryption — application-level data encryption.

- AES-256-GCM avec nonce aléatoire 96 bits (12 octets)
- Tag d'authentification 128 bits (16 octets)
- La clé maîtresse est récupérée depuis Vault (ou .env en dev)
- Format de sortie : base64(nonce || ciphertext || tag)
"""

from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AESCipher:
    """AES-256-GCM encrypt/decrypt with key from Vault.

    Usage:
        cipher = AESCipher(key_bytes_32)
        encrypted = cipher.encrypt(b"hello world")
        decrypted = cipher.decrypt(encrypted)  # b"hello world"
    """

    NONCE_LENGTH: int = 12  # 96 bits
    TAG_LENGTH: int = 16    # 128 bits (implied by AESGCM)

    def __init__(self, key: bytes | str) -> None:
        """Initialize with a 32-byte AES-256 key.

        Args:
            key: 32 bytes of key material (binary or base64-encoded string).
        """
        if isinstance(key, str):
            key = base64.b64decode(key)
        if len(key) != 32:
            raise ValueError(f"AES-256 key must be exactly 32 bytes, got {len(key)}")
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> str:
        """Encrypt plaintext, returning base64(nonce || ciphertext || tag)."""
        nonce = secrets.token_bytes(self.NONCE_LENGTH)
        # AESGCM.encrypt returns ciphertext || tag
        ciphertext_with_tag = self._aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext_with_tag).decode("ascii")

    def decrypt(self, encrypted: str) -> bytes:
        """Decrypt base64(nonce || ciphertext || tag), returning plaintext.

        Raises:
            DecryptionError: if the ciphertext was tampered with or the key is wrong.
        """
        raw = base64.b64decode(encrypted)
        if len(raw) < self.NONCE_LENGTH + self.TAG_LENGTH:
            raise DecryptionError("Ciphertext too short")

        nonce = raw[: self.NONCE_LENGTH]
        ciphertext_with_tag = raw[self.NONCE_LENGTH :]

        try:
            return self._aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        except Exception as exc:
            raise DecryptionError(f"Decryption failed (tampered or wrong key): {exc}") from exc

    def encrypt_string(self, plaintext: str) -> str:
        """Encrypt a string, returning base64-encoded ciphertext."""
        return self.encrypt(plaintext.encode("utf-8"))

    def decrypt_string(self, encrypted: str) -> str:
        """Decrypt and decode as UTF-8 string."""
        return self.decrypt(encrypted).decode("utf-8")


class DecryptionError(Exception):
    """Raised when decryption fails (tampering, wrong key)."""


def create_aes_cipher(key: bytes | str) -> AESCipher:
    """Factory for AESCipher. Validates key length."""
    return AESCipher(key)
