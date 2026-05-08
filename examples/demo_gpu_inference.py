# -*- coding: utf-8 -*-
"""
GPU 推論エンジン デモスクリプト
Phase 11 Task 3

実装の動作確認とパフォーマンス演出
"""

import asyncio
import numpy as np
import json
from datetime import datetime

# Add src to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from inference.gpu_inference import (
    GPUInferenceRequest,
    initialize_gpu_inference,
    get_performance_comparison,
)


async def demo_single_inference():
    """デモ 1: 単一推論"""
    print("\n" + "="*60)
    print("🔷 デモ 1: 単一推論実行")
    print("="*60)
    
    # サービス初期化
    service = await initialize_gpu_inference()
    
    # リクエスト作成
    request = GPUInferenceRequest(
        request_id="demo_001",
        model_id="threat_detection",
        input_data=np.random.randn(64, 512).astype(np.float32),
        priority=1,
        use_cache=True,
    )
    
    print(f"📥 リクエスト ID: {request.request_id}")
    print(f"📊 モデル: {request.model_id}")
    print(f"📈 入力形状: {request.input_data.shape}")
    print(f"💾 キャッシング: {'有効' if request.use_cache else '無効'}")
    
    # 推論実行
    print("\n⚙️  推論実行中...")
    result = await service.infer(request)
    
    print(f"✅ 推論完了")
    print(f"📤 出力形状: {result.output.shape}")
    print(f"⏱️  推論時間: {result.inference_time_ms:.2f}ms")
    print(f"💾 キャッシュから: {result.from_cache}")


async def demo_batch_inference():
    """デモ 2: バッチ推論"""
    print("\n" + "="*60)
    print("🔷 デモ 2: バッチ推論 (100 リクエスト)")
    print("="*60)
    
    # サービス初期化
    service = await initialize_gpu_inference()
    
    # バッチリクエスト作成
    requests = []
    for i in range(100):
        requests.append(
            GPUInferenceRequest(
                request_id=f"batch_{i:04d}",
                model_id="threat_detection",
                input_data=np.random.randn(1, 512).astype(np.float32),
                priority=i % 3,
            )
        )
    
    print(f"📥 バッチリクエスト数: {len(requests)}")
    print(f"📊 優先度分布: P0={sum(1 for r in requests if r.priority == 0)}, "
          f"P1={sum(1 for r in requests if r.priority == 1)}, "
          f"P2={sum(1 for r in requests if r.priority == 2)}")
    
    # バッチ推論実行
    print("\n⚙️  バッチ推論実行中...")
    results = await service.batch_infer(requests)
    
    print(f"✅ バッチ推論完了")
    print(f"📤 結果数: {len(results)}")
    print(f"⏱️  平均推論時間: {np.mean([r.inference_time_ms for r in results]):.2f}ms")
    print(f"⏱️  最大推論時間: {np.max([r.inference_time_ms for r in results]):.2f}ms")


async def demo_caching():
    """デモ 3: キャッシング効果"""
    print("\n" + "="*60)
    print("🔷 デモ 3: キャッシング効果の演出")
    print("="*60)
    
    # サービス初期化
    service = await initialize_gpu_inference()
    
    # 同じリクエストを複数回実行
    request = GPUInferenceRequest(
        request_id="cache_demo",
        model_id="threat_detection",
        input_data=np.random.randn(1, 512).astype(np.float32),
        use_cache=True,
    )
    
    print(f"📥 同一リクエスト ID: {request.request_id}")
    print(f"💾 キャッシング: 有効\n")
    
    total_time = 0
    for i in range(5):
        result = await service.infer(request)
        total_time += result.inference_time_ms
        cache_indicator = "💾 [CACHE HIT]" if result.from_cache else "🔄 [MISS]"
        print(f"  実行 {i+1}: {result.inference_time_ms:.2f}ms {cache_indicator}")
    
    avg_time = total_time / 5
    print(f"\n✅ 平均推論時間: {avg_time:.2f}ms")
    print(f"💡 キャッシング効果: 1 回目ミス → 2-5 回目ヒット")


