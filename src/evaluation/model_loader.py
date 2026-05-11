#!/usr/bin/env python3
"""
モデルチェックポイント読込エンジン

PyTorchチェックポイントからGPTモデルを読込し、推論に使用可能な状態にします。
"""

import torch
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ModelCheckpointLoader:
    """
    PyTorchチェックポイントからモデルを読込するエンジン
    """
    
    def __init__(self, device: str = 'cpu'):
        """
        初期化
        
        Args:
            device: 計算デバイス ('cpu' or 'cuda')
        """
        self.device = device
        logger.info(f"Initialized ModelCheckpointLoader with device={device}")
    
    def load_checkpoint(self, checkpoint_path: str) -> Optional[torch.nn.Module]:
        """
        チェックポイントからモデルを読込
        
        Args:
            checkpoint_path: チェックポイントファイルのパス
            
        Returns:
            読込されたGPTモデル、またはエラー時はNone
        """
        checkpoint_path = Path(checkpoint_path)
        
        if not checkpoint_path.exists():
            logger.error(f"Checkpoint not found: {checkpoint_path}")
            return None
        
        try:
            logger.info(f"Loading checkpoint from: {checkpoint_path}")
            checkpoint = torch.load(checkpoint_path, map_location=self.device)
            
            # チェックポイント内容を確認
            logger.info(f"Checkpoint keys: {checkpoint.keys()}")
            
            # GPTモデルのインポート
            from model import GPT, GPTConfig
            
            # Configを取得
            if 'config' in checkpoint:
                config_dict = checkpoint['config']
                if isinstance(config_dict, dict):
                    config = GPTConfig(**config_dict)
                else:
                    config = config_dict
            else:
                # デフォルト設定を使用
                logger.warning("No config in checkpoint, using defaults")
                config = GPTConfig(
                    vocab_size=50257,
                    n_layers=6,
                    n_heads=8,
                    embedding_dim=256,
                    block_size=1024
                )
            
            logger.info(f"Creating model with config: {config}")
            
            # モデル生成
            model = GPT(config)
            model.to(self.device)
            
            # 重みを読込
            if 'model_state_dict' in checkpoint:
                logger.info("Loading model_state_dict...")
                model.load_state_dict(checkpoint['model_state_dict'])
            elif 'state_dict' in checkpoint:
                logger.info("Loading state_dict...")
                model.load_state_dict(checkpoint['state_dict'])
            else:
                logger.warning("No state_dict found in checkpoint")
            
            # 評価モード
            model.eval()
            
            logger.info("✅ Model loaded successfully")
            return model
        
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_checkpoint_info(self, checkpoint_path: str) -> Dict[str, Any]:
        """
        チェックポイント内のメタデータを取得
        
        Args:
            checkpoint_path: チェックポイントファイルのパス
            
        Returns:
            メタデータ辞書
        """
        checkpoint_path = Path(checkpoint_path)
        
        try:
            checkpoint = torch.load(checkpoint_path, map_location='cpu')
            
            info = {
                'path': str(checkpoint_path),
                'size_mb': checkpoint_path.stat().st_size / (1024 * 1024),
                'keys': list(checkpoint.keys()),
            }
            
            if 'config' in checkpoint:
                info['config'] = checkpoint['config']
            
            if 'step' in checkpoint:
                info['step'] = checkpoint['step']
            
            if 'model_state_dict' in checkpoint:
                info['params'] = sum(p.numel() for p in checkpoint['model_state_dict'].values())
            
            return info
        
        except Exception as e:
            logger.error(f"Failed to get checkpoint info: {e}")
            return {}


