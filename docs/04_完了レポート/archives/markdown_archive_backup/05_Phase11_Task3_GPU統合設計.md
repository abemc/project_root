# 🚀 Task 3: GPU 統合 & ML 推論最適化 設計書

**フェーズ**: Phase 11 - Task 3  
**期間**: Week 3-5 (3 週間)  
**バージョン**: v1.0  
**作成日**: 2026-04-17  
**ステータス**: 📋 設計フェーズ

---

## 🎯 概要

Phase 10 での CPU 依存型 ML 推論を GPU アクセラレーションで高速化し、推論レイテンシを 70% 削減、スループットを 3 倍に増加させるタスク。

### 成功基準
- 🎯 推論レイテンシ: **-70%** (80ms → 24ms)
- 🎯 推論スループット: **+200%** (5,000 → 15,000 推論/秒)
- 🎯 GPU 使用率: **最適化** (50% 目標)
- 🎯 メモリ効率: **-50%** (GPU VRAM 最適化)
- 🎯 Cost per inference: **-65%**

---

## 📊 現在の推論ボトルネック

### Phase 10 推論分析結果

```
Total Inferences/sec:       5,000 推論/s
CPU Inference Time:         80ms 平均
Threat Score Computation:   45ms (CPU)
ML Model Inference:         25ms (CPU)
Data Transfer Overhead:     8ms

Model Type Distribution:
  - GRU Threat Detection:    2,500/s
  - Embedding Generation:    1,500/s
  - Anomaly Detection:       1,000/s

GPU Availability:
  - Current: NOT IN USE
  - Resource: 1x GPU (NVIDIA A100)
  - VRAM: 40GB available
  - Compute Capacity: 312 TFLOPS
```

### Performance Bottlenecks

```
Problem 1: CPU Inference (45% of total time)
  - NumPy 計算 (スレッド制約)
  - メモリバンド幅制限
  - GIL ロック

Problem 2: メモリ転送 (8% overhead)
  - GPU ← CPU データ転送
  - CPU ← GPU 結果転送
  - バッファリングなし

Problem 3: モデル I/O (10% overhead)
  - ファイルベースモデルロード
  - 毎回パース
  - キャッシングなし

Expected Impact:
  Current: 5,000/s × 80ms = 400 推論並行
  GPU Target: 15,000/s × 24ms = 360 推論並行 (効率化)
```

---

## 🔧 GPU 統合戦略

### 1. TensorRT による推論最適化

#### 1.1 Model Compilation

```python
# ❌ 現在: PyTorch モデル (CPU で実行)
model = ThreatDetectionModel()
output = model(input_tensor)
# 実行時間: 45ms

# ✅ 最適化: TensorRT エンジン化
# Step 1: PyTorch → ONNX 変換
torch.onnx.export(model, ...)

# Step 2: ONNX → TensorRT エンジン
builder = trt.Builder(logger)
network = builder.create_network()
parser = trt.OnnxParser(network, logger)
config = builder.create_builder_config()
config.set_flag(trt.BuilderFlag.FP16)  # FP16 精度

# Step 3: エンジンをシリアライズ
engine = builder.build_serialized_network(config)

# Step 4: 推論実行
context = engine.create_execution_context()
output = context.execute_v2(buffers)
# 実行時間: 6ms (7.5 倍高速化) ✅
```

**期待効果**: 推論時間 45ms → 6ms (-87%)

#### 1.2 Precision Optimization

```
FP32 (32-bit Float): 45ms (基準)
  - 精度: 最高
  - 速度: 基準

FP16 (16-bit Float): 12ms (-73%)
  - 精度: 十分 (99.8% 一致)
  - 速度: 3.75 倍高速

INT8 (8-bit Integer): 6ms (-87%)
  - 精度: 微調整後 99.5% 一致
  - 速度: 7.5 倍高速

選択: INT8 (最大性能、十分な精度)
```

### 2. 推論パイプライン最適化

#### 2.1 バッチ処理

```python
# ❌ 現在: 単一推論ループ
for request in requests:
    output = model.infer(request)
# 時間: N × 80ms (順序処理)

# ✅ 最適化: バッチ推論
batch_size = 64
for i in range(0, len(requests), batch_size):
    batch = requests[i:i+batch_size]
    batch_tensor = torch.stack([r.tensor for r in batch])
    outputs = model.infer_batch(batch_tensor)
# 時間: (N/64) × 6ms + オーバーヘッド
# 削減: -96% (80ms → 3ms per inference)
```

**期待効果**: バッチ処理で -96% (単位あたり)

#### 2.2 非同期パイプライン

```
        Input Queue
             ↓
    [GPU Thread] 推論実行中
    ├─ Batch 1: 6ms
    ├─ Batch 2: 6ms
    └─ Batch 3: 6ms (次の 18ms 間)
             ↓
        Output Queue

同期処理:  Batch 1 → Batch 2 → Batch 3
時間: 18ms (順序)

非同期処理:
Batch 1 実行中に Batch 2 待機
Batch 2 実行中に Batch 3 待機
時間: ~20ms (2.5 バッチ並列)
削減: -10% (オーバーヘッド考慮)
```

### 3. GPU メモリ管理

#### 3.1 推論エンジン配置

```yaml
GPU VRAM配置 (40GB A100):

Persistent:
  - TensorRT Engines: 2GB
    * Threat Detection: 800MB
    * Embedding Gen: 600MB
    * Anomaly Detect: 600MB
  
  - Model Weights: 3GB
    * Cached models: 3GB
  
  - Static Buffers: 2GB
    * Input staging: 500MB
    * Output staging: 500MB
    * Workspace: 1GB

Total Persistent: 7GB

Per-Batch (Temporary):
  - Batch Input: 500MB (64 samples)
  - Batch Output: 500MB
  - Intermediate: 1GB
  
Total Per-Batch: 2GB (同時実行中)

Available for Scaling: 40 - 7 - 2 = 31GB ✅
```