async def demo_performance_comparison():
    """デモ 4: パフォーマンス比較"""
    print("\n" + "="*60)
    print("🔷 デモ 4: Phase 10 vs Phase 11 パフォーマンス比較")
    print("="*60)
    
    results = await get_performance_comparison()
    
    # Phase 10 ベースライン
    phase10 = results["phase10_baseline"]
    print(f"\n📊 Phase 10 (ベースライン)")
    print(f"  推論時間: {phase10['inference_time_ms']}ms")
    print(f"  スループット: {phase10['throughput_per_sec']:,} req/sec")
    print(f"  月額コスト: ${phase10['cost_monthly']:,}")
    
    # TensorRT INT8
    int8 = results["tensorrt_int8"]
    print(f"\n📊 TensorRT INT8 最適化")
    print(f"  推論時間: {int8['inference_time_ms']}ms")
    print(f"  改善: {int8['improvement']:.0f}% ⬇️")
    
    # バッチ処理
    batch = results["batch_processing_64"]
    print(f"\n📊 バッチ処理 (バッチサイズ=64)")
    print(f"  推論時間: {batch['inference_time_ms']}ms")
    print(f"  スループット: {batch['throughput_per_sec']:,} req/sec")
    print(f"  改善: {batch['improvement']:.0f}% ⬇️")
    
    # キャッシング
    cache = results["with_caching_50pct"]
    print(f"\n📊 キャッシング (50% ヒット率)")
    print(f"  有効レイテンシ: {cache['effective_latency_ms']}ms")
    print(f"  スループット: {cache['throughput_per_sec']:,} req/sec")
    print(f"  改善: {cache['improvement']:.0f}% ⬇️")
    
    # Phase 11 最終値
    phase11 = results["phase11_target"]
    print(f"\n🎯 Phase 11 最終目標達成")
    print(f"  推論時間: {phase11['inference_time_ms']}ms")
    print(f"  スループット: {phase11['throughput_per_sec']:,} req/sec")
    print(f"  月額コスト: ${phase11['cost_monthly']:,}")
    print(f"  性能改善: {phase11['performance_improvement']:.0f}% 🚀")
    print(f"  コスト削減: {phase11['cost_reduction']:.0f}% 💰")
    
    # 総括
    latency_improvement = ((phase10['inference_time_ms'] - phase11['inference_time_ms']) 
                          / phase10['inference_time_ms'] * 100)
    throughput_improvement = phase11['throughput_per_sec'] / phase10['throughput_per_sec']
    
    print(f"\n" + "="*60)
    print(f"📈 総体的な改善")
    print(f"="*60)
    print(f"  推論レイテンシ: {phase10['inference_time_ms']}ms → {phase11['inference_time_ms']}ms "
          f"({latency_improvement:.0f}% 削減) ✅")
    print(f"  スループット: {phase10['throughput_per_sec']:,} → {phase11['throughput_per_sec']:,} "
          f"req/sec ({throughput_improvement:.1f}x 向上) ✅")
    print(f"  月額コスト: ${phase10['cost_monthly']:,} → ${phase11['cost_monthly']:,} "
          f"({-phase11['cost_reduction']:.0f}% 削減) ✅")


async def demo_monitoring():
    """デモ 5: リアルタイムモニタリング"""
    print("\n" + "="*60)
    print("🔷 デモ 5: リアルタイムモニタリング")
    print("="*60)
    
    # サービス初期化
    service = await initialize_gpu_inference()
    
    # 複数リクエスト実行
    print(f"📥 20 個の推論リクエストを実行中...\n")
    
    for i in range(20):
        request = GPUInferenceRequest(
            request_id=f"monitor_{i:04d}",
            model_id="threat_detection",
            input_data=np.random.randn(1, 512).astype(np.float32),
            use_cache=(i % 2 == 0),  # 50% キャッシング
        )
        await service.infer(request)
    
    # レポート取得
    report = await service.get_inference_report()
    
    print("📊 バッチプロセッサ統計")
    batch_stats = report["batch_processor"]
    print(f"  処理済みバッチ: {batch_stats['batches_processed']}")
    print(f"  処理済みリクエスト: {batch_stats['requests_processed']}")
    print(f"  平均バッチサイズ: {batch_stats['avg_batch_size']:.1f}")
    
    print("\n💾 GPU モデルキャッシング統計")
    cache_stats = report["model_cache"]
    print(f"  キャッシュヒット: {cache_stats['cache_hits']}")
    print(f"  キャッシュミス: {cache_stats['cache_misses']}")
    print(f"  ヒット率: {cache_stats['cache_hit_rate']*100:.1f}%")
    print(f"  キャッシュ済みモデル数: {cache_stats['models_cached']}")
    print(f"  VRAM 使用: {cache_stats['vram_used_mb']:.0f}MB")
    
    print("\n📈 推論結果キャッシング統計")
    infer_cache_stats = report["inference_cache"]
    print(f"  キャッシュヒット: {infer_cache_stats['hits']}")
    print(f"  キャッシュミス: {infer_cache_stats['misses']}")
    print(f"  ヒット率: {infer_cache_stats['hit_rate']*100:.1f}%")
    print(f"  キャッシュエントリ: {infer_cache_stats['entries']}")
    
    print(f"\n⏰ レポート生成時刻: {report['timestamp']}")


async def main():
    """メインデモ実行"""
    print("\n" + "🚀 "*30)
    print("GPU 推論エンジン実装デモンストレーション")
    print("Phase 11 Task 3")
    print("🚀 "*30)
    
    try:
        # デモ実行
        await demo_single_inference()
        await demo_batch_inference()
        await demo_caching()
        await demo_performance_comparison()
        await demo_monitoring()
        
        # 完了メッセージ
        print("\n" + "="*60)
        print("✅ デモンストレーション完了")
        print("="*60)
        print(f"\n📝 実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🎉 Phase 11 Task 3 実装完了!\n")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
