"""
Phase 5: Deployment Manager
デプロイメント管理システム - モデルと設定の本番環境への自動デプロイメント

Components:
- DeploymentConfig: デプロイメント設定の定義
- DeploymentArtifact: デプロイ成果物の管理
- DeploymentPipeline: デプロイメントワークフロー
- DeploymentManager: 統合デプロイメント管理
- DeploymentRecovery: デプロイ時の障害回復機構
"""

import os
import json
import shutil
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import tempfile

logger = logging.getLogger(__name__)


class DeploymentEnvironment(Enum):
    """デプロイメント環境の種類"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStatus(Enum):
    """デプロイメント状態"""
    PENDING = "pending"
    VALIDATING = "validating"
    STAGING_DEPLOY = "staging_deploy"
    TESTING = "testing"
    PRODUCTION_DEPLOY = "production_deploy"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ArtifactType(Enum):
    """デプロイ成果物の種類"""
    MODEL_WEIGHTS = "model_weights"
    TOKENIZER = "tokenizer"
    CONFIGURATION = "configuration"
    PROMPT_TEMPLATES = "prompt_templates"
    HYPERPARAMETERS = "hyperparameters"


@dataclass
class DeploymentConfig:
    """デプロイメント設定"""
    config_id: str
    version: str
    timestamp: str
    environment: DeploymentEnvironment
    
    # パス設定
    source_model_path: str
    target_model_path: str
    checkpoint_path: Optional[str] = None
    
    # バージョン管理
    enable_versioning: bool = True
    max_versions: int = 5
    enable_canary: bool = False
    canary_percentage: float = 0.1  # 10% カナリア
    
    # バリデーション
    enable_validation: bool = True
    validation_tests: List[str] = field(default_factory=list)
    
    # ロールバック
    enable_auto_rollback: bool = True
    rollback_threshold: float = 0.05  # 5% 以上のパフォーマンス低下で自動ロールバック
    
    # スケジューリング
    schedule_time: Optional[str] = None  # "02:00" のような形式 (UTC)
    blackout_windows: List[Tuple[str, str]] = field(default_factory=list)  # [(start, end), ...]
    
    # 通知
    notify_on_completion: bool = True
    notification_recipients: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['environment'] = self.environment.value
        d['blackout_windows'] = self.blackout_windows  # Tuples are JSON-serializable
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'DeploymentConfig':
        d = d.copy()
        if isinstance(d.get('environment'), str):
            d['environment'] = DeploymentEnvironment(d['environment'])
        return cls(**d)


@dataclass
class DeploymentArtifact:
    """デプロイ成果物"""
    artifact_id: str
    artifact_type: ArtifactType
    source_path: str
    artifact_hash: str  # SHA256 チェックサム
    size_bytes: int
    timestamp: str
    version: str
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    compression_enabled: bool = False
    compressed_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['artifact_type'] = self.artifact_type.value
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'DeploymentArtifact':
        d = d.copy()
        if isinstance(d.get('artifact_type'), str):
            d['artifact_type'] = ArtifactType(d['artifact_type'])
        return cls(**d)


@dataclass
class DeploymentRecord:
    """デプロイメント実行記録"""
    deployment_id: str
    config_id: str
    status: DeploymentStatus
    start_time: str
    end_time: Optional[str] = None
    
    artifacts_deployed: List[str] = field(default_factory=list)  # artifact_ids
    validation_results: Dict[str, Any] = field(default_factory=dict)
    performance_metrics_before: Dict[str, float] = field(default_factory=dict)
    performance_metrics_after: Dict[str, float] = field(default_factory=dict)
    
    # ロールバック情報
    rollback_triggered: bool = False
    rollback_reason: Optional[str] = None
    rollback_time: Optional[str] = None
    
    # エラー情報
    error_log: Optional[str] = None
    error_type: Optional[str] = None
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['status'] = self.status.value
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'DeploymentRecord':
        d = d.copy()
        if isinstance(d.get('status'), str):
            d['status'] = DeploymentStatus(d['status'])
        return cls(**d)


class DeploymentPipeline:
    """デプロイメントワークフロー"""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.deployment_id = f"deploy_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.artifacts: Dict[str, DeploymentArtifact] = {}
        self.validation_results: Dict[str, Any] = {}
        self.record: Optional[DeploymentRecord] = None
    
    def prepare_artifacts(self, model_path: str, config_dict: Dict) -> List[DeploymentArtifact]:
        """デプロイ成果物の準備"""
        artifacts = []
        
        # モデルウェイト
        model_artifact = self._create_artifact(
            artifact_type=ArtifactType.MODEL_WEIGHTS,
            source_path=model_path,
            version=self.config.version
        )
        artifacts.append(model_artifact)
        self.artifacts[model_artifact.artifact_id] = model_artifact
        
        # 設定ファイル
        config_artifact = self._create_config_artifact(config_dict)
        artifacts.append(config_artifact)
        self.artifacts[config_artifact.artifact_id] = config_artifact
        
        logger.info(f"Prepared {len(artifacts)} artifacts for deployment")
        return artifacts
    
    def _create_artifact(self, artifact_type: ArtifactType, source_path: str, version: str) -> DeploymentArtifact:
        """成果物を作成"""
        artifact_id = f"{artifact_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # ファイルサイズとハッシュを計算
        if os.path.exists(source_path):
            size_bytes = os.path.getsize(source_path)
            artifact_hash = self._compute_hash(source_path)
        else:
            size_bytes = 0
            artifact_hash = "unknown"
        
        return DeploymentArtifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            source_path=source_path,
            artifact_hash=artifact_hash,
            size_bytes=size_bytes,
            timestamp=datetime.now().isoformat(),
            version=version,
            compression_enabled=False
        )
    
    def _create_config_artifact(self, config_dict: Dict) -> DeploymentArtifact:
        """設定成果物を作成"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_dict, f)
            config_path = f.name
        
        artifact_id = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        artifact_hash = self._compute_hash(config_path)
        size_bytes = os.path.getsize(config_path)
        
        artifact = DeploymentArtifact(
            artifact_id=artifact_id,
            artifact_type=ArtifactType.CONFIGURATION,
            source_path=config_path,
            artifact_hash=artifact_hash,
            size_bytes=size_bytes,
            timestamp=datetime.now().isoformat(),
            version=self.config.version,
            compression_enabled=False
        )
        
        return artifact
    
    def _compute_hash(self, file_path: str) -> str:
        """ファイルのSHA256ハッシュを計算"""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error computing hash for {file_path}: {e}")
            return "error"
    
    def validate_artifacts(self) -> Tuple[bool, Dict[str, str]]:
        """成果物のバリデーション"""
        validation_results = {}
        all_valid = True
        
        for artifact_id, artifact in self.artifacts.items():
            try:
                # ファイル存在確認
                if not os.path.exists(artifact.source_path):
                    validation_results[artifact_id] = "FAILED: File not found"
                    all_valid = False
                    continue
                
                # ハッシュ検証
                current_hash = self._compute_hash(artifact.source_path)
                if current_hash != artifact.artifact_hash:
                    validation_results[artifact_id] = "FAILED: Hash mismatch"
                    all_valid = False
                    continue
                
                validation_results[artifact_id] = "PASSED"
                
            except Exception as e:
                validation_results[artifact_id] = f"ERROR: {str(e)}"
                all_valid = False
        
        self.validation_results = validation_results
        return all_valid, validation_results
    
    def deploy_to_environment(self, environment: DeploymentEnvironment, target_path: str) -> bool:
        """環境へのデプロイ"""
        logger.info(f"Deploying to {environment.value}")
        
        try:
            # ターゲットディレクトリの準備
            os.makedirs(target_path, exist_ok=True)
            
            # 成果物をコピー
            for artifact in self.artifacts.values():
                if os.path.exists(artifact.source_path):
                    dest = os.path.join(target_path, os.path.basename(artifact.source_path))
                    if os.path.isfile(artifact.source_path):
                        shutil.copy2(artifact.source_path, dest)
                    else:
                        if os.path.exists(dest):
                            shutil.rmtree(dest)
                        shutil.copytree(artifact.source_path, dest)
                    logger.info(f"Copied {artifact.artifact_id} to {dest}")
            
            return True
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False
    
    def create_deployment_record(self) -> DeploymentRecord:
        """デプロイメント記録を作成"""
        self.record = DeploymentRecord(
            deployment_id=self.deployment_id,
            config_id=self.config.config_id,
            status=DeploymentStatus.PENDING,
            start_time=datetime.now().isoformat(),
            artifacts_deployed=[a.artifact_id for a in self.artifacts.values()],
            validation_results=self.validation_results
        )
        return self.record


