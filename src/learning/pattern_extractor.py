"""
Pattern Extractor: 成功パターンの自動抽出・学習

過去のエピソード・実行履歴から、成功した状況の共通特性を抽出。
次回同じシチュエーション検出時に推奨順序・パラメータを自動適用。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json
import logging
from pathlib import Path
from collections import Counter

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """パターンの種別"""
    TOOL_SEQUENCE = "tool_sequence"  # ツール実行順序
    PARAMETER_SET = "parameter_set"  # パラメータの組み合わせ
    CONTEXT_CONDITION = "context_condition"  # 成功する条件
    TIME_PATTERN = "time_pattern"  # 時間帯別パターン
    TASK_DECOMPOSITION = "task_decomposition"  # タスク分解方法


@dataclass
class SuccessPattern:
    """成功パターン"""
    pattern_id: str
    pattern_type: PatternType
    description: str  # パターンの説明
    conditions: Dict[str, Any]  # 成功する条件
    recommendations: Dict[str, Any]  # 推奨アクション
    frequency: int  # 出現回数
    success_rate: float  # 成功率 (0-1)
    confidence: float  # 信頼度 (0-1)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionTrace:
    """実行トレース（パターン抽出用）"""
    trace_id: str
    task_id: str
    tool_sequence: List[str]  # 実行したツール順序
    parameters_used: Dict[str, Dict[str, Any]]  # ツール毎のパラメータ
    context: Dict[str, Any]  # 実行時コンテキスト
    success: bool
    duration_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)


class PatternExtractor:
    """成功パターン抽出・管理"""
    
    def __init__(
        self,
        storage_dir: str = "logs",
        pattern_threshold: int = 5,  # このトレース数でパターン認定
        min_success_rate: float = 0.7,  # パターン認定の最小成功率
    ):
        """
        初期化
        
        Args:
            storage_dir: パターン保存ディレクトリ
            pattern_threshold: パターン認定の閾値トレース数
            min_success_rate: パターン認定の最小成功率
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.traces_file = self.storage_dir / "execution_traces.jsonl"
        self.patterns_file = self.storage_dir / "success_patterns.json"
        
        self.pattern_threshold = pattern_threshold
        self.min_success_rate = min_success_rate
        
        self.traces: List[ExecutionTrace] = []
        self.patterns: Dict[str, SuccessPattern] = {}
        
        self._load_traces()
        self._load_patterns()
    
    def _load_traces(self):
        """実行トレースをロード"""
        if not self.traces_file.exists():
            return
        
        try:
            with open(self.traces_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        trace = ExecutionTrace(
                            trace_id=data['trace_id'],
                            task_id=data['task_id'],
                            tool_sequence=data['tool_sequence'],
                            parameters_used=data['parameters_used'],
                            context=data['context'],
                            success=data['success'],
                            duration_seconds=data['duration_seconds'],
                            timestamp=datetime.fromisoformat(data['timestamp']),
                        )
                        self.traces.append(trace)
        except Exception as e:
            logger.warning(f"Failed to load traces: {e}")
    
    def _load_patterns(self):
        """成功パターンをロード"""
        if not self.patterns_file.exists():
            return
        
        try:
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for pid, pdata in data.items():
                    pattern = SuccessPattern(
                        pattern_id=pdata['pattern_id'],
                        pattern_type=PatternType(pdata['pattern_type']),
                        description=pdata['description'],
                        conditions=pdata['conditions'],
                        recommendations=pdata['recommendations'],
                        frequency=pdata['frequency'],
                        success_rate=pdata['success_rate'],
                        confidence=pdata['confidence'],
                        created_at=datetime.fromisoformat(pdata['created_at']),
                        last_updated=datetime.fromisoformat(pdata['last_updated']),
                    )
                    self.patterns[pid] = pattern
        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")
    
    def record_trace(
        self,
        task_id: str,
        tool_sequence: List[str],
        parameters_used: Dict[str, Dict[str, Any]],
        context: Dict[str, Any],
        success: bool,
        duration_seconds: float,
    ) -> str:
        """
        実行トレースを記録
        
        Args:
            task_id: タスク ID
            tool_sequence: 実行したツールの順序
            parameters_used: 各ツールに使用したパラメータ
            context: 実行時コンテキスト（入力サイズ、優先度など）
            success: 成功フラグ
            duration_seconds: 実行時間
        
        Returns:
            trace_id
        """
        trace = ExecutionTrace(
            trace_id=f"{task_id}_{datetime.now().timestamp()}",
            task_id=task_id,
            tool_sequence=tool_sequence,
            parameters_used=parameters_used,
            context=context,
            success=success,
            duration_seconds=duration_seconds,
        )
        
        self.traces.append(trace)
        
        # ファイルに保存
        try:
            with open(self.traces_file, 'a', encoding='utf-8') as f:
                entry = {
                    'trace_id': trace.trace_id,
                    'task_id': trace.task_id,
                    'tool_sequence': trace.tool_sequence,
                    'parameters_used': trace.parameters_used,
                    'context': trace.context,
                    'success': trace.success,
                    'duration_seconds': trace.duration_seconds,
                    'timestamp': trace.timestamp.isoformat(),
                }
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save trace: {e}")
        
        # パターン検出
        self._extract_patterns()
        
        logger.info(f"Trace recorded: {trace.trace_id} (success={success})")
        return trace.trace_id
    
    def _extract_patterns(self):
        """トレースから成功パターンを抽出"""
        
        # 1. ツール実行順序パターン
        self._extract_tool_sequence_patterns()
        
        # 2. パラメータセットパターン
        self._extract_parameter_patterns()
        
        # 3. コンテキスト条件パターン
        self._extract_context_patterns()
        
        self._save_patterns()
    
    def _extract_tool_sequence_patterns(self):
        """ツール実行順序パターンを抽出"""
        # 成功したトレースのツール順序をグループ化
        sequence_groups: Dict[tuple, List[ExecutionTrace]] = {}
        
        for trace in self.traces:
            if not trace.success:
                continue
            
            seq_key = tuple(trace.tool_sequence)
            if seq_key not in sequence_groups:
                sequence_groups[seq_key] = []
            sequence_groups[seq_key].append(trace)
        
        # 閾値を超えたものをパターン化
        for seq, traces in sequence_groups.items():
            if len(traces) >= self.pattern_threshold:
                pattern_id = f"seq_{hash(seq) % 10000}"
                
                success_count = sum(1 for t in traces if t.success)
                success_rate = success_count / len(traces)
                
                if success_rate >= self.min_success_rate:
                    avg_duration = sum(t.duration_seconds for t in traces) / len(traces)
                    
                    pattern = SuccessPattern(
                        pattern_id=pattern_id,
                        pattern_type=PatternType.TOOL_SEQUENCE,
                        description=f"Successful tool sequence: {' → '.join(seq)}",
                        conditions={
                            'tool_sequence': list(seq),
                        },
                        recommendations={
                            'recommended_tools': list(seq),
                            'expected_duration': avg_duration,
                        },
                        frequency=len(traces),
                        success_rate=success_rate,
                        confidence=min(1.0, len(traces) / (self.pattern_threshold * 2)),
                    )
                    
                    if pattern_id in self.patterns:
                        self.patterns[pattern_id].frequency = len(traces)
                        self.patterns[pattern_id].success_rate = success_rate
                        self.patterns[pattern_id].last_updated = datetime.now()
                    else:
                        self.patterns[pattern_id] = pattern
    
    def _extract_parameter_patterns(self):
        """パラメータセットパターンを抽出"""
        # 成功したトレースのパラメータを集約
        param_profiles: Dict[tuple, List[ExecutionTrace]] = {}
        
        for trace in self.traces:
            if not trace.success:
                continue
            
            # 主要パラメータをキーにしたプロファイル生成（簡易実装）
            profile_items = []
            for tool, params in trace.parameters_used.items():
                # 重要パラメータのみ抽出（例: max_retries, timeout）
                important = {
                    k: v for k, v in params.items()
                    if k in ['max_retries', 'timeout', 'batch_size', 'threshold']
                }
                if important:
                    profile_items.append(json.dumps(important, sort_keys=True))
            
            if profile_items:
                profile_key = tuple(sorted(profile_items))
                if profile_key not in param_profiles:
                    param_profiles[profile_key] = []
                param_profiles[profile_key].append(trace)
        
        # パターン化
        for profile_key, traces in param_profiles.items():
            if len(traces) >= self.pattern_threshold:
                pattern_id = f"param_{hash(profile_key) % 10000}"
                
                success_rate = sum(1 for t in traces if t.success) / len(traces)
                
                if success_rate >= self.min_success_rate:
                    # パラメータプロファイルを復元
                    param_recommendations = {}
                    for item_str in profile_key:
                        param_recommendations.update(json.loads(item_str))
                    
                    pattern = SuccessPattern(
                        pattern_id=pattern_id,
                        pattern_type=PatternType.PARAMETER_SET,
                        description=f"Successful parameter set",
                        conditions={
                            'tool_count': len(traces[0].tool_sequence),
                        },
                        recommendations={
                            'recommended_parameters': param_recommendations,
                        },
                        frequency=len(traces),
                        success_rate=success_rate,
                        confidence=min(1.0, len(traces) / (self.pattern_threshold * 2)),
                    )
                    
                    if pattern_id not in self.patterns:
                        self.patterns[pattern_id] = pattern
    
    def _extract_context_patterns(self):
        """コンテキスト条件パターンを抽出"""
        # 成功したトレースのコンテキストから共通パターンを検出
        success_traces = [t for t in self.traces if t.success]
        
        if len(success_traces) < self.pattern_threshold:
            return
        
        # コンテキストキーの頻出分析
        context_keys = set()
        for trace in success_traces:
            context_keys.update(trace.context.keys())
        
        for key in context_keys:
            values = []
            for trace in success_traces:
                if key in trace.context:
                    values.append(trace.context[key])
            
            # 数値の場合は平均値、カテゴリの場合は最頻値を推奨条件に
            try:
                numeric_values = [float(v) for v in values if isinstance(v, (int, float))]
                if numeric_values:
                    avg_value = sum(numeric_values) / len(numeric_values)
                    pattern_id = f"ctx_{key}"
                    
                    pattern = SuccessPattern(
                        pattern_id=pattern_id,
                        pattern_type=PatternType.CONTEXT_CONDITION,
                        description=f"Success condition: {key} around {avg_value:.2f}",
                        conditions={key: avg_value},
                        recommendations={key: avg_value},
                        frequency=len(success_traces),
                        success_rate=1.0,
                        confidence=0.7,
                    )
                    
                    if pattern_id not in self.patterns:
                        self.patterns[pattern_id] = pattern
            except (ValueError, TypeError):
                # 非数値はスキップ
                pass
    
    def _save_patterns(self):
        """パターンをファイルに保存"""
        try:
            patterns_data = {
                pid: {
                    'pattern_id': p.pattern_id,
                    'pattern_type': p.pattern_type.value,
                    'description': p.description,
                    'conditions': p.conditions,
                    'recommendations': p.recommendations,
                    'frequency': p.frequency,
                    'success_rate': p.success_rate,
                    'confidence': p.confidence,
                    'created_at': p.created_at.isoformat(),
                    'last_updated': p.last_updated.isoformat(),
                }
                for pid, p in self.patterns.items()
            }
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(patterns_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
    
    def get_recommended_actions(
        self,
        context: Dict[str, Any],
        current_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        コンテキストから推奨アクションを取得
        
        Args:
            context: 現在のコンテキスト
            current_tools: 現在のツール実行リスト（オプション）
        
        Returns:
            推奨アクション（ツール順序、パラメータなど）
        """
        recommendations = {
            'tool_sequence': None,
            'parameters': None,
            'confidence': 0.0,
        }
        
        # マッチするパターンを検索
        matching_patterns = []
        
        for pattern in self.patterns.values():
            if pattern.pattern_type == PatternType.TOOL_SEQUENCE:
                # 既存トレースとの類似度をチェック
                if current_tools:
                    match_score = self._compute_sequence_similarity(
                        current_tools, pattern.conditions.get('tool_sequence', [])
                    )
                    if match_score > 0.5:
                        matching_patterns.append((pattern, match_score))
            
            elif pattern.pattern_type == PatternType.PARAMETER_SET:
                # パラメータセットをマッチング
                if pattern.success_rate >= self.min_success_rate:
                    matching_patterns.append((pattern, pattern.confidence))
            
            elif pattern.pattern_type == PatternType.CONTEXT_CONDITION:
                # コンテキスト条件をチェック
                condition_key = list(pattern.conditions.keys())[0]
                if condition_key in context:
                    match_score = 1.0 - abs(
                        context[condition_key] - pattern.conditions[condition_key]
                    ) / max(abs(pattern.conditions[condition_key]), 1.0)
                    if match_score > 0.7:
                        matching_patterns.append((pattern, match_score))
        
        # 最良マッチを選択
        if matching_patterns:
            matching_patterns.sort(key=lambda x: x[1], reverse=True)
            best_pattern = matching_patterns[0][0]
            
            recommendations['tool_sequence'] = best_pattern.recommendations.get('recommended_tools')
            recommendations['parameters'] = best_pattern.recommendations.get('recommended_parameters')
            recommendations['confidence'] = best_pattern.confidence
        
        return recommendations
    
    def _compute_sequence_similarity(
        self,
        seq1: List[str],
        seq2: List[str],
    ) -> float:
        """2つのシーケンスの類似度を計算"""
        if not seq1 or not seq2:
            return 0.0
        
        # 簡易実装: 共通要素の割合
        common = len(set(seq1) & set(seq2))
        total = len(set(seq1) | set(seq2))
        
        return common / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """パターン統計を取得"""
        success_traces = [t for t in self.traces if t.success]
        success_rate = len(success_traces) / max(len(self.traces), 1)
        
        pattern_types = {}
        for pattern in self.patterns.values():
            key = pattern.pattern_type.value
            pattern_types[key] = pattern_types.get(key, 0) + 1
        
        avg_duration = (
            sum(t.duration_seconds for t in success_traces) / len(success_traces)
            if success_traces
            else 0.0
        )
        
        return {
            'total_traces': len(self.traces),
            'successful_traces': len(success_traces),
            'success_rate': success_rate,
            'patterns_discovered': len(self.patterns),
            'patterns_by_type': pattern_types,
            'avg_successful_duration': avg_duration,
        }
