"""
暗号化エンジン実装

エンドツーエンド暗号化機能
- AES-256-GCM対称鍵暗号
- RSA-4096公開鍵暗号
- 鍵管理システム
- メトリクス収集
"""

import os
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import base64
import json

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EncryptionConfig:
    """暗号化設定"""
    algorithm: str = "AES-256-GCM"
    key_size: int = 32  # 256ビット = 32バイト
    iv_size: int = 12   # 96ビット = 12バイト（GCM推奨）
    tag_size: int = 16  # 128ビット = 16バイト
    rsa_key_size: int = 4096
    key_rotation_days: int = 90


@dataclass
class EncryptionMetrics:
    """暗号化メトリクス"""
    total_encryptions: int = 0
    total_decryptions: int = 0
    total_bytes_encrypted: int = 0
    total_bytes_decrypted: int = 0
    encryption_errors: int = 0
    decryption_errors: int = 0
    last_encryption_time: Optional[datetime] = None
    last_decryption_time: Optional[datetime] = None
    
    def get_success_rate(self) -> float:
        """成功率を取得"""
        total = self.total_encryptions + self.total_decryptions
        if total == 0:
            return 100.0
        errors = self.encryption_errors + self.decryption_errors
        return ((total - errors) / total) * 100
    
    def get_avg_encryption_size(self) -> float:
        """平均暗号化サイズを取得"""
        if self.total_encryptions == 0:
            return 0.0
        return self.total_bytes_encrypted / self.total_encryptions
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_encryptions": self.total_encryptions,
            "total_decryptions": self.total_decryptions,
            "total_bytes_encrypted": self.total_bytes_encrypted,
            "total_bytes_decrypted": self.total_bytes_decrypted,
            "encryption_errors": self.encryption_errors,
            "decryption_errors": self.decryption_errors,
            "success_rate": self.get_success_rate(),
            "avg_encryption_size": self.get_avg_encryption_size(),
        }


