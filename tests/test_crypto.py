"""
Property-based tests for PII encryption.

Feature: identity-and-access
Property 13: PII encryption round-trip
Validates: Requirements 7.1, 7.2
"""

import pytest
from hypothesis import given, settings, strategies as st

from app.crypto import encrypt_field, decrypt_field


class TestPIIEncryption:
    """Test suite for PII encryption functionality."""

    @given(plaintext=st.text(min_size=1, max_size=254))
    @settings(max_examples=20)
    def test_encryption_round_trip(self, plaintext: str):
        """
        Property 13: PII encryption round-trip
        
        For any plaintext string, encrypting and then decrypting should
        return the original plaintext.
        
        Validates: Requirements 7.1, 7.2
        """
        # Encrypt the plaintext
        encrypted = encrypt_field(plaintext)
        
        # Encrypted value should not equal plaintext (unless by extreme coincidence)
        assert encrypted != plaintext
        
        # Decrypt should return original plaintext
        decrypted = decrypt_field(encrypted)
        assert decrypted == plaintext

    @given(plaintext=st.text(min_size=1, max_size=100))
    @settings(max_examples=20)
    def test_encryption_produces_different_ciphertexts(self, plaintext: str):
        """
        For the same plaintext, encrypting twice should produce different
        ciphertexts due to random nonce generation.
        """
        encrypted1 = encrypt_field(plaintext)
        encrypted2 = encrypt_field(plaintext)
        
        # Different nonces should produce different ciphertexts
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same plaintext
        assert decrypt_field(encrypted1) == plaintext
        assert decrypt_field(encrypted2) == plaintext

    def test_encryption_with_special_characters(self):
        """Test encryption with special characters and unicode."""
        test_cases = [
            "test@example.com",
            "user+tag@domain.co.uk",
            "名前@example.jp",
            "Ñoño@example.es",
            "test!@#$%^&*()",
        ]
        
        for plaintext in test_cases:
            encrypted = encrypt_field(plaintext)
            decrypted = decrypt_field(encrypted)
            assert decrypted == plaintext

    def test_encryption_with_empty_string(self):
        """Empty strings can be encrypted (though not tested in property tests)."""
        # Empty strings are technically valid to encrypt, though the property
        # test uses min_size=1 to focus on non-empty strings
        encrypted = encrypt_field("")
        decrypted = decrypt_field(encrypted)
        assert decrypted == ""

    def test_decryption_with_invalid_ciphertext_fails(self):
        """Decryption with invalid ciphertext should raise an exception."""
        import base64
        
        # Create invalid base64 that's too short
        invalid_ciphertext = base64.b64encode(b"short").decode()
        
        with pytest.raises(Exception):
            decrypt_field(invalid_ciphertext)

    def test_decryption_with_tampered_ciphertext_fails(self):
        """Decryption with tampered ciphertext should fail authentication."""
        plaintext = "sensitive data"
        encrypted = encrypt_field(plaintext)
        
        # Tamper with the encrypted value
        import base64
        raw = base64.b64decode(encrypted)
        tampered = base64.b64encode(raw[:-1] + b"X").decode()
        
        with pytest.raises(Exception):
            decrypt_field(tampered)
