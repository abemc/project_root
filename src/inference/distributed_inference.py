# -*- coding: utf-8 -*-
"""
分散推論エンジン実装
Phase 12 Task 1

複数GPU・複数ノード間での推論分散処理
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import numpy as np
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


# ============================================================================
# GPU ノード管理
# ============================================================================

class GPUStatus(Enum):
    """GPU ステータス"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    OFFLINE = "offline"


@dataclass
class GPUNodeInfo:
    """GPU ノード情報"""
    node_id: str
    gpu_count: int
    vram_total_gb: float
    vram_used_gb: float = 0.0
    status: GPUStatus = GPUStatus.HEALTHY
    latency_ms: float = 0.0
    throughput_req_sec: int = 0
    error_count: int = 0
    last_heartbeat: datetime = None
    
    @property
    def utilization_percent(self) -> float:
        """GPU 使用率"""
        if self.vram_total_gb == 0:
            return 0.0
        return (self.vram_used_gb / self.vram_total_gb) * 100
    
    @property
    def availability_score(self) -> float:
        """ノード可用性スコア (0-1)"""
        if self.status == GPUStatus.HEALTHY:
            return 1.0 - (self.utilization_percent / 100)
        elif self.status == GPUStatus.DEGRADED:
            return 0.5
        else:
            return 0.0


# ============================================================================
# 分散推論リクエスト
# ============================================================================

@dataclass
class DistributedInferenceRequest:
    """分散推論リクエスト"""
    request_id: str
    model_id: str
    input_data: np.ndarray
    priority: int = 0
    timeout_sec: int = 30
    preferred_node_id: Optional[str] = None  # 優先ノード
    
    def __lt__(self, other):
        """優先度キューソート"""
        return self.priority > other.priority


@dataclass
class InferenceResult:
    """推論結果"""
    request_id: str
    model_id: str
    output: np.ndarray
    node_id: str
    inference_time_ms: float
    routing_time_ms: float = 0.0
    total_time_ms: float = 0.0
    timestamp: datetime = None


# ============================================================================
# GPU クラスタ管理
# ============================================================================

class GPUCluster:
    """GPU クラスタ管理"""
    
    def __init__(self):
        self.nodes: Dict[str, GPUNodeInfo] = {}
        self.stats = {
            "total_nodes": 0,
            "healthy_nodes": 0,
            "avg_utilization": 0.0,
            "total_throughput": 0,
        }
    
    def register_node(
        self,
        node_id: str,
        gpu_count: int,
        vram_total_gb: float
    ) -> bool:
        """ノード登録"""
        if node_id in self.nodes:
            logger.warning(f"⚠️  ノード既に登録: {node_id}")
            return False
        
        node = GPUNodeInfo(
            node_id=node_id,
            gpu_count=gpu_count,
            vram_total_gb=vram_total_gb,
            last_heartbeat=datetime.now(),
        )
        
        self.nodes[node_id] = node
        self.stats["total_nodes"] = len(self.nodes)
        
        logger.info(f"✅ GPU ノード登録: {node_id} (GPU: {gpu_count}, VRAM: {vram_total_gb}GB)")
        return True
    
    def update_node_status(
        self,
        node_id: str,
        vram_used_gb: float,
        latency_ms: float,
        throughput: int,
        error_count: int = 0
    ):
        """ノード状態更新"""
        if node_id not in self.nodes:
            logger.warning(f"❌ ノット見つかりません: {node_id}")
            return
        
        node = self.nodes[node_id]
        node.vram_used_gb = vram_used_gb
        node.latency_ms = latency_ms
        node.throughput_req_sec = throughput
        node.error_count = error_count
        node.last_heartbeat = datetime.now()
        
        # ステータス判定
        if error_count > 5:
            node.status = GPUStatus.FAILED
        elif node.utilization_percent > 90:
            node.status = GPUStatus.DEGRADED
        else:
            node.status = GPUStatus.HEALTHY
    
    def select_best_node(self) -> Optional[str]:
        """最適ノード選択 (可用性スコアベース)"""
        healthy_nodes = [
            node for node in self.nodes.values()
            if node.status == GPUStatus.HEALTHY
        ]
        
        if not healthy_nodes:
            logger.warning("❌ 利用可能なノードがありません")
            return None
        
        # スコアが最高のノードを選択
        best_node = max(healthy_nodes, key=lambda n: n.availability_score)
        return best_node.node_id
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """クラスタ統計取得"""
        if not self.nodes:
            return self.stats
        
        healthy = sum(1 for n in self.nodes.values() if n.status == GPUStatus.HEALTHY)
        avg_util = np.mean([n.utilization_percent for n in self.nodes.values()])
        total_tps = sum(n.throughput_req_sec for n in self.nodes.values())
        
        self.stats.update({
            "healthy_nodes": healthy,
            "avg_utilization": avg_util,
            "total_throughput": total_tps,
        })
        
        return self.stats.copy()


# ============================================================================
# ルーティングエンジン
# ============================================================================

class RoutingEngine:
    """リクエストルーティングエンジン"""
    
    def __init__(self, cluster: GPUCluster):
        self.cluster = cluster
        self.route_stats = defaultdict(lambda: {"routed": 0, "failed": 0})
        self.load_history: Dict[str, List[float]] = defaultdict(list)
    
    async def route_request(
        self,
        request: DistributedInferenceRequest
    ) -> Optional[str]:
        """リクエストをノードにルーティング"""
        start = time.time()
        
        # 優先ノードがあれば確認
        if request.preferred_node_id:
            node = self.cluster.nodes.get(request.preferred_node_id)
            if node and node.status == GPUStatus.HEALTHY:
                self.route_stats[request.preferred_node_id]["routed"] += 1
                routing_time = (time.time() - start) * 1000
                logger.debug(f"✅ 優先ノードへルーティング: {request.preferred_node_id} ({routing_time:.2f}ms)")
                return request.preferred_node_id
        
        # 最適ノード選択
        best_node_id = self.cluster.select_best_node()
        
        if best_node_id:
            self.route_stats[best_node_id]["routed"] += 1
            routing_time = (time.time() - start) * 1000
            logger.debug(f"✅ ルーティング: {best_node_id} ({routing_time:.2f}ms)")
            return best_node_id
        else:
            logger.error(f"❌ ルーティング失敗: {request.request_id}")
            for node_id in self.route_stats:
                self.route_stats[node_id]["failed"] += 1
            return None
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """ルーティング統計"""
        return dict(self.route_stats)


