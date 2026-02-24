"""Tests for cryptographic utilities."""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mender_simulator.utils.crypto import (
    generate_rsa_keypair,
    sign_data,
    verify_signature
)


class TestRSAKeyGeneration:
    """Tests for RSA key pair generation."""

    def test_generate_keypair_returns_tuple(self):
        """Test that generate_rsa_keypair returns a tuple."""
        result = generate_rsa_keypair()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generate_keypair_returns_pem_strings(self):
        """Test that keys are in PEM format."""
        private_key, public_key = generate_rsa_keypair()

        assert isinstance(private_key, str)
        assert isinstance(public_key, str)
        assert "-----BEGIN PRIVATE KEY-----" in private_key
        assert "-----END PRIVATE KEY-----" in private_key
        assert "-----BEGIN PUBLIC KEY-----" in public_key
        assert "-----END PUBLIC KEY-----" in public_key

    def test_generate_keypair_unique(self):
        """Test that each call generates unique keys."""
        key1 = generate_rsa_keypair()
        key2 = generate_rsa_keypair()

        assert key1[0] != key2[0]  # Private keys different
        assert key1[1] != key2[1]  # Public keys different

    def test_generate_keypair_custom_size(self):
        """Test key generation with custom size."""
        private_key, public_key = generate_rsa_keypair(key_size=2048)

        assert "-----BEGIN PRIVATE KEY-----" in private_key
        assert "-----BEGIN PUBLIC KEY-----" in public_key


class TestSignAndVerify:
    """Tests for signing and verification."""

    def test_sign_data_returns_base64(self):
        """Test that sign_data returns base64 encoded signature."""
        private_key, _ = generate_rsa_keypair()
        data = b"test data to sign"

        signature = sign_data(private_key, data)

        assert isinstance(signature, str)
        # Base64 characters only
        import base64
        try:
            base64.b64decode(signature)
        except Exception:
            pytest.fail("Signature is not valid base64")

    def test_verify_valid_signature(self):
        """Test verification of valid signature."""
        private_key, public_key = generate_rsa_keypair()
        data = b"test data to sign"

        signature = sign_data(private_key, data)
        is_valid = verify_signature(public_key, data, signature)

        assert is_valid is True

    def test_verify_invalid_signature(self):
        """Test verification fails with wrong data."""
        private_key, public_key = generate_rsa_keypair()
        data = b"test data to sign"
        wrong_data = b"different data"

        signature = sign_data(private_key, data)
        is_valid = verify_signature(public_key, wrong_data, signature)

        assert is_valid is False

    def test_verify_wrong_key(self):
        """Test verification fails with wrong public key."""
        private_key1, _ = generate_rsa_keypair()
        _, public_key2 = generate_rsa_keypair()
        data = b"test data to sign"

        signature = sign_data(private_key1, data)
        is_valid = verify_signature(public_key2, data, signature)

        assert is_valid is False

    def test_sign_empty_data(self):
        """Test signing empty data."""
        private_key, public_key = generate_rsa_keypair()
        data = b""

        signature = sign_data(private_key, data)
        is_valid = verify_signature(public_key, data, signature)

        assert is_valid is True

    def test_sign_large_data(self):
        """Test signing large data."""
        private_key, public_key = generate_rsa_keypair()
        data = b"x" * 10000

        signature = sign_data(private_key, data)
        is_valid = verify_signature(public_key, data, signature)

        assert is_valid is True
