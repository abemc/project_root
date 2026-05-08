"""Encryption Manager for data encryption/decryption operations."""

import os
import json
import hashlib
import hmac
from typing import Union, Tuple, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    RSA_2048 = "rsa_2048"


class EncryptionManager:
    """Manages encryption/decryption operations for data protection.
    
    Supports:
    - AES-256-GCM (authenticated encryption)
    - AES-256-CBC (symmetric encryption)
    - RSA-2048 (asymmetric encryption)
    - HMAC for data integrity verification
    - Key rotation
    - Encryption metadata tracking
    """

    def __init__(self, master_key: Optional[bytes] = None):
        """Initialize encryption manager.
        
        Args:
            master_key: Master key for encryption (defaults to generating new)
        """
        self.master_key = master_key or os.urandom(32)
        self.rsa_private_key: Optional[Any] = None
        self.rsa_public_key: Optional[Any] = None
        self.encryption_log: Dict[str, Any] = {}
        self.key_rotation_history: list = []
        self._backend = default_backend()

    def generate_rsa_keys(self, key_size: int = 2048) -> Tuple[bytes, bytes]:
        """Generate RSA key pair.
        
        Args:
            key_size: RSA key size in bits (default: 2048)
            
        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=self._backend
        )
        self.rsa_private_key = private_key
        self.rsa_public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_pem = self.rsa_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        self._log_encryption("rsa_key_generation", {
            "key_size": key_size,
            "timestamp": datetime.utcnow().isoformat()
        })

        return private_pem, public_pem

    def encrypt_aes_256_gcm(self, data: Union[str, bytes]) -> Dict[str, str]:
        """Encrypt data using AES-256-GCM.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Dict containing encrypted data, IV, and tag (all as hex strings)
        """
        if isinstance(data, str):
            data = data.encode()

        iv = os.urandom(12)
        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.GCM(iv),
            backend=self._backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()

        self._log_encryption("aes_256_gcm_encrypt", {
            "data_size": len(data),
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "ciphertext": ciphertext.hex(),
            "iv": iv.hex(),
            "tag": encryptor.tag.hex(),
            "algorithm": "aes_256_gcm"
        }

    def decrypt_aes_256_gcm(self, encrypted_data: Dict[str, str]) -> str:
        """Decrypt AES-256-GCM encrypted data.
        
        Args:
            encrypted_data: Dict with ciphertext, iv, and tag
            
        Returns:
            Decrypted data as string
        """
        ciphertext = bytes.fromhex(encrypted_data["ciphertext"])
        iv = bytes.fromhex(encrypted_data["iv"])
        tag = bytes.fromhex(encrypted_data["tag"])

        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.GCM(iv, tag),
            backend=self._backend
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        self._log_encryption("aes_256_gcm_decrypt", {
            "data_size": len(ciphertext),
            "timestamp": datetime.utcnow().isoformat()
        })

        return plaintext.decode()

    def encrypt_aes_256_cbc(self, data: Union[str, bytes]) -> Dict[str, str]:
        """Encrypt data using AES-256-CBC.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Dict containing encrypted data, IV, and HMAC
        """
        if isinstance(data, str):
            data = data.encode()

        iv = os.urandom(16)
        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.CBC(iv),
            backend=self._backend
        )
        encryptor = cipher.encryptor()

        # Add PKCS7 padding
        block_size = 16
        padding_length = block_size - (len(data) % block_size)
        padded_data = data + bytes([padding_length] * padding_length)

        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Generate HMAC for integrity
        hmac_obj = hmac.new(self.master_key, ciphertext, hashlib.sha256)

        self._log_encryption("aes_256_cbc_encrypt", {
            "data_size": len(data),
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "ciphertext": ciphertext.hex(),
            "iv": iv.hex(),
            "hmac": hmac_obj.hexdigest(),
            "algorithm": "aes_256_cbc"
        }

    def decrypt_aes_256_cbc(self, encrypted_data: Dict[str, str]) -> str:
        """Decrypt AES-256-CBC encrypted data.
        
        Args:
            encrypted_data: Dict with ciphertext, iv, and hmac
            
        Returns:
            Decrypted data as string
            
        Raises:
            ValueError: If HMAC verification fails
        """
        ciphertext = bytes.fromhex(encrypted_data["ciphertext"])
        iv = bytes.fromhex(encrypted_data["iv"])
        expected_hmac = encrypted_data["hmac"]

        # Verify HMAC
        hmac_obj = hmac.new(self.master_key, ciphertext, hashlib.sha256)
        if not hmac.compare_digest(hmac_obj.hexdigest(), expected_hmac):
            raise ValueError("HMAC verification failed - data may be corrupted")

        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.CBC(iv),
            backend=self._backend
        )
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove PKCS7 padding
        padding_length = padded_plaintext[-1]
        plaintext = padded_plaintext[:-padding_length]

        self._log_encryption("aes_256_cbc_decrypt", {
            "data_size": len(plaintext),
            "timestamp": datetime.utcnow().isoformat()
        })

        return plaintext.decode()

    def encrypt_rsa(self, data: Union[str, bytes]) -> Dict[str, str]:
        """Encrypt data using RSA-2048.
        
        Args:
            data: Data to encrypt (max ~190 bytes for 2048-bit key)
            
        Returns:
            Dict containing encrypted data as hex string
        """
        if not self.rsa_public_key:
            self.generate_rsa_keys()

        if isinstance(data, str):
            data = data.encode()

        if len(data) > 190:
            raise ValueError("Data too large for RSA encryption")

        ciphertext = self.rsa_public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        self._log_encryption("rsa_encrypt", {
            "data_size": len(data),
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "ciphertext": ciphertext.hex(),
            "algorithm": "rsa_2048"
        }

    def decrypt_rsa(self, encrypted_data: Dict[str, str]) -> str:
        """Decrypt RSA-2048 encrypted data.
        
        Args:
            encrypted_data: Dict with ciphertext
            
        Returns:
            Decrypted data as string
        """
        if not self.rsa_private_key:
            raise ValueError("RSA private key not initialized")

        ciphertext = bytes.fromhex(encrypted_data["ciphertext"])

        plaintext = self.rsa_private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        self._log_encryption("rsa_decrypt", {
            "data_size": len(plaintext),
            "timestamp": datetime.utcnow().isoformat()
        })

        return plaintext.decode()

    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Dict[str, str]:
        """Hash password using SHA-256 with salt.
        
        Args:
            password: Password to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Dict with hashed password and salt
        """
        if salt is None:
            salt = os.urandom(16)
        else:
            salt = bytes.fromhex(salt) if isinstance(salt, str) else salt

        hash_obj = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            100000
        )

        self._log_encryption("password_hash", {
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "hash": hash_obj.hex(),
            "salt": salt.hex(),
            "algorithm": "pbkdf2_sha256"
        }

    def verify_password(self, password: str, stored_hash: Dict[str, str]) -> bool:
        """Verify password against stored hash.
        
        Args:
            password: Password to verify
            stored_hash: Dict with hash and salt
            
        Returns:
            True if password matches
        """
        new_hash = self.hash_password(password, stored_hash["salt"])
        return hmac.compare_digest(new_hash["hash"], stored_hash["hash"])

    def generate_hmac(self, data: Union[str, bytes]) -> str:
        """Generate HMAC for data integrity verification.
        
        Args:
            data: Data to generate HMAC for
            
        Returns:
            HMAC as hex string
        """
        if isinstance(data, str):
            data = data.encode()

        hmac_obj = hmac.new(self.master_key, data, hashlib.sha256)
        return hmac_obj.hexdigest()

    def verify_hmac(self, data: Union[str, bytes], hmac_value: str) -> bool:
        """Verify HMAC for data integrity.
        
        Args:
            data: Data to verify
            hmac_value: HMAC value to compare against
            
        Returns:
            True if HMAC matches
        """
        computed_hmac = self.generate_hmac(data)
        return hmac.compare_digest(computed_hmac, hmac_value)

    def rotate_key(self) -> Tuple[bytes, bytes]:
        """Rotate encryption key.
        
        Returns:
            Tuple of (old_key, new_key)
        """
        old_key = self.master_key
        new_key = os.urandom(32)

        self.key_rotation_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "old_key_hash": hashlib.sha256(old_key).hexdigest(),
            "new_key_hash": hashlib.sha256(new_key).hexdigest()
        })

        self.master_key = new_key
        self._log_encryption("key_rotation", {
            "timestamp": datetime.utcnow().isoformat(),
            "history_length": len(self.key_rotation_history)
        })

        return old_key, new_key

    def get_encryption_log(self) -> Dict[str, Any]:
        """Get encryption operation log.
        
        Returns:
            Encryption log dictionary
        """
        return self.encryption_log.copy()

    def get_key_rotation_history(self) -> list:
        """Get key rotation history.
        
        Returns:
            List of key rotation events
        """
        return self.key_rotation_history.copy()

    def _log_encryption(self, operation: str, details: Dict[str, Any]) -> None:
        """Log encryption operation.
        
        Args:
            operation: Operation name
            details: Operation details
        """
        if operation not in self.encryption_log:
            self.encryption_log[operation] = []
        
        self.encryption_log[operation].append(details)

    def get_stats(self) -> Dict[str, Any]:
        """Get encryption statistics.
        
        Returns:
            Statistics dictionary
        """
        total_operations = sum(len(v) for v in self.encryption_log.values())
        
        return {
            "total_operations": total_operations,
            "operations_by_type": {k: len(v) for k, v in self.encryption_log.items()},
            "key_rotations": len(self.key_rotation_history),
            "rsa_keys_generated": bool(self.rsa_private_key)
        }
