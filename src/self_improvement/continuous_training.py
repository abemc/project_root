"""継続的マイクロファインチューニングモジュール

ユーザーフィードバックに基づいてモデルの重みを段階的に更新するための機能を提供します。
"""

import json
import logging
import torch
import torch.nn.functional as F
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TrainingCheckpoint:
    """訓練チェックポイント"""
    step: int
    timestamp: str
    loss: float
    learning_rate: float
    num_samples: int
    improvement_percentage: float = 0.0
    model_path: str = ""
    

class ContinuousTrainer:
    """継続的なマイクロファインチューニング"""
    
    def __init__(
        self,
        model,
        optimizer_class=torch.optim.AdamW,
        storage_dir: str = None,
        device: str = None,
    ):
        """
        Args:
            model: 訓練するモデル
            optimizer_class: オプティマイザークラス
            storage_dir: チェックポイント保存先
            device: 計算デバイス (torch.device)
        """
        self.model = model
        self.optimizer_class = optimizer_class
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        if storage_dir is None:
            storage_dir = Path("checkpoints/micro_finetune")
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_file = self.storage_dir / "checkpoints.jsonl"
        self.stats_file = self.storage_dir / "training_stats.json"
        
        # 訓練状態
        self.optimizer = None
        self.current_step = 0
        self.training_history = []
        self._load_checkpoints()
    
    def _load_checkpoints(self):
        """既存のチェックポイント履歴を読み込む"""
        if self.checkpoints_file.exists():
            try:
                with open(self.checkpoints_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            checkpoint = TrainingCheckpoint(**data)
                            self.training_history.append(checkpoint)
                
                if self.training_history:
                    self.current_step = self.training_history[-1].step
                logger.info(f"Loaded {len(self.training_history)} checkpoint records")
            except Exception as e:
                logger.error(f"Failed to load checkpoints: {e}")
    
    def prepare_training_data(
        self,
        feedback_items: List[Dict[str, Any]],
        tokenizer,
        max_length: int = 512,
    ) -> List[Dict[str, torch.Tensor]]:
        """
        フィードバックを訓練データに変換
        
        Args:
            feedback_items: フィードバック項目（instruction, output, rating）
            tokenizer: トークナイザー
            max_length: 最大シーケンス長
        
        Returns:
            トークン化されたバッチ
        """
        training_data = []
        
        for item in feedback_items:
            instruction = item.get("instruction", "")
            output = item.get("output", "")
            rating = item.get("rating", 1.0)  # 評価が高いほど重み付けが大きい
            
            # 入出力を結合
            text = f"Instruction: {instruction}\n\nResponse: {output}"
            
            try:
                # トークン化
                encoded = tokenizer(
                    text,
                    max_length=max_length,
                    truncation=True,
                    padding="max_length",
                    return_tensors="pt"
                )
                
                # サンプル重みを追加（評価に基づく）
                encoded["weights"] = torch.tensor([rating])
                training_data.append(encoded)
                
            except Exception as e:
                logger.warning(f"Failed to encode sample: {e}")
        
        return training_data
    
    def micro_finetune(
        self,
        training_data: List[Dict[str, torch.Tensor]],
        learning_rate: float = 1e-5,
        num_epochs: int = 1,
        batch_size: int = 4,
        gradient_accumulation_steps: int = 2,
        warmup_steps: int = 0,
        save_checkpoint: bool = True,
    ) -> Dict[str, float]:
        """
        マイクロファインチューニング実行
        
        Args:
            training_data: 訓練データ
            learning_rate: 学習率
            num_epochs: エポック数
            batch_size: バッチサイズ
            gradient_accumulation_steps: 勾配蓄積ステップ数
            warmup_steps: ウォームアップステップ数
            save_checkpoint: チェックポイント保存するか
        
        Returns:
            訓練統計
        """
        if not training_data:
            logger.warning("No training data provided")
            return {"loss": 0.0, "improvement": 0.0}
        
        # オプティマイザーの初期化
        if self.optimizer is None:
            self.optimizer = self.optimizer_class(
                self.model.parameters(),
                lr=learning_rate
            )
        
        self.model.to(self.device)
        self.model.train()
        
        total_loss = 0.0
        update_steps = 0
        self.optimizer.zero_grad()
        
        for epoch in range(num_epochs):
            for i, batch in enumerate(training_data):
                # デバイスに移動
                input_ids = batch["input_ids"].to(self.device)
                batch.get("attention_mask", torch.ones_like(input_ids)).to(self.device)
                weights = batch.get("weights", torch.ones(1)).to(self.device)
                
                # 順方向パス
                try:
                    logits = self.model(input_ids)
                    
                    # シンプルな言語モデル損失
                    shift_logits = logits[..., :-1, :].contiguous()
                    shift_labels = input_ids[..., 1:].contiguous()
                    
                    loss = F.cross_entropy(
                        shift_logits.view(-1, shift_logits.size(-1)),
                        shift_labels.view(-1),
                        reduction='mean'
                    )
                    
                    # 評価による重み付け
                    loss = loss * weights.mean()
                    
                    # 逆方向パス（勾配蓄積）
                    loss.backward()
                    total_loss += loss.item()
                    
                    # 勾配蓄積ステップに達したら更新
                    if (i + 1) % gradient_accumulation_steps == 0:
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                        self.optimizer.step()
                        self.optimizer.zero_grad()
                        
                        update_steps += 1
                        self.current_step += 1
                        
                        if update_steps % 10 == 0:
                            logger.info(f"Step {self.current_step}: loss={loss.item():.4f}")
                
                except Exception as e:
                    logger.error(f"Error during training: {e}")
                    self.optimizer.zero_grad()
        
        avg_loss = total_loss / max(1, len(training_data))
        improvement = 100 * (1 - avg_loss) if avg_loss < 1.0 else 0.0
        
        result = {
            "loss": avg_loss,
            "improvement": improvement,
            "total_updates": update_steps,
            "learning_rate": learning_rate,
        }
        
        # チェックポイントを保存
        if save_checkpoint and update_steps > 0:
            self._save_checkpoint(avg_loss, learning_rate, len(training_data), improvement)
        
        logger.info(f"Micro-finetuning completed: loss={avg_loss:.4f}, improvement={improvement:.1f}%")
        
        return result
    
    def _save_checkpoint(
        self,
        loss: float,
        learning_rate: float,
        num_samples: int,
        improvement: float,
    ):
        """チェックポイントを保存"""
        try:
            checkpoint = TrainingCheckpoint(
                step=self.current_step,
                timestamp=datetime.now().isoformat(),
                loss=loss,
                learning_rate=learning_rate,
                num_samples=num_samples,
                improvement_percentage=improvement,
                model_path=str(self.storage_dir / f"model_step_{self.current_step}.pt"),
            )
            
            # モデル重みを保存
            torch.save(
                self.model.state_dict(),
                checkpoint.model_path
            )
            
            # チェックポイント情報を保存
            with open(self.checkpoints_file, 'a', encoding='utf-8') as f:
                data = asdict(checkpoint)
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
            
            self.training_history.append(checkpoint)
            logger.info(f"Saved checkpoint: {checkpoint.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self, step: int) -> bool:
        """
        特定のステップのチェックポイントをロード
        
        Args:
            step: ステップ番号
        
        Returns:
            成功したか
        """
        checkpoint = None
        for ckpt in self.training_history:
            if ckpt.step == step:
                checkpoint = ckpt
                break
        
        if not checkpoint or not Path(checkpoint.model_path).exists():
            logger.error(f"Checkpoint not found for step {step}")
            return False
        
        try:
            state_dict = torch.load(checkpoint.model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.current_step = checkpoint.step
            logger.info(f"Loaded checkpoint from step {step}")
            return True
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return False
    
    def get_training_stats(self) -> Dict[str, Any]:
        """訓練統計を取得"""
        if not self.training_history:
            return {
                "total_steps": 0,
                "total_samples": 0,
                "average_loss": 0.0,
                "total_improvement": 0.0,
                "checkpoints_count": 0,
                "first_checkpoint": None,
                "last_checkpoint": None,
            }
        
        stats = {
            "total_steps": self.current_step,
            "total_samples": sum(ckpt.num_samples for ckpt in self.training_history),
            "average_loss": sum(ckpt.loss for ckpt in self.training_history) / len(self.training_history),
            "total_improvement": sum(ckpt.improvement_percentage for ckpt in self.training_history),
            "checkpoints_count": len(self.training_history),
            "first_checkpoint": self.training_history[0].timestamp if self.training_history else None,
            "last_checkpoint": self.training_history[-1].timestamp if self.training_history else None,
        }
        
        # 統計をファイルに保存
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
        
        return stats
    
    def should_trigger_training(
        self,
        feedback_items: List[Dict[str, Any]],
        threshold: int = 50,
    ) -> bool:
        """
        訓練をトリガーすべきか判定
        
        Args:
            feedback_items: フィードバック項目
            threshold: トレーニングを実行するフィードバック数
        
        Returns:
            訓練をトリガーすべきか
        """
        # 高評価フィードバックの数でチェック
        high_rating_feedback = [
            f for f in feedback_items
            if f.get("rating", 0) >= 0.7
        ]
        
        should_train = len(high_rating_feedback) >= threshold
        
        if should_train:
            logger.info(
                f"Training triggered: {len(high_rating_feedback)} high-rating samples"
            )
        
        return should_train
    
    def get_improvement_trend(self, window: int = 10) -> List[float]:
        """
        改善傾向を取得（最近のウィンドウ）
        
        Returns:
            改善パーセンテージのリスト
        """
        if not self.training_history:
            return []
        
        return [
            ckpt.improvement_percentage
            for ckpt in self.training_history[-window:]
        ]