class KeyManager:
    """鍵管理"""
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        """初期化"""
        self.config = config or EncryptionConfig()
        self.master_key: Optional[bytes] = None
        self.rsa_private_key = None
        self.rsa_public_key = None
        self.key_registry: Dict[str, Dict[str, Any]] = {}
        self._lock_available = False
        
        try:
            import asyncio
            self._lock = asyncio.Lock()
            self._lock_available = True
        except:
            pass
    
    def generate_master_key(self) -> bytes:
        """マスターキーを生成"""
        key = os.urandom(self.config.key_size)
        self.master_key = key
        logger.info("Master key generated")
        return key
    
    def set_master_key(self, key: bytes) -> None:
        """マスターキーを設定"""
        if len(key) != self.config.key_size:
            raise ValueError(f"Key must be {self.config.key_size} bytes")
        self.master_key = key
        logger.info("Master key set")
    
    def get_master_key(self) -> Optional[bytes]:
        """マスターキーを取得"""
        if self.master_key is None:
            raise RuntimeError("Master key not set")
        return self.master_key
    
    def generate_rsa_keypair(self) -> Tuple[Any, Any]:
        """RSA鍵ペアを生成"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library not available")
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.config.rsa_key_size,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        self.rsa_private_key = private_key
        self.rsa_public_key = public_key
        
        logger.info(f"RSA {self.config.rsa_key_size}-bit keypair generated")
        return private_key, public_key
    
    def get_rsa_private_key(self) -> Any:
        """RSA秘密鍵を取得"""
        if self.rsa_private_key is None:
            raise RuntimeError("RSA private key not set")
        return self.rsa_private_key
    
    def get_rsa_public_key(self) -> Any:
        """RSA公開鍵を取得"""
        if self.rsa_public_key is None:
            raise RuntimeError("RSA public key not set")
        return self.rsa_public_key
    
    def export_rsa_public_key(self) -> str:
        """RSA公開鍵をPEM形式でエクスポート"""
        public_key = self.get_rsa_public_key()
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')
    
    def import_rsa_public_key(self, pem: str) -> None:
        """RSA公開鍵をPEM形式からインポート"""
        public_key = serialization.load_pem_public_key(
            pem.encode('utf-8'),
            backend=default_backend()
        )
        self.rsa_public_key = public_key
        logger.info("RSA public key imported")
    
    def register_key(self, key_id: str, key: bytes, metadata: Optional[Dict] = None) -> None:
        """鍵を登録"""
        self.key_registry[key_id] = {
            "key": key,
            "created": datetime.now(),
            "metadata": metadata or {},
        }
        logger.info(f"Key registered: {key_id}")
    
    def get_registered_key(self, key_id: str) -> Optional[bytes]:
        """登録された鍵を取得"""
        if key_id in self.key_registry:
            return self.key_registry[key_id]["key"]
        return None
    
    def list_keys(self) -> Dict[str, Dict[str, Any]]:
        """すべての登録鍵をリスト"""
        result = {}
        for key_id, data in self.key_registry.items():
            result[key_id] = {
                "created": data["created"].isoformat(),
                "metadata": data["metadata"],
            }
        return result


class CryptoEngine:
    """暗号化エンジン"""
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        """初期化"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library not available. Install with: pip install cryptography")
        
        self.config = config or EncryptionConfig()
        self.key_manager = KeyManager(config)
        self.metrics = EncryptionMetrics()
    
    def encrypt(self, plaintext: str, key: Optional[bytes] = None) -> str:
        """テキストを暗号化"""
        try:
            # キーを取得
            if key is None:
                key = self.key_manager.get_master_key()
            
            # プレーンテキストをバイト列に変換
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext
            
            # IVを生成
            iv = os.urandom(self.config.iv_size)
            
            # 暗号化
            cipher = AESGCM(key)
            ciphertext = cipher.encrypt(iv, plaintext_bytes, None)
            
            # IV + 暗号文 + タグをBase64エンコード
            encrypted_data = base64.b64encode(iv + ciphertext).decode('utf-8')
            
            # メトリクス更新
            self.metrics.total_encryptions += 1
            self.metrics.total_bytes_encrypted += len(plaintext_bytes)
            self.metrics.last_encryption_time = datetime.now()
            
            logger.debug(f"Data encrypted: {len(plaintext_bytes)} bytes → {len(encrypted_data)} bytes")
            return encrypted_data
            
        except Exception as e:
            self.metrics.encryption_errors += 1
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str, key: Optional[bytes] = None) -> str:
        """テキストを復号化"""
        try:
            # キーを取得
            if key is None:
                key = self.key_manager.get_master_key()
            
            # Base64デコード
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # IV と 暗号文を分離
            iv = encrypted_bytes[:self.config.iv_size]
            ciphertext = encrypted_bytes[self.config.iv_size:]
            
            # 復号化
            cipher = AESGCM(key)
            plaintext_bytes = cipher.decrypt(iv, ciphertext, None)
            
            # バイト列を文字列に変換
            plaintext = plaintext_bytes.decode('utf-8')
            
            # メトリクス更新
            self.metrics.total_decryptions += 1
            self.metrics.total_bytes_decrypted += len(plaintext_bytes)
            self.metrics.last_decryption_time = datetime.now()
            
            logger.debug(f"Data decrypted: {len(encrypted_data)} bytes → {len(plaintext)} chars")
            return plaintext
            
        except Exception as e:
            self.metrics.decryption_errors += 1
            logger.error(f"Decryption error: {e}")
            raise
    
    def encrypt_with_rsa(self, plaintext: str) -> str:
        """RSA公開鍵でテキストを暗号化"""
        try:
            public_key = self.key_manager.get_rsa_public_key()
            
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext
            
            # RSA暗号化
            ciphertext = public_key.encrypt(
                plaintext_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Base64エンコード
            encrypted_data = base64.b64encode(ciphertext).decode('utf-8')
            
            self.metrics.total_encryptions += 1
            self.metrics.total_bytes_encrypted += len(plaintext_bytes)
            
            logger.debug(f"Data encrypted with RSA: {len(plaintext_bytes)} bytes")
            return encrypted_data
            
        except Exception as e:
            self.metrics.encryption_errors += 1
            logger.error(f"RSA encryption error: {e}")
            raise
    
    def decrypt_with_rsa(self, encrypted_data: str) -> str:
        """RSA秘密鍵でテキストを復号化"""
        try:
            private_key = self.key_manager.get_rsa_private_key()
            
            # Base64デコード
            ciphertext = base64.b64decode(encrypted_data)
            
            # RSA復号化
            plaintext_bytes = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # バイト列を文字列に変換
            plaintext = plaintext_bytes.decode('utf-8')
            
            self.metrics.total_decryptions += 1
            self.metrics.total_bytes_decrypted += len(plaintext_bytes)
            
            logger.debug(f"Data decrypted with RSA: {len(encrypted_data)} bytes")
            return plaintext
            
        except Exception as e:
            self.metrics.decryption_errors += 1
            logger.error(f"RSA decryption error: {e}")
            raise
    
    def encrypt_dict(self, data: Dict[str, Any], key: Optional[bytes] = None) -> str:
        """辞書をJSON暗号化"""
        json_str = json.dumps(data)
        return self.encrypt(json_str, key)
    
    def decrypt_dict(self, encrypted_data: str, key: Optional[bytes] = None) -> Dict[str, Any]:
        """JSON復号化を辞書に変換"""
        json_str = self.decrypt(encrypted_data, key)
        return json.loads(json_str)
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """パスワードをハッシュ化"""
        if salt is None:
            salt = os.urandom(16)
        
        # SHA-256ハッシュ化
        password_bytes = password.encode('utf-8')
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password_bytes,
            salt,
            100000
        )
        
        # Base64エンコード
        salt_b64 = base64.b64encode(salt).decode('utf-8')
        hash_b64 = base64.b64encode(hashed).decode('utf-8')
        
        return hash_b64, salt_b64
    
    def verify_password(self, password: str, hash_b64: str, salt_b64: str) -> bool:
        """パスワードを検証"""
        try:
            salt = base64.b64decode(salt_b64)
            stored_hash = base64.b64decode(hash_b64)
            
            # ハッシュ化
            password_bytes = password.encode('utf-8')
            computed_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password_bytes,
                salt,
                100000
            )
            
            # 比較
            return computed_hash == stored_hash
            
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def get_metrics(self) -> EncryptionMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """メトリクスを辞書形式で取得"""
        return self.metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """メトリクスをリセット"""
        self.metrics = EncryptionMetrics()


# グローバルエンジンインスタンス
_global_engine: Optional[CryptoEngine] = None


def get_crypto_engine(config: Optional[EncryptionConfig] = None) -> CryptoEngine:
    """グローバル暗号化エンジンを取得"""
    global _global_engine
    if _global_engine is None:
        _global_engine = CryptoEngine(config)
    return _global_engine


def initialize_crypto(master_key: Optional[bytes] = None) -> CryptoEngine:
    """暗号化エンジンを初期化"""
    engine = get_crypto_engine()
    
    if master_key is None:
        engine.key_manager.generate_master_key()
    else:
        engine.key_manager.set_master_key(master_key)
    
    # RSA鍵ペアを生成
    engine.key_manager.generate_rsa_keypair()
    
    logger.info("Crypto engine initialized")
    return engine