class InferenceEngine:
    """
    モデル推論エンジン
    """
    
    def __init__(self, model: torch.nn.Module, device: str = 'cpu', 
                 max_length: int = 100):
        """
        初期化
        
        Args:
            model: GPTモデル
            device: 計算デバイス
            max_length: 最大生成長
        """
        self.model = model
        self.device = device
        self.max_length = max_length
        logger.info(f"Initialized InferenceEngine (max_length={max_length})")
    
    def generate(self, prompt: str, max_new_tokens: int = 50) -> str:
        """
        テキスト生成推論
        
        Args:
            prompt: 入力プロンプト
            max_new_tokens: 生成トークン数
            
        Returns:
            生成されたテキスト
        """
        try:
            # シンプルなトークン化（文字ベース）
            tokens = self._encode(prompt)
            tokens = torch.tensor([tokens], dtype=torch.long).to(self.device)
            
            with torch.no_grad():
                for _ in range(max_new_tokens):
                    if tokens.shape[1] > self.max_length:
                        break
                    
                    # 推論
                    logits = self.model(tokens)
                    
                    # 最後のトークンの確率分布
                    next_token_logits = logits[0, -1, :]
                    
                    # 最も確率の高いトークンを選択
                    next_token = next_token_logits.argmax(dim=-1, keepdim=True).unsqueeze(0)
                    
                    tokens = torch.cat([tokens, next_token], dim=1)
            
            # デコード
            generated_text = self._decode(tokens[0].tolist())
            return prompt + generated_text
        
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return prompt
    
    def classify(self, text: str, choices: list) -> str:
        """
        テキスト分類推論
        
        Args:
            text: 分類対象のテキスト
            choices: 選択肢リスト
            
        Returns:
            選択された選択肢
        """
        try:
            # 各選択肢に対するスコア計算
            scores = []
            
            for choice in choices:
                # テキスト + 選択肢の結合
                full_text = f"{text} {choice}"
                tokens = self._encode(full_text)
                tokens = torch.tensor([tokens], dtype=torch.long).to(self.device)
                
                with torch.no_grad():
                    logits = self.model(tokens)
                    # 最後のトークンのスコア
                    score = logits[0, -1, :].max().item()
                    scores.append(score)
            
            # 最高スコアの選択肢を返す
            best_idx = scores.index(max(scores))
            return choices[best_idx]
        
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return choices[0] if choices else ""
    
    def _encode(self, text: str) -> list:
        """シンプルなテキストエンコード（文字ベース）"""
        # 文字コードを mod vocab_size
        vocab_size = self.model.config.vocab_size if hasattr(self.model, 'config') else 50257
        return [ord(c) % vocab_size for c in text]
    
    def _decode(self, tokens: list) -> str:
        """シンプルなテキストデコード"""
        try:
            return ''.join(chr(t % 256) if 0 <= t < 256 else '?' for t in tokens)
        except:
            return ""


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*80)
    print("モデルローダー デモンストレーション")
    print("="*80)
    
    # チェックポイント一覧を表示
    checkpoint_dir = Path('checkpoints')
    checkpoints = sorted(checkpoint_dir.glob('ckpt_step_*.pt'))
    
    if checkpoints:
        latest_checkpoint = checkpoints[-1]
        print(f"\n✅ 最新のチェックポイント: {latest_checkpoint.name}")
        
        # ローダーを初期化
        loader = ModelCheckpointLoader(device='cpu')
        
        # チェックポイント情報を取得
        info = loader.get_checkpoint_info(str(latest_checkpoint))
        print("\n📊 チェックポイント情報:")
        print(f"  ├─ サイズ: {info.get('size_mb', 0):.1f} MB")
        print(f"  ├─ パラメータ数: {info.get('params', 0):,}")
        print(f"  ├─ ステップ: {info.get('step', 'N/A')}")
        print(f"  └─ キー: {info.get('keys', [])}")
        
        # モデルを読込
        print("\n📥 モデルを読込中...")
        model = loader.load_checkpoint(str(latest_checkpoint))
        
        if model:
            print("✅ モデル読込成功")
            print(f"  └─ モデル: {model.__class__.__name__}")
            
            # 推論エンジンを初期化
            engine = InferenceEngine(model, device='cpu')
            
            # サンプル推論
            print("\n🔄 サンプル推論:")
            prompt = "What is 2 + 2?"
            result = engine.generate(prompt, max_new_tokens=20)
            print(f"  Prompt: {prompt}")
            print(f"  Result: {result[:100]}...")
    else:
        print("❌ チェックポイントが見つかりません")


if __name__ == "__main__":
    demo()
