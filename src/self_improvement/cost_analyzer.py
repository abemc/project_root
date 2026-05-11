"""
Phase 5: Cost Analyzer
コスト分析システム - API使用量、請求管理、ROI分析

Components:
- CostModel: コスト計算モデル
- BillingRecord: 請求記録
- CostBreakdown: コスト分析
- BudgetManager: 予算管理
- CostAnalyzer: 統合コスト分析システム
"""

import json
import logging
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import os

logger = logging.getLogger(__name__)


class CostMetricType(Enum):
    """コストメトリクスの種類"""
    TOKENS = "tokens"
    REQUESTS = "requests"
    INFERENCE_TIME = "inference_time"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"


class BillingPeriod(Enum):
    """請求期間"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class CostModel:
    """コスト計算モデル"""
    model_id: str
    pricing_per_1k_tokens: float  # $0.01 per 1K tokens など
    pricing_per_request: float  # $0.001 per request など
    pricing_per_hour_compute: float  # $10.00 per hour など
    
    # ボリューム割引
    enable_volume_discounts: bool = True
    volume_discount_tiers: Dict[int, float] = field(default_factory=dict)  # {tokens: discount_percent}
    
    # トラフィックに基づく料金モデル
    base_cost: float = 0.0  # 基本料金
    
    def calculate_token_cost(self, num_tokens: int) -> float:
        """トークンコストを計算"""
        base_cost = (num_tokens / 1000) * self.pricing_per_1k_tokens
        
        # ボリューム割引を適用
        if self.enable_volume_discounts:
            discount = 0.0
            for threshold, discount_pct in sorted(self.volume_discount_tiers.items()):
                if num_tokens >= threshold:
                    discount = discount_pct
            base_cost *= (1 - discount / 100)
        
        return base_cost
    
    def calculate_request_cost(self, num_requests: int) -> float:
        """リクエストコストを計算"""
        return num_requests * self.pricing_per_request
    
    def calculate_compute_cost(self, hours: float) -> float:
        """計算コストを計算"""
        return hours * self.pricing_per_hour_compute
    
    def calculate_total_cost(
        self,
        num_tokens: int = 0,
        num_requests: int = 0,
        compute_hours: float = 0
    ) -> float:
        """総コストを計算"""
        return (
            self.calculate_token_cost(num_tokens) +
            self.calculate_request_cost(num_requests) +
            self.calculate_compute_cost(compute_hours) +
            self.base_cost
        )


@dataclass
class BillingRecord:
    """請求記録"""
    billing_id: str
    period_start: str
    period_end: str
    
    # メトリクス
    total_tokens: int
    total_requests: int
    total_compute_hours: float
    
    # コスト明細
    token_cost: float
    request_cost: float
    compute_cost: float
    discount_applied: float = 0.0
    
    total_cost: float = 0.0
    
    # 追加情報
    model_id: str = ""
    currency: str = "USD"
    status: str = "generated"  # generated, sent, paid, overdue
    issue_date: str = ""
    due_date: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'BillingRecord':
        return cls(**d)
    
    def calculate_total(self) -> float:
        """総額を計算"""
        self.total_cost = (
            self.token_cost +
            self.request_cost +
            self.compute_cost -
            self.discount_applied
        )
        return self.total_cost


@dataclass
class CostBreakdown:
    """コスト分析結果"""
    analysis_id: str
    timestamp: str
    period_days: int
    
    # コストコンポーネント
    tokens_cost: float
    requests_cost: float
    compute_cost: float
    storage_cost: float = 0.0
    bandwidth_cost: float = 0.0
    
    # 割引
    volume_discount: float = 0.0
    promotional_discount: float = 0.0
    
    # サマリー
    total_cost: float = 0.0
    daily_average: float = 0.0
    monthly_projection: float = 0.0
    yearly_projection: float = 0.0
    
    # コスト効率
    cost_per_token: float = 0.0
    cost_per_request: float = 0.0
    cost_per_compute_hour: float = 0.0
    
    # トレンド
    cost_trend: str = "stable"  # increasing, stable, decreasing
    cost_growth_percent: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class BudgetManager:
    """予算管理システム"""
    
    def __init__(self, monthly_budget: float = 1000.0):
        self.monthly_budget = monthly_budget
        self.spent_this_month = 0.0
        self.alerts: List[Dict] = []
        self.budget_history: List[Dict] = []
    
    def record_spend(self, amount: float):
        """支出を記録"""
        self.spent_this_month += amount
        self.check_budget_alerts()
    
    def check_budget_alerts(self):
        """予算アラートをチェック"""
        percentage = (self.spent_this_month / self.monthly_budget) * 100
        
        if percentage >= 100:
            self.alerts.append({
                'type': 'CRITICAL',
                'message': f'Budget exceeded: {percentage:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        elif percentage >= 80:
            self.alerts.append({
                'type': 'WARNING',
                'message': f'Approaching budget limit: {percentage:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
        elif percentage >= 50:
            self.alerts.append({
                'type': 'INFO',
                'message': f'Half budget used: {percentage:.1f}%',
                'timestamp': datetime.now().isoformat()
            })
    
    def get_remaining_budget(self) -> float:
        """残り予算を取得"""
        return max(0, self.monthly_budget - self.spent_this_month)
    
    def get_budget_status(self) -> Dict[str, Any]:
        """予算ステータスを取得"""
        percentage = (self.spent_this_month / self.monthly_budget) * 100
        days_in_month = 30
        days_elapsed = (datetime.now().day - 1)  # Simplified
        expected_burn_rate = self.monthly_budget / days_in_month * days_elapsed
        
        return {
            'monthly_budget': self.monthly_budget,
            'spent': self.spent_this_month,
            'remaining': self.get_remaining_budget(),
            'percentage_used': percentage,
            'expected_burn_rate': expected_burn_rate,
            'projected_overage': max(0, self.spent_this_month - expected_burn_rate),
            'days_until_limit': self._estimate_days_until_limit()
        }
    
    def _estimate_days_until_limit(self) -> float:
        """予算制限までの日数を推定"""
        if self.spent_this_month <= 0:
            return 30.0
        
        avg_daily_spend = self.spent_this_month / max(1, datetime.now().day - 1)
        remaining = self.get_remaining_budget()
        
        if avg_daily_spend <= 0:
            return 30.0
        
        return remaining / avg_daily_spend


class CostAnalyzer:
    """統合コスト分析システム"""
    
    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        logs_dir: str = "logs/cost_analysis"
    ):
        self.logs_dir = logs_dir
        os.makedirs(logs_dir, exist_ok=True)
        
        # デフォルトコストモデル (GPT-3.5相当)
        self.cost_model = cost_model or CostModel(
            model_id="default_model",
            pricing_per_1k_tokens=0.0015,  # $0.0015 per 1K tokens
            pricing_per_request=0.0001,
            pricing_per_hour_compute=10.0,
            volume_discount_tiers={
                1000000: 10,   # 100M tokens: 10% discount
                10000000: 20,  # 1B tokens: 20% discount
            }
        )
        
        self.budget_manager = BudgetManager(monthly_budget=1000.0)
        
        self.billing_records: Dict[str, BillingRecord] = {}
        self.cost_history: List[CostBreakdown] = []
        
        self._load_history()
    
    def _load_history(self):
        """履歴を読み込み"""
        # Billing records
        billing_file = os.path.join(self.logs_dir, "billing_records.jsonl")
        if os.path.exists(billing_file):
            try:
                with open(billing_file, 'r') as f:
                    for line in f:
                        record_dict = json.loads(line)
                        record = BillingRecord.from_dict(record_dict)
                        self.billing_records[record.billing_id] = record
                logger.info(f"Loaded {len(self.billing_records)} billing records")
            except Exception as e:
                logger.error(f"Failed to load billing records: {e}")
        
        # Cost history
        cost_file = os.path.join(self.logs_dir, "cost_history.jsonl")
        if os.path.exists(cost_file):
            try:
                with open(cost_file, 'r') as f:
                    for line in f:
                        breakdown_dict = json.loads(line)
                        # Recreate CostBreakdown
                        self.cost_history.append(CostBreakdown(**breakdown_dict))
                logger.info(f"Loaded {len(self.cost_history)} cost analyses")
            except Exception as e:
                logger.error(f"Failed to load cost history: {e}")
    
    def record_api_usage(
        self,
        num_tokens: int,
        num_requests: int = 1,
        compute_hours: float = 0
    ):
        """API使用量を記録"""
        total_cost = self.cost_model.calculate_total_cost(
            num_tokens=num_tokens,
            num_requests=num_requests,
            compute_hours=compute_hours
        )
        self.budget_manager.record_spend(total_cost)
    
    def analyze_costs(
        self,
        usage_data: Dict[str, int],
        period_days: int = 30
    ) -> CostBreakdown:
        """コスト分析を実行"""
        analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # メトリクスを抽出
        total_tokens = usage_data.get('total_tokens', 0)
        total_requests = usage_data.get('total_requests', 0)
        total_compute_hours = usage_data.get('total_compute_hours', 0)
        
        # コストを計算
        tokens_cost = self.cost_model.calculate_token_cost(total_tokens)
        requests_cost = self.cost_model.calculate_request_cost(total_requests)
        compute_cost = self.cost_model.calculate_compute_cost(total_compute_hours)
        
        total_cost = tokens_cost + requests_cost + compute_cost
        
        # コスト効率を計算
        cost_per_token = tokens_cost / max(total_tokens, 1)
        cost_per_request = requests_cost / max(total_requests, 1)
        cost_per_compute_hour = compute_cost / max(total_compute_hours, 1)
        
        # 予測
        daily_average = total_cost / max(period_days, 1)
        monthly_projection = daily_average * 30
        yearly_projection = daily_average * 365
        
        # トレンドを分析
        cost_trend = "stable"
        cost_growth_percent = 0.0
        
        if len(self.cost_history) > 0:
            prev_cost = self.cost_history[-1].total_cost
            growth = ((total_cost - prev_cost) / max(prev_cost, 1)) * 100
            cost_growth_percent = growth
            
            if growth > 5:
                cost_trend = "increasing"
            elif growth < -5:
                cost_trend = "decreasing"
        
        breakdown = CostBreakdown(
            analysis_id=analysis_id,
            timestamp=datetime.now().isoformat(),
            period_days=period_days,
            tokens_cost=tokens_cost,
            requests_cost=requests_cost,
            compute_cost=compute_cost,
            total_cost=total_cost,
            daily_average=daily_average,
            monthly_projection=monthly_projection,
            yearly_projection=yearly_projection,
            cost_per_token=cost_per_token,
            cost_per_request=cost_per_request,
            cost_per_compute_hour=cost_per_compute_hour,
            cost_trend=cost_trend,
            cost_growth_percent=cost_growth_percent
        )
        
        self.cost_history.append(breakdown)
        
        # ファイルに保存
        cost_file = os.path.join(self.logs_dir, "cost_history.jsonl")
        try:
            with open(cost_file, 'a') as f:
                f.write(json.dumps(breakdown.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to save cost analysis: {e}")
        
        return breakdown
    
    def generate_billing_report(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> BillingRecord:
        """請求レポートを生成"""
        billing_id = f"bill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 使用量をシミュレート (実運用ではデータベースから取得)
        total_tokens_estimated = 1000000  # 1M tokens
        total_requests_estimated = 5000
        total_hours_estimated = 10.0
        
        # コストを計算
        token_cost = self.cost_model.calculate_token_cost(total_tokens_estimated)
        request_cost = self.cost_model.calculate_request_cost(total_requests_estimated)
        compute_cost = self.cost_model.calculate_compute_cost(total_hours_estimated)
        
        # 割引を計算
        discount_applied = 0.0
        total_before_discount = token_cost + request_cost + compute_cost
        if total_before_discount > 500:
            discount_applied = total_before_discount * 0.05  # 5% 割引
        
        record = BillingRecord(
            billing_id=billing_id,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            total_tokens=total_tokens_estimated,
            total_requests=total_requests_estimated,
            total_compute_hours=total_hours_estimated,
            token_cost=token_cost,
            request_cost=request_cost,
            compute_cost=compute_cost,
            discount_applied=discount_applied,
            model_id=self.cost_model.model_id,
            issue_date=datetime.now().isoformat(),
            due_date=(datetime.now() + timedelta(days=30)).isoformat()
        )
        
        record.calculate_total()
        self.billing_records[billing_id] = record
        
        # ファイルに保存
        billing_file = os.path.join(self.logs_dir, "billing_records.jsonl")
        try:
            with open(billing_file, 'a') as f:
                f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to save billing record: {e}")
        
        return record
    
    def calculate_roi(
        self,
        total_cost: float,
        improvement_metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """ROI (Return on Investment) を計算"""
        
        # 改善から得られる価値を推定
        # 例: 10% のエラー削減 = 月間1000件のリクエスト削減可能
        error_reduction = improvement_metrics.get('error_reduction_percent', 0) / 100
        latency_improvement = improvement_metrics.get('latency_improvement_percent', 0) / 100
        token_savings = improvement_metrics.get('token_savings_percent', 0) / 100
        
        # 価値を計算
        estimated_error_cost_saved = 5000 * error_reduction  # 月間エラーコスト: $5000
        estimated_latency_value = 2000 * latency_improvement  # レイテンシ改善の価値: $2000/月
        estimated_token_savings_value = 1000 * token_savings  # トークン削減の価値: $1000
        
        total_value = (
            estimated_error_cost_saved +
            estimated_latency_value +
            estimated_token_savings_value
        )
        
        roi_percent = ((total_value - total_cost) / max(total_cost, 1)) * 100
        payback_months = total_cost / max(total_value / 12, 1)
        
        return {
            'total_investment': total_cost,
            'estimated_monthly_value': total_value / 12,
            'estimated_annual_value': total_value,
            'roi_percent': roi_percent,
            'payback_period_months': payback_months,
            'break_even_month': payback_months
        }
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """コストサマリーを取得"""
        if not self.cost_history:
            return {}
        
        recent_costs = [c.total_cost for c in self.cost_history[-12:]]  # 直近12ヶ月
        
        return {
            'current_monthly_cost': self.cost_history[-1].total_cost if self.cost_history else 0,
            'average_monthly_cost': statistics.mean(recent_costs) if recent_costs else 0,
            'min_monthly_cost': min(recent_costs) if recent_costs else 0,
            'max_monthly_cost': max(recent_costs) if recent_costs else 0,
            'budget': self.budget_manager.monthly_budget,
            'budget_status': self.budget_manager.get_budget_status(),
            'cost_trend': self.cost_history[-1].cost_trend if self.cost_history else "unknown"
        }
    
    def get_cost_forecast(self, months: int = 3) -> Dict[str, float]:
        """コスト予測を取得"""
        if not self.cost_history:
            return {}
        
        recent_costs = [c.total_cost for c in self.cost_history[-6:]]  # 直近6ヶ月
        if len(recent_costs) < 2:
            return {'trend': 'insufficient_data'}
        
        # 簡単な線形トレンド
        avg_recent = statistics.mean(recent_costs)
        growth_rate = (recent_costs[-1] - recent_costs[0]) / max(recent_costs[0], 1)
        
        forecast = {}
        for i in range(1, months + 1):
            forecast[f'month_{i}'] = avg_recent * (1 + (growth_rate / 6) * i)
        
        return forecast
    
    def get_billing_history(self, limit: int = 12) -> List[BillingRecord]:
        """請求履歴を取得"""
        records = list(self.billing_records.values())
        records.sort(key=lambda r: r.period_start, reverse=True)
        return records[:limit]
    
    def export_cost_report(self, filename: str = "cost_report.json"):
        """コストレポートをエクスポート"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'cost_summary': self.get_cost_summary(),
            'recent_analyses': [c.to_dict() for c in self.cost_history[-12:]],
            'billing_records': [r.to_dict() for r in self.get_billing_history()],
            'budget_status': self.budget_manager.get_budget_status()
        }
        
        filepath = os.path.join(self.logs_dir, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Exported cost report to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to export cost report: {e}")
            return None
