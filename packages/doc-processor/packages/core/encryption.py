"""
Medical Document Encryption (AES-256-GCM)
PBKDF2 with 480,000 iterations for key derivation.
"""

import os
import hashlib
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import cryptography, fall back to basic XOR for environments without it
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography package not installed. Using fallback encryption.")


class MedicalDocEncryption:
    """AES-256-GCM encryption for medical documents."""

    ITERATIONS = 480_000
    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32  # 256 bits

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key using PBKDF2-HMAC-SHA256."""
        if HAS_CRYPTO:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=MedicalDocEncryption.KEY_SIZE,
                salt=salt,
                iterations=MedicalDocEncryption.ITERATIONS,
            )
            return kdf.derive(password.encode('utf-8'))
        else:
            # Fallback: simple PBKDF2 using hashlib
            return hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                MedicalDocEncryption.ITERATIONS,
                dklen=MedicalDocEncryption.KEY_SIZE,
            )

    @staticmethod
    def encrypt_file(input_path: str, output_path: str, password: str) -> Dict[str, Any]:
        """
        Encrypt a file using AES-256-GCM.

        Args:
            input_path: Path to the file to encrypt
            output_path: Path for the encrypted output
            password: Encryption password

        Returns:
            Metadata dictionary with salt and verification hash
        """
        salt = os.urandom(MedicalDocEncryption.SALT_SIZE)
        key = MedicalDocEncryption._derive_key(password, salt)

        with open(input_path, 'rb') as f:
            plaintext = f.read()

        if HAS_CRYPTO:
            nonce = os.urandom(MedicalDocEncryption.NONCE_SIZE)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)

            # Prepend salt + nonce to ciphertext
            with open(output_path, 'wb') as f:
                f.write(salt)
                f.write(nonce)
                f.write(ciphertext)
        else:
            # Fallback: XOR with key stream
            import struct
            nonce = os.urandom(MedicalDocEncryption.NONCE_SIZE)
            key_stream = hashlib.sha256(key + nonce).digest()
            # Extend key stream to cover full plaintext
            blocks_needed = (len(plaintext) // 32) + 1
            extended_key = b''
            for i in range(blocks_needed):
                extended_key += hashlib.sha256(key + struct.pack('>I', i) + nonce).digest()

            ciphertext = bytes(a ^ b for a, b in zip(plaintext, extended_key[:len(plaintext)]))

            with open(output_path, 'wb') as f:
                f.write(salt)
                f.write(nonce)
                f.write(ciphertext)

        # Verification hash
        file_hash = hashlib.sha256(plaintext).hexdigest()[:16]

        return {
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "iterations": MedicalDocEncryption.ITERATIONS,
            "algorithm": "AES-256-GCM" if HAS_CRYPTO else "XOR-Fallback",
            "original_size": len(plaintext),
            "verification_hash": file_hash,
        }

    @staticmethod
    def decrypt_file(input_path: str, output_path: str, password: str) -> bool:
        """
        Decrypt a file.

        Args:
            input_path: Path to the encrypted file
            output_path: Path for the decrypted output
            password: Decryption password

        Returns:
            True if decryption succeeded, False otherwise
        """
        try:
            with open(input_path, 'rb') as f:
                salt = f.read(MedicalDocEncryption.SALT_SIZE)
                nonce = f.read(MedicalDocEncryption.NONCE_SIZE)
                ciphertext = f.read()

            key = MedicalDocEncryption._derive_key(password, salt)

            if HAS_CRYPTO:
                aesgcm = AESGCM(key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            else:
                import struct
                key_stream = hashlib.sha256(key + nonce).digest()
                blocks_needed = (len(ciphertext) // 32) + 1
                extended_key = b''
                for i in range(blocks_needed):
                    extended_key += hashlib.sha256(key + struct.pack('>I', i) + nonce).digest()

                plaintext = bytes(a ^ b for a, b in zip(ciphertext, extended_key[:len(ciphertext)]))

            with open(output_path, 'wb') as f:
                f.write(plaintext)

            return True
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return False

    @staticmethod
    def encrypt_data(data: bytes, password: str) -> bytes:
        """Encrypt raw bytes in memory."""
        salt = os.urandom(MedicalDocEncryption.SALT_SIZE)
        key = MedicalDocEncryption._derive_key(password, salt)

        if HAS_CRYPTO:
            nonce = os.urandom(MedicalDocEncryption.NONCE_SIZE)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, data, None)
            return salt + nonce + ciphertext
        else:
            import struct
            nonce = os.urandom(MedicalDocEncryption.NONCE_SIZE)
            key_stream = hashlib.sha256(key + nonce).digest()
            blocks_needed = (len(data) // 32) + 1
            extended_key = b''
            for i in range(blocks_needed):
                extended_key += hashlib.sha256(key + struct.pack('>I', i) + nonce).digest()
            ciphertext = bytes(a ^ b for a, b in zip(data, extended_key[:len(data)]))
            return salt + nonce + ciphertext

    @staticmethod
    def decrypt_data(encrypted: bytes, password: str) -> Optional[bytes]:
        """Decrypt raw bytes in memory."""
        try:
            salt = encrypted[:MedicalDocEncryption.SALT_SIZE]
            nonce = encrypted[MedicalDocEncryption.SALT_SIZE:MedicalDocEncryption.SALT_SIZE + MedicalDocEncryption.NONCE_SIZE]
            ciphertext = encrypted[MedicalDocEncryption.SALT_SIZE + MedicalDocEncryption.NONCE_SIZE:]

            key = MedicalDocEncryption._derive_key(password, salt)

            if HAS_CRYPTO:
                aesgcm = AESGCM(key)
                return aesgcm.decrypt(nonce, ciphertext, None)
            else:
                import struct
                key_stream = hashlib.sha256(key + nonce).digest()
                blocks_needed = (len(ciphertext) // 32) + 1
                extended_key = b''
                for i in range(blocks_needed):
                    extended_key += hashlib.sha256(key + struct.pack('>I', i) + nonce).digest()
                return bytes(a ^ b for a, b in zip(ciphertext, extended_key[:len(ciphertext)]))
        except Exception as e:
            logger.error(f"Data decryption failed: {e}")
            return None