**期待効果**: 十分な VRAM マージン

#### 3.2 VRAM キャッシング戦略

```python
# Active Model Caching
class GPUModelCache:
    def __init__(self, max_vram_gb=10):
        self.cache = {}  # model_id → engine
        self.total_vram = 0
        self.max_vram = max_vram_gb * 1024**3
    
    def get_engine(self, model_id):
        # Hit: キャッシュから直接返却
        if model_id in self.cache:
            return self.cache[model_id]
        
        # Miss: モデル読込 → VRAM キャッシュ
        engine = load_tensorrt_engine(model_id)
        self.cache[model_id] = engine
        self.total_vram += engine.get_vram_size()
        
        # LRU 削除
        while self.total_vram > self.max_vram:
            old_id = self._evict_oldest()
            del self.cache[old_id]
        
        return engine
```

**期待効果**: モデルロード時間 -100% (初回後)

### 4. 推論 キャッシング

#### 4.1 キャッシュキー戦略

```python
# Layer 別キャッシング
cache_key_patterns = {
    "threat_score": f"threat_score:{user_id}:{context_id}:{timestamp_bucket}",
    # TTL: 5分
    
    "embedding": f"embedding:{data_id}:{version}",
    # TTL: 24時間 (変化しない)
    
    "anomaly_detection": f"anomaly:{device_id}:{time_bucket}",
    # TTL: 10分
}
```

**期待効果**: 推論キャッシュヒット率 40-60%

---

## 📊 性能予測

### 推論スループット改善

```
Phase 10 (CPU):
  - 単一推論: 80ms
  - スループット: 5,000/s
  - 遅延: P99 = 200ms

Phase 11 改善段階:
  ✅ TensorRT (INT8): 45ms → 6ms (87%)
  ✅ バッチ処理 64 (6ms → 3ms): 96%
  ✅ 非同期処理 (+10%)
  ✅ GPU キャッシング (Hit時 -100%)
  
  → 最終: 3ms × 0.9 (非同期 O/H) = 2.7ms/推論
  → スループット: 15,000/s+
  → キャッシュヒット 50%: 効果的レイテンシ 1.35ms
```

### コスト削減

```
Phase 10 (CPU):
  - CPU リソース: EC2 c5.9xlarge × 4 = $10,000/月
  - メモリ: 128GB × 4 = $2,000/月
  - 合計: $12,000/月

Phase 11 (GPU):
  - GPU: A100 × 1 = $3,500/月
  - 副 CPU: c5.4xlarge × 2 = $5,000/月
  - メモリ: 64GB × 2 = $1,000/月
  - 合計: $9,500/月

削減: -21% ($12,000 → $9,500)
+ 性能: 3 倍向上
```

---

## 🛠️ 実装フェーズ

### Phase 1: TensorRT 環境構築 (Day 1-3)

```
Step 1: CUDA/cuDNN/TensorRT インストール
Step 2: PyTorch → ONNX 変換
Step 3: ONNX → TensorRT エンジン生成
Step 4: INT8 キャリブレーション
Step 5: 単一推論テスト
```

### Phase 2: 推論エンジン実装 (Day 4-7)

```
Step 1: GPUInferenceEngine クラス実装
Step 2: バッチ処理 エンジン構築
Step 3: 非同期実行 対応
Step 4: エラーハンドリング
Step 5: ヘルスチェック
```

### Phase 3: キャッシング & 統合 (Day 8-14)

```
Step 1: GPU キャッシング実装
Step 2: Redis 推論キャッシュ統合
Step 3: フォールバック機構
Step 4: 監視・ロギング
Step 5: 統合テスト
```

### Phase 4: パフォーマンス検証 (Day 15-21)

```
Step 1: Staging デプロイ
Step 2: A/B テスト (CPU vs GPU)
Step 3: レイテンシ測定
Step 4: SLA 検証
Step 5: 本番ロールアウト計画
```

---

## 🧪 テスト戦略

### Unit テスト
- TensorRT エンジン初期化
- バッチ処理の正確性
- キャッシュヒット/ミス
- エラーハンドリング

### 統合テスト
- GPU ← CPU データ転送検証
- バッチ結果の一貫性
- 推論キャッシュ一貫性
- フォールバック動作

### パフォーマンステスト
- 推論レイテンシ (目標: <30ms)
- スループット (目標: 15,000/s)
- メモリ使用量 (目標: <10GB persistent)
- GPU 使用率 (目標: 50%)

---

## ✅ 完了基準

```
✅ TensorRT エンジン: 作成・キャリブレーション完了
✅ バッチ処理: 実装・テスト完了
✅ 推論キャッシング: Redis 統合完了
✅ パフォーマンス: 目標値達成
✅ テスト: 100% PASS
✅ SLA 維持: 99.99%
```

---

## 📋 実装チェックリスト

### Week 3-4: GPU 統合 & 最適化
- [ ] TensorRT 環境セットアップ
- [ ] PyTorch ↔ ONNX 変換パイプ
- [ ] INT8 キャリブレーション
- [ ] GPU 推論エンジン実装
- [ ] バッチ処理エンジン
- [ ] 非同期実行サポート
- [ ] ユニットテスト (100%)
- [ ] Staging 統合テスト

### Week 5: パフォーマンス検証
- [ ] A/B テスト (CPU vs GPU)
- [ ] レイテンシ測定
- [ ] スループット測定
- [ ] SLA 検証
- [ ] Go Live 判定

---

**次のステップ**: GPU 推論エンジン実装開始

