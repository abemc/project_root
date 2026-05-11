"""動的プロンプト最適化モジュール

フィードバックを基にプロンプトテンプレートを動的に調整し、
より高い品質な回答を引き出します。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """プロンプトテンプレート"""
    name: str
    template: str
    system_prompt: str
    created_at: str
    success_rate: float = 0.0
    usage_count: int = 0
    average_rating: float = 0.5
    tags: List[str] = None
    description: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class PromptOptimizer:
    """フィードバックに基づくプロンプト最適化"""
    
    def __init__(self, storage_dir: str = None):
        """
        Args:
            storage_dir: プロンプトテンプレート保存先
        """
        if storage_dir is None:
            storage_dir = Path("logs/prompts")
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.templates_file = self.storage_dir / "templates.jsonl"
        self.performance_file = self.storage_dir / "performance.json"
        
        # テンプレートキャッシュ
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_templates()
        
        # デフォルトテンプレートを初期化
        self._init_default_templates()
    
    def _load_templates(self):
        """保存されたテンプレートを読み込む"""
        if self.templates_file.exists():
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            template = PromptTemplate(**data)
                            self.templates[template.name] = template
                logger.info(f"Loaded {len(self.templates)} prompt templates")
            except Exception as e:
                logger.error(f"Failed to load templates: {e}")
    
    def _init_default_templates(self):
        """デフォルトテンプレートの初期化"""
        if not self.templates:
            self.register_template(
                name="default",
                template="{context}\n\n質問: {query}\n\n答え:",
                system_prompt="あなたは有用で正確なアシスタントです。質問に対して簡潔で正確に答えてください。",
                description="基本的なテンプレート"
            )
            self.register_template(
                name="detailed",
                template="{context}\n\n質問: {query}\n\nステップバイステップで詳しく説明してください:",
                system_prompt="あなたは専門的で詳細なアシスタントです。質問に対して段階的に詳しく説明してください。",
                description="詳細説明用テンプレート"
            )
            self.register_template(
                name="concise",
                template="{context}\n\nQ: {query}\nA:",
                system_prompt="あなたは簡潔で効率的なアシスタントです。質問に対して短く、要点を押さえた回答をしてください。",
                description="簡潔回答用テンプレート"
            )
    
    def register_template(
        self,
        name: str,
        template: str,
        system_prompt: str,
        description: str = "",
        tags: List[str] = None,
    ) -> PromptTemplate:
        """
        新しいプロンプトテンプレートを登録
        
        Args:
            name: テンプレート名
            template: プロンプトテンプレート（{context}, {query}プレースホルダー対応）
            system_prompt: システムプロンプト
            description: 説明
            tags: タグ
        """
        prompt = PromptTemplate(
            name=name,
            template=template,
            system_prompt=system_prompt,
            created_at=datetime.now().isoformat(),
            description=description,
            tags=tags or [],
        )
        
        self.templates[name] = prompt
        
        # ディスクに保存
        self._save_template(prompt)
        logger.info(f"Registered prompt template: {name}")
        
        return prompt
    
    def _save_template(self, template: PromptTemplate):
        """テンプレートをディスクに保存"""
        try:
            with open(self.templates_file, 'a', encoding='utf-8') as f:
                data = {
                    "name": template.name,
                    "template": template.template,
                    "system_prompt": template.system_prompt,
                    "created_at": template.created_at,
                    "success_rate": template.success_rate,
                    "usage_count": template.usage_count,
                    "average_rating": template.average_rating,
                    "tags": template.tags,
                    "description": template.description,
                }
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save template: {e}")
    
    def get_template(self, name: str) -> PromptTemplate:
        """テンプレートを取得"""
        if name not in self.templates:
            logger.warning(f"Template not found: {name}, using default")
            return self.templates.get("default")
        return self.templates[name]
    
    def get_best_template(self) -> PromptTemplate:
        """最も高性能なテンプレートを取得"""
        best = max(
            self.templates.values(),
            key=lambda t: t.average_rating if t.usage_count > 0 else 0
        )
        return best
    
    def get_templates_for_query_type(self, query_type: str) -> List[PromptTemplate]:
        """
        クエリタイプに適したテンプレートを取得
        
        Args:
            query_type: クエリタイプ (question, summary, creative, etc.)
        """
        return [
            t for t in self.templates.values()
            if query_type in t.tags or query_type.lower() in t.description.lower()
        ]
    
    def format_prompt(
        self,
        query: str,
        template_name: str = "best",
        context: str = "",
    ) -> tuple[str, str]:
        """
        プロンプトをフォーマット
        
        Args:
            query: ユーザーのクエリ
            template_name: 使用するテンプレート名（"best"の場合は最高性能のものを使用）
            context: コンテキスト情報
        
        Returns:
            (システムプロンプト, ユーザープロンプト)のタプル
        """
        if template_name == "best":
            template = self.get_best_template()
        else:
            template = self.get_template(template_name)
        
        # プロンプトをフォーマット
        user_prompt = template.template.format(
            context=context.strip(),
            query=query.strip()
        )
        
        # 使用カウント更新
        template.usage_count += 1
        
        return template.system_prompt, user_prompt
    
    def update_template_performance(
        self,
        template_name: str,
        rating: float,
    ):
        """
        テンプレートの性能を更新
        
        Args:
            template_name: テンプレート名
            rating: ユーザー評価（0.0-1.0）
        """
        if template_name not in self.templates:
            logger.warning(f"Template not found: {template_name}")
            return
        
        template = self.templates[template_name]
        
        # 移動平均で更新
        total_ratings = template.average_rating * max(1, template.usage_count - 1)
        template.average_rating = (total_ratings + rating) / max(1, template.usage_count)
        
        # 成功率を更新（0.7以上を成功と見なす）
        if template.usage_count > 0:
            template.success_rate = len([1 for r in [rating] if r >= 0.7]) / template.usage_count
        
        logger.info(
            f"Updated template performance: {template_name} "
            f"(avg_rating: {template.average_rating:.3f}, success_rate: {template.success_rate:.2%})"
        )
    
    def generate_optimized_template(
        self,
        feedback_items: List[Dict[str, Any]],
        low_rating_threshold: float = 0.5,
    ) -> Optional[PromptTemplate]:
        """
        低評価フィードバックから最適化されたテンプレートを生成
        
        Args:
            feedback_items: フィードバック項目。"rating"と"suggestions"を含む
            low_rating_threshold: 改善対象とする評価閾値
        
        Returns:
            生成されたPromptTemplate
        """
        # 低評価フィードバックを収集
        poor_feedback = [
            f for f in feedback_items
            if f.get("rating", 1.0) < low_rating_threshold
        ]
        
        if not poor_feedback:
            logger.info("No poor feedback to optimize from")
            return None
        
        # パターン分析
        improvement_suggestions = [
            f.get("suggestions", "") for f in poor_feedback
            if f.get("suggestions")
        ]
        
        if not improvement_suggestions:
            return None
        
        # 提案から最適化されたシステムプロンプトを生成
        # 実装例：LLMで生成するか、規則ベースで生成
        optimized_system = self._analyze_suggestions(improvement_suggestions)
        
        # 新しいテンプレートを登録
        template_name = f"optimized_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_template = self.register_template(
            name=template_name,
            template="{context}\n\n質問: {query}\n\n答え:",
            system_prompt=optimized_system,
            description=f"最適化テンプレート (基づく: {len(poor_feedback)}件の低評価フィードバック)",
            tags=["optimized"],
        )
        
        return new_template
    
    def _analyze_suggestions(self, suggestions: List[str]) -> str:
        """
        提案を分析してシステムプロンプトを生成
        """
        # 簡単な規則ベースの分析
        if any("詳しく" in s for s in suggestions):
            return "あなたは詳細で説明的なアシスタントです。ユーザーの質問に対して、段階的に詳しく回答してください。"
        elif any("簡潔" in s for s in suggestions):
            return "あなたは簡潔で効率的なアシスタントです。ユーザーの質問に対して、短く要点を押さえた回答をしてください。"
        elif any("正確" in s for s in suggestions):
            return "あなたは正確で信頼できるアシスタントです。ユーザーの質問に対して、事実に基づいた正確な回答をしてください。"
        else:
            return "あなたは有用で高品質なアシスタントです。ユーザーの質問に対して、分かりやすく有用な回答をしてください。"
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """すべてのテンプレートをリスト"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "usage_count": t.usage_count,
                "average_rating": t.average_rating,
                "success_rate": f"{t.success_rate:.2%}",
                "tags": t.tags,
            }
            for t in sorted(
                self.templates.values(),
                key=lambda t: t.average_rating * t.usage_count,
                reverse=True
            )
        ]
