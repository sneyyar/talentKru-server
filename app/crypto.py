import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _get_key() -> bytes:
    """Derive a 32-byte AES key from ENCRYPTION_KEY."""
    raw = settings.ENCRYPTION_KEY.encode()
    return hashlib.sha256(raw).digest()


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field using AES-256-GCM. Returns base64-encoded ciphertext.
    
    Args:
        plaintext: The string to encrypt
        
    Returns:
        Base64-encoded string containing nonce + ciphertext
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_field(encoded: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext.
    
    Args:
        encoded: Base64-encoded string containing nonce + ciphertext
        
    Returns:
        The decrypted plaintext string
        
    Raises:
        cryptography.hazmat.primitives.ciphers.aead.InvalidTag: If authentication fails
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encoded)
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def hash_email(email: str) -> str:
    """Compute SHA-256 hash of lowercase email for uniqueness enforcement.
    
    Args:
        email: The email address to hash
        
    Returns:
        Hex-encoded SHA-256 hash of the lowercase email
    """
    return hashlib.sha256(email.lower().encode()).hexdigest()