# ============================================================================
# 分散推論エンジン
# ============================================================================

class DistributedInferenceEngine:
    """分散推論エンジン"""
    
    def __init__(self):
        self.cluster = GPUCluster()
        self.router = RoutingEngine(self.cluster)
        self.aggregator = ResultAggregator()
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_latency_ms": 0.0,
            "avg_routing_latency_ms": 0.0,
        }
    
    def register_gpu_node(
        self,
        node_id: str,
        gpu_count: int,
        vram_total_gb: float
    ) -> bool:
        """GPU ノード登録"""
        return self.cluster.register_node(node_id, gpu_count, vram_total_gb)
    
    async def infer(
        self,
        request: DistributedInferenceRequest
    ) -> Optional[InferenceResult]:
        """分散推論実行"""
        start = time.time()
        self.stats["total_requests"] += 1
        
        # Step 1: ルーティング
        routing_start = time.time()
        node_id = await self.router.route_request(request)
        routing_time_ms = (time.time() - routing_start) * 1000
        
        if not node_id:
            self.stats["failed_requests"] += 1
            return None
        
        # Step 2: シミュレーション推論
        await asyncio.sleep(0.006)  # 6ms 推論
        output = np.random.randn(256).astype(np.float32)
        
        # Step 3: 結果集約
        inference_time_ms = (time.time() - start - routing_time_ms)
        total_time_ms = (time.time() - start) * 1000
        
        result = InferenceResult(
            request_id=request.request_id,
            model_id=request.model_id,
            output=output,
            node_id=node_id,
            inference_time_ms=inference_time_ms * 1000,
            routing_time_ms=routing_time_ms,
            total_time_ms=total_time_ms,
            timestamp=datetime.now(),
        )
        
        # 統計更新
        self.aggregator.add_result(result)
        self.stats["successful_requests"] += 1
        
        latencies = [r.total_time_ms for r in self.aggregator.results[-100:]]
        self.stats["avg_latency_ms"] = np.mean(latencies) if latencies else 0.0
        
        routing_latencies = [r.routing_time_ms for r in self.aggregator.results[-100:]]
        self.stats["avg_routing_latency_ms"] = np.mean(routing_latencies) if routing_latencies else 0.0
        
        return result
    
    async def batch_infer(
        self,
        requests: List[DistributedInferenceRequest]
    ) -> List[InferenceResult]:
        """バッチ分散推論"""
        tasks = [self.infer(req) for req in requests]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
    
    def get_engine_report(self) -> Dict[str, Any]:
        """エンジンレポート"""
        return {
            "cluster": self.cluster.get_cluster_stats(),
            "routing": self.router.get_routing_stats(),
            "aggregator": self.aggregator.get_stats(),
            "engine": self.stats.copy(),
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================================
# 結果集約エンジン
# ============================================================================

class ResultAggregator:
    """推論結果集約"""
    
    def __init__(self):
        self.results: List[InferenceResult] = []
        self.stats = {
            "total_results": 0,
            "avg_inference_time": 0.0,
            "avg_routing_time": 0.0,
            "max_inference_time": 0.0,
            "min_inference_time": float('inf'),
        }
    
    def add_result(self, result: InferenceResult):
        """結果追加"""
        self.results.append(result)
        self.stats["total_results"] += 1
        
        # 統計更新
        if result.inference_time_ms > 0:
            self.stats["avg_inference_time"] = (
                self.stats["avg_inference_time"] * 0.9 +
                result.inference_time_ms * 0.1
            )
            self.stats["max_inference_time"] = max(
                self.stats["max_inference_time"],
                result.inference_time_ms
            )
            self.stats["min_inference_time"] = min(
                self.stats["min_inference_time"],
                result.inference_time_ms
            )
        
        if result.routing_time_ms > 0:
            self.stats["avg_routing_time"] = (
                self.stats["avg_routing_time"] * 0.9 +
                result.routing_time_ms * 0.1
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """統計取得"""
        return self.stats.copy()


# ============================================================================
# グローバルインスタンス
# ============================================================================

_distributed_engine: Optional[DistributedInferenceEngine] = None


async def initialize_distributed_inference() -> DistributedInferenceEngine:
    """分散推論エンジン初期化"""
    global _distributed_engine
    _distributed_engine = DistributedInferenceEngine()
    
    # テスト用ノード登録
    _distributed_engine.register_gpu_node("node_dc1_gpu1", 4, 24.0)
    _distributed_engine.register_gpu_node("node_dc1_gpu2", 4, 24.0)
    _distributed_engine.register_gpu_node("node_dc2_gpu1", 4, 24.0)
    _distributed_engine.register_gpu_node("node_dc2_gpu2", 4, 24.0)
    
    logger.info("✅ 分散推論エンジン初期化完了 (4 nodes)")
    return _distributed_engine


def get_distributed_engine() -> DistributedInferenceEngine:
    """分散推論エンジン取得"""
    if _distributed_engine is None:
        raise RuntimeError("分散推論エンジンが初期化されていません")
    return _distributed_engine
