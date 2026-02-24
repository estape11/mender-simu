"""Cryptographic utilities for RSA key generation and signing."""

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from typing import Tuple
import base64


def generate_rsa_keypair(key_size: int = 3072) -> Tuple[str, str]:
    """
    Generate an RSA key pair for device authentication.

    Args:
        key_size: RSA key size in bits (default 3072 for Mender compatibility)

    Returns:
        Tuple of (private_key_pem, public_key_pem) as strings
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return private_pem, public_pem


def sign_data(private_key_pem: str, data: bytes) -> str:
    """
    Sign data using RSA private key with SHA256.

    Args:
        private_key_pem: PEM-encoded private key
        data: Data to sign

    Returns:
        Base64-encoded signature
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )

    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode('utf-8')


def verify_signature(public_key_pem: str, data: bytes, signature_b64: str) -> bool:
    """
    Verify a signature using RSA public key.

    Args:
        public_key_pem: PEM-encoded public key
        data: Original data that was signed
        signature_b64: Base64-encoded signature

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        signature = base64.b64decode(signature_b64)

        public_key.verify(
            signature,
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False