class DeploymentRecovery:
    """デプロイ時の障害回復"""
    
    def __init__(self, backup_dir: str = "logs/deployment/backups"):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self, source_path: str, version: str) -> str:
        """デプロイ前のバックアップ作成"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(self.backup_dir, f"backup_{version}_{timestamp}")
        
        try:
            if os.path.isfile(source_path):
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(source_path, backup_path)
            else:
                shutil.copytree(source_path, backup_path)
            
            logger.info(f"Created backup at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return ""
    
    def restore_from_backup(self, backup_path: str, target_path: str) -> bool:
        """バックアップからのリストア"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup not found: {backup_path}")
                return False
            
            if os.path.isfile(backup_path):
                shutil.copy2(backup_path, target_path)
            else:
                if os.path.exists(target_path):
                    shutil.rmtree(target_path)
                shutil.copytree(backup_path, target_path)
            
            logger.info(f"Restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def cleanup_old_backups(self, max_backups: int = 5):
        """古いバックアップをクリーンアップ"""
        try:
            backups = sorted([d for d in os.listdir(self.backup_dir) if d.startswith('backup_')])
            if len(backups) > max_backups:
                for old_backup in backups[:-max_backups]:
                    backup_path = os.path.join(self.backup_dir, old_backup)
                    if os.path.isdir(backup_path):
                        shutil.rmtree(backup_path)
                    else:
                        os.remove(backup_path)
                    logger.info(f"Deleted old backup: {old_backup}")
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")


class DeploymentManager:
    """統合デプロイメント管理システム"""
    
    def __init__(self, logs_dir: str = "logs/deployment"):
        self.logs_dir = logs_dir
        os.makedirs(logs_dir, exist_ok=True)
        
        self.deployments: Dict[str, DeploymentRecord] = {}
        self.configs: Dict[str, DeploymentConfig] = {}
        self.recovery = DeploymentRecovery(os.path.join(logs_dir, "backups"))
        
        self._load_history()
    
    def _load_history(self):
        """デプロイメント履歴を読み込み"""
        history_file = os.path.join(self.logs_dir, "deployment_history.jsonl")
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    for line in f:
                        record_dict = json.loads(line)
                        record = DeploymentRecord.from_dict(record_dict)
                        self.deployments[record.deployment_id] = record
                logger.info(f"Loaded {len(self.deployments)} deployment records")
            except Exception as e:
                logger.error(f"Failed to load deployment history: {e}")
    
    def _save_deployment_record(self, record: DeploymentRecord):
        """デプロイメント記録を保存"""
        history_file = os.path.join(self.logs_dir, "deployment_history.jsonl")
        try:
            self.deployments[record.deployment_id] = record
            with open(history_file, 'a') as f:
                f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to save deployment record: {e}")
    
    def create_deployment_config(
        self,
        version: str,
        environment: DeploymentEnvironment,
        source_model_path: str,
        target_model_path: str,
        **kwargs
    ) -> DeploymentConfig:
        """デプロイメント設定を作成"""
        config_id = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        config = DeploymentConfig(
            config_id=config_id,
            version=version,
            timestamp=datetime.now().isoformat(),
            environment=environment,
            source_model_path=source_model_path,
            target_model_path=target_model_path,
            **kwargs
        )
        
        self.configs[config_id] = config
        logger.info(f"Created deployment config: {config_id}")
        
        return config
    
    def validate_deployment_config(self, config: DeploymentConfig) -> Tuple[bool, List[str]]:
        """デプロイメント設定の検証"""
        errors = []
        
        # パスの検証
        if not os.path.exists(config.source_model_path):
            errors.append(f"Source model path not found: {config.source_model_path}")
        
        if not os.path.exists(os.path.dirname(config.target_model_path)):
            errors.append(f"Target model directory not found: {os.path.dirname(config.target_model_path)}")
        
        # エンバイロンメント固有の検証
        if config.environment == DeploymentEnvironment.PRODUCTION and config.enable_canary:
            if config.canary_percentage <= 0 or config.canary_percentage >= 1:
                errors.append("Canary percentage must be between 0 and 1")
        
        return len(errors) == 0, errors
    
    def execute_deployment(
        self,
        config: DeploymentConfig,
        model_checkpoint: Optional[str] = None,
        config_dict: Optional[Dict] = None
    ) -> Tuple[bool, DeploymentRecord]:
        """デプロイメントを実行"""
        
        # 設定のバリデーション
        is_valid, errors = self.validate_deployment_config(config)
        if not is_valid:
            logger.error(f"Deployment config validation failed: {errors}")
            record = DeploymentRecord(
                deployment_id=f"deploy_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                config_id=config.config_id,
                status=DeploymentStatus.FAILED,
                start_time=datetime.now().isoformat(),
                error_log="; ".join(errors),
                error_type="CONFIG_VALIDATION_ERROR"
            )
            self._save_deployment_record(record)
            return False, record
        
        # パイプラインを開始
        pipeline = DeploymentPipeline(config)
        
        # ステップ 1: 成果物の準備
        if config_dict is None:
            config_dict = {
                "version": config.version,
                "timestamp": config.timestamp,
                "environment": config.environment.value
            }
        
        artifacts = pipeline.prepare_artifacts(config.source_model_path, config_dict)
        logger.info(f"Step 1: Prepared {len(artifacts)} artifacts")
        
        # ステップ 2: バリデーション
        if config.enable_validation:
            is_valid, results = pipeline.validate_artifacts()
            if not is_valid:
                logger.error(f"Artifact validation failed: {results}")
                record = DeploymentRecord(
                    deployment_id=f"deploy_validation_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    config_id=config.config_id,
                    status=DeploymentStatus.FAILED,
                    start_time=datetime.now().isoformat(),
                    error_log=json.dumps(results),
                    error_type="ARTIFACT_VALIDATION_ERROR"
                )
                self._save_deployment_record(record)
                return False, record
            logger.info("Step 2: Artifact validation passed")
        
        # ステップ 3: バックアップ作成
        backup_path = self.recovery.create_backup(
            config.source_model_path,
            config.version
        )
        logger.info(f"Step 3: Created backup at {backup_path}")
        
        # ステップ 4: デプロイ
        deployment_success = pipeline.deploy_to_environment(
            config.environment,
            config.target_model_path
        )
        
        if not deployment_success:
            logger.error("Deployment failed")
            # ロールバック
            if backup_path:
                self.recovery.restore_from_backup(backup_path, config.target_model_path)
                logger.info("Rolled back to backup")
            
            record = DeploymentRecord(
                deployment_id=f"deploy_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                config_id=config.config_id,
                status=DeploymentStatus.FAILED,
                start_time=datetime.now().isoformat(),
                error_log="Deployment to environment failed",
                error_type="DEPLOYMENT_ERROR"
            )
            self._save_deployment_record(record)
            return False, record
        
        # ステップ 5: デプロイメント記録を作成
        record = pipeline.create_deployment_record()
        record.status = DeploymentStatus.COMPLETED
        record.end_time = datetime.now().isoformat()
        self._save_deployment_record(record)
        
        logger.info(f"Deployment completed successfully: {record.deployment_id}")
        return True, record
    
    def get_deployment_history(self, limit: int = 10) -> List[DeploymentRecord]:
        """デプロイメント履歴を取得"""
        records = list(self.deployments.values())
        records.sort(key=lambda r: r.start_time, reverse=True)
        return records[:limit]
    
    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """特定のデプロイメント状態を取得"""
        return self.deployments.get(deployment_id)
    
    def get_version_compatibility(self, version1: str, version2: str) -> Dict[str, Any]:
        """バージョン間の互換性を確認"""
        return {
            "version1": version1,
            "version2": version2,
            "compatible": True,  # 簡略版
            "breaking_changes": [],
            "migration_required": False
        }
    
    def cleanup_old_deployments(self, keep_count: int = 5):
        """古いデプロイメント記録をクリーンアップ"""
        records = list(self.deployments.values())
        records.sort(key=lambda r: r.start_time, reverse=True)
        
        if len(records) > keep_count:
            for old_record in records[keep_count:]:
                del self.deployments[old_record.deployment_id]
            logger.info(f"Cleaned up {len(records) - keep_count} old deployment records")
