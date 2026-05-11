#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自律型 RAG Agent
バックアップ・リストア機能付き設定管理を統合した自律実行型エージェント

使用方法:
    python autonomous_rag_agent.py --query "質問文"
    python autonomous_rag_agent.py --backup
    python autonomous_rag_agent.py --restore
    python autonomous_rag_agent.py --list-backups
    python autonomous_rag_agent.py --show-config
    python autonomous_rag_agent.py --export-config <filename>
    python autonomous_rag_agent.py --import-config <filename>
"""

import sys
import json
import argparse
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from docs_manager import DocumentManager
from rag_agent_config import RAGAgentConfig

try:
    from src.rag.retriever import Retriever
    retriever_available = True
except ImportError:
    Retriever = None
    retriever_available = False

try:
    from src.rag.llm import call_llm
    llm_available = True
except ImportError:
    call_llm = None
    llm_available = False

try:
    from src.ethics.ethics_monitor import EthicsMonitor, EthicsStatus
    ethics_available = True
except ImportError:
    EthicsMonitor = None
    EthicsStatus = None
    ethics_available = False


class AutonomousRAGAgent:
    """自律型 RAG エージェント"""
    
    def __init__(self):
        """初期化"""
        self.config_manager = RAGAgentConfig()
        self.config = self.config_manager.load_config()
        self.document_manager = DocumentManager()
        self.retriever = self._load_retriever()
        self.ethics_monitor = EthicsMonitor() if ethics_available else None
        self.ethics_log_path = Path(__file__).resolve().parent / "logs" / "ethics_audit.jsonl"
        self.response_log_path = Path(__file__).resolve().parent / "logs" / "agent_responses.jsonl"
        self.log_max_bytes = self._safe_int(
            os.getenv("RAG_LOG_MAX_BYTES", self.config.get("log_max_bytes", 5 * 1024 * 1024)),
            5 * 1024 * 1024,
        )
        self.log_backup_count = self._safe_int(
            os.getenv("RAG_LOG_BACKUP_COUNT", self.config.get("log_backup_count", 3)),
            3,
        )
        print(f"✅ RAG Agent 初期化完了")
        print(f"   設定ファイル: {self.config_manager.config_file}")
        print(f"   バックアップ保存先: {self.config_manager.backup_dir}")

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        """int変換に失敗した場合は既定値を返す。"""
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    def _rotate_jsonl_if_needed(self, path: Path) -> None:
        """ファイルサイズが閾値超過時に JSONL を世代ローテーションする。"""
        if self.log_max_bytes <= 0 or self.log_backup_count <= 0 or not path.exists():
            return

        try:
            if path.stat().st_size < self.log_max_bytes:
                return

            oldest = path.with_name(f"{path.name}.{self.log_backup_count}")
            if oldest.exists():
                oldest.unlink()

            for i in range(self.log_backup_count - 1, 0, -1):
                src = path.with_name(f"{path.name}.{i}")
                dst = path.with_name(f"{path.name}.{i + 1}")
                if src.exists():
                    src.rename(dst)

            path.rename(path.with_name(f"{path.name}.1"))
        except Exception as exc:
            print(f"⚠️ ログローテーションに失敗 ({path.name}): {exc}")

    def _persist_jsonl(self, path: Path, payload: Dict[str, Any], error_prefix: str) -> None:
        """JSONL保存（必要に応じてローテーション）を行う。"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_jsonl_if_needed(path)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            print(f"⚠️ {error_prefix}: {exc}")

    def _load_retriever(self):
        """Corpus 検索用 Retriever を初期化する。"""
        if not retriever_available:
            return None

        corpus_path = Path(__file__).resolve().parent / "corpus"
        index_path = corpus_path / "corpus.index"
        meta_path = corpus_path / "corpus_meta.json"

        try:
            return Retriever(index_path=index_path, meta_path=meta_path)
        except Exception as exc:
            print(f"⚠️ Retriever 初期化エラー: {exc}")
            return None

    def _search_corpus(self, question: str, top_k: int) -> List[Dict]:
        """設定に応じて Corpus を検索する。"""
        if not self.retriever:
            return []

        search_method = self.config.get('search_method', 'ハイブリッド')

        if search_method == 'BM25':
            return self.retriever.search_keyword(question, top_k=top_k)
        if search_method == 'ベクトル検索':
            return self.retriever.search(question, top_k=top_k)
        return self.retriever.hybrid_search(question, top_k=top_k)

    def _format_sources(self, docs: List[Dict]) -> List[Dict]:
        """Retriever 結果を既存 UI 用のソース情報に整形する。"""
        doc_lookup = {doc['name']: doc for doc in self.document_manager.documents}
        sources = []

        for doc in docs:
            meta = doc.get('meta', {})
            source_name = meta.get('source') or doc.get('source') or doc.get('id', 'unknown')
            doc_info = doc_lookup.get(source_name, {})
            sources.append({
                'name': source_name,
                'category': doc_info.get('category', meta.get('category', 'knowledge_base')),
                'path': doc_info.get('path', meta.get('path', 'corpus/corpus_meta.json')),
                'score': float(doc.get('score', 0.0)),
                'text': doc.get('text', ''),
            })

        return sources

    def _estimate_confidence(self, sources: List[Dict]) -> float:
        """参照件数とスコアから簡易信頼度を推定する。"""
        if not sources:
            return 0.10

        top_score = max(float(s.get("score", 0.0)) for s in sources)
        source_factor = min(len(sources), 5) / 5.0
        score_factor = max(0.0, min(top_score, 1.0))

        # 件数と類似度を等重みでブレンド
        confidence = (source_factor * 0.5) + (score_factor * 0.5)
        return round(confidence, 2)

    def _build_rag_prompt(self, question: str, sources: List[Dict]) -> str:
        """RAG回答用のプロンプトを構築する。"""
        context_blocks = []
        for i, src in enumerate(sources[:5], 1):
            text = (src.get("text") or "").strip()
            preview = text[:800] if text else "（本文なし）"
            context_blocks.append(
                f"[{i}] source={src.get('name', 'unknown')} score={src.get('score', 0.0):.4f}\n{preview}"
            )

        context_text = "\n\n".join(context_blocks) if context_blocks else "（参照コンテキストなし）"

        return (
            "以下の参照情報を使って、質問に日本語で回答してください。\n"
            "要件:\n"
            "1. 断定しすぎず、根拠が弱い部分は不確実性を明示する\n"
            "2. 最後に『参照ソース』として source 名を箇条書きで列挙する\n"
            "3. 参照情報にない内容は推測で埋めすぎない\n\n"
            f"[質問]\n{question}\n\n"
            f"[参照情報]\n{context_text}\n"
        )

    def _generate_answer_with_llm(self, question: str, sources: List[Dict]) -> Tuple[str, str]:
        """LLMで回答を生成する。戻り値は (answer, generation_mode)。"""
        if not llm_available:
            return self._generate_answer(question, sources), "fallback-no-llm"

        prompt = self._build_rag_prompt(question, sources)
        model = self.config.get("llm_model", "qwen2.5:7b")
        temperature = float(self.config.get("temperature", 0.3))
        max_tokens = int(self.config.get("max_tokens", 2048))

        system_prompt = (
            "あなたは根拠重視のRAGアシスタントです。"
            "回答では根拠と不確実性を明確に示し、参照ソース名を必ず記載してください。"
        )

        # 軽い自己修正: 1回失敗したら低温度で再試行
        answer = call_llm(
            prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if isinstance(answer, str) and answer.startswith("Error"):
            answer_retry = call_llm(
                prompt,
                model=model,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=max_tokens,
            )
            if isinstance(answer_retry, str) and not answer_retry.startswith("Error"):
                return answer_retry, "llm-retry"
            return self._generate_answer(question, sources), "fallback-llm-error"

        if not isinstance(answer, str) or not answer.strip():
            return self._generate_answer(question, sources), "fallback-empty"

        return answer.strip(), "llm"

    def _audit_answer(self, question: str, answer: str, sources: List[Dict]) -> Dict:
        """倫理監査を実行し、監査結果を辞書で返す。"""
        if not self.ethics_monitor:
            return {
                "enabled": False,
                "response_id": None,
                "status": "not_available",
                "overall_score": None,
                "violations": [],
            }

        response_id = datetime.now().strftime("%Y%m%d%H%M%S")
        metadata = {
            "response_id": response_id,
            "question": question,
            "source_count": len(sources),
        }
        audit = self.ethics_monitor.audit_response(response_id=response_id, response=answer, metadata=metadata)

        audit_result = {
            "enabled": True,
            "response_id": response_id,
            "status": audit.status.value,
            "overall_score": round(float(audit.overall_score), 3),
            "violations": audit.violations,
            "transparency_score": round(float(audit.transparency.score), 3) if audit.transparency else None,
        }
        self._persist_ethics_audit(question=question, sources=sources, audit_result=audit_result)
        return audit_result

    def _persist_ethics_audit(self, question: str, sources: List[Dict], audit_result: Dict[str, Any]) -> None:
        """倫理監査結果を JSONL で追記保存する。"""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "source_count": len(sources),
            "source_names": [s.get("name", "unknown") for s in sources[:10]],
            "audit": audit_result,
        }
        self._persist_jsonl(self.ethics_log_path, payload, "倫理監査ログ保存に失敗")

    def _compute_risk_assessment(self, confidence: float, ethics_audit: Dict[str, Any]) -> Dict[str, Any]:
        """信頼度と倫理監査を統合した複合リスクを計算する。"""
        ethics_status = ethics_audit.get("status", "not_available")
        ethics_score = ethics_audit.get("overall_score")
        if ethics_score is None:
            ethics_score = 0.6

        # リスクは 0 に近いほど低く、1 に近いほど高い
        confidence_risk = 1.0 - max(0.0, min(float(confidence), 1.0))
        ethics_risk = 1.0 - max(0.0, min(float(ethics_score), 1.0))
        status_penalty = 0.0
        if ethics_status == "warning":
            status_penalty = 0.15
        elif ethics_status == "fail":
            status_penalty = 0.30

        risk_score = min(1.0, round((confidence_risk * 0.5) + (ethics_risk * 0.5) + status_penalty, 3))

        if risk_score >= 0.75:
            level = "high"
        elif risk_score >= 0.45:
            level = "medium"
        else:
            level = "low"

        return {
            "risk_score": risk_score,
            "risk_level": level,
            "confidence_risk": round(confidence_risk, 3),
            "ethics_risk": round(ethics_risk, 3),
            "ethics_status": ethics_status,
        }

    def _persist_response_log(self, payload: Dict[str, Any]) -> None:
        """応答情報を JSONL で追記保存する。"""
        self._persist_jsonl(self.response_log_path, payload, "応答ログ保存に失敗")

    def get_ethics_report(self, period_hours: int = 24) -> Dict[str, Any]:
        """倫理監査サマリーを取得する。"""
        if not self.ethics_monitor:
            return {
                "enabled": False,
                "message": "EthicsMonitor が利用できません",
            }
        report = self.ethics_monitor.get_ethics_report(time_period_hours=period_hours)
        report["enabled"] = True
        report["log_path"] = str(self.ethics_log_path)
        return report

    def _build_ethics_block_message(self, ethics_audit: Dict) -> str:
        """倫理違反時の差し替えメッセージを作成する。"""
        violations = ethics_audit.get("violations", [])
        violation_text = "\n".join([f"- {v}" for v in violations]) if violations else "- 詳細情報なし"
        return (
            "【安全上の理由により回答を保留しました】\n"
            "倫理監査で懸念が検出されたため、回答本文の表示を中止しました。\n"
            "\n"
            "検出内容:\n"
            f"{violation_text}\n"
            "\n"
            "質問を具体化するか、表現を中立化して再実行してください。"
        )
    
    def query(
        self,
        question: str,
        verbose: bool = False,
        strict_ethics: bool = False,
        save_response_log: bool = False,
    ) -> Dict:
        """
        質問を処理してRAG応答を生成
        
        Args:
            question: ユーザーの質問
            verbose: 詳細出力フラグ
        
        Returns:
            応答情報を含む辞書
        """
        # 日時に関する単純な問いはシステム時刻で応答する（LLM が利用不可のときのフォールバック）
        q_lower = (question or "").lower()
        date_keywords = ["今日", "何月", "何日", "何年", "現在の日付", "今日の日付", "今何日", "今の時刻", "現在の時刻", "日時"]
        if any(kw in q_lower for kw in date_keywords):
            now = datetime.now()
            date_str = now.strftime("%Y年%m月%d日")
            time_str = now.strftime("%H:%M:%S")
            answer = f"現在の日付は {date_str}、時刻は {time_str} です。"
            response = {
                "question": question,
                "answer": answer,
                "sources": [],
                "model": self.config.get('llm_model'),
                "search_method": self.config.get('search_method'),
                "timestamp": now.isoformat(),
                "source_count": 0,
                "confidence": 1.0,
                "needs_human_review": False,
                "execution_trace": [{"step": 0, "action": "date_fallback", "result": "system_time"}],
                "ethics_audit": {"enabled": False},
                "risk_assessment": {"risk_score": 0.0, "risk_level": "low"},
            }
            if save_response_log:
                self._persist_response_log(response)
            return response

        if verbose:
            print(f"\n📤 質問処理開始")
            print(f"   質問: {question}")
            print(f"   モデル: {self.config['llm_model']}")
            print(f"   検索方式: {self.config['search_method']}")
        
        top_k = self.config.get('top_k', 5)
        selected_docs = self._search_corpus(question, top_k)

        if not selected_docs:
            search_results = self.document_manager.search(question)
            selected_docs = search_results[:top_k]
            sources = [
                {
                    "name": doc['name'],
                    "category": doc['category'],
                    "path": doc['path'],
                    "score": 0.85,
                    "text": "",
                }
                for doc in selected_docs
            ]
        else:
            sources = self._format_sources(selected_docs)
        
        if verbose:
            print(f"   検索結果: {len(selected_docs)} 件")
        
        answer, generation_mode = self._generate_answer_with_llm(question, sources)
        confidence = self._estimate_confidence(sources)
        ethics_audit = self._audit_answer(question=question, answer=answer, sources=sources)
        risk_assessment = self._compute_risk_assessment(confidence=confidence, ethics_audit=ethics_audit)
        needs_human_review = (
            confidence < 0.45
            or ethics_audit.get("status") in ("warning", "fail")
            or risk_assessment.get("risk_score", 0.0) >= 0.45
        )

        strict_blocked = (
            strict_ethics
            and (
                ethics_audit.get("status") in ("warning", "fail")
                or risk_assessment.get("risk_level") == "high"
            )
        )
        if strict_blocked:
            answer = self._build_ethics_block_message(ethics_audit)

        execution_trace = [
            {
                "step": 1,
                "action": "search_corpus",
                "result": f"sources={len(sources)}"
            },
            {
                "step": 2,
                "action": "generate_answer",
                "result": generation_mode
            },
            {
                "step": 3,
                "action": "ethics_audit",
                "result": ethics_audit.get("status", "not_available")
            },
            {
                "step": 4,
                "action": "risk_gate",
                "result": "blocked" if strict_blocked else "passed"
            }
        ]
        
        response = {
            "question": question,
            "answer": answer,
            "sources": sources,
            "model": self.config['llm_model'],
            "search_method": self.config['search_method'],
            "timestamp": datetime.now().isoformat(),
            "source_count": len(sources),
            "confidence": confidence,
            "needs_human_review": needs_human_review,
            "execution_trace": execution_trace,
            "ethics_audit": ethics_audit,
            "risk_assessment": risk_assessment,
        }

        if save_response_log:
            self._persist_response_log(response)
        
        return response
    
    def _generate_answer(self, question: str, docs: List[Dict]) -> str:
        """応答を生成（ダミー実装）"""
        return f"""
【質問】
{question}

【参照ドキュメント】
{len(docs)}個のドキュメントを参照して回答しました:
{chr(10).join([f"  • {doc['name']}" for doc in docs[:3]])}

【応答】
質問の主題を分析し、{len(docs)}個の関連ドキュメントから情報を統合しました。
詳細は参照ドキュメントを確認してください。
"""
    
    def backup_config(self, verbose: bool = False) -> bool:
        """
        設定をバックアップ
        
        Args:
            verbose: 詳細出力フラグ
        
        Returns:
            成功フラグ
        """
        try:
            backup_file = self.config_manager.backup_config()
            if verbose:
                print(f"✅ 設定をバックアップしました")
                print(f"   ファイル: {backup_file}")
            return True
        except Exception as e:
            print(f"❌ バックアップエラー: {str(e)}")
            return False
    
    def restore_config(self, backup_file: Optional[str] = None, verbose: bool = False) -> bool:
        """
        設定をリストア
        
        Args:
            backup_file: リストアするバックアップファイル（None=最新）
            verbose: 詳細出力フラグ
        
        Returns:
            成功フラグ
        """
        try:
            if self.config_manager.restore_config(backup_file):
                self.config = self.config_manager.load_config()  # 設定を再読み込み
                if verbose:
                    if backup_file:
                        print(f"✅ 設定をリストアしました: {backup_file}")
                    else:
                        print(f"✅ 最新のバックアップからリストアしました")
                return True
            else:
                print(f"❌ リストアファイルが見つかりません")
                return False
        except Exception as e:
            print(f"❌ リストアエラー: {str(e)}")
            return False
    
    def list_backups(self, verbose: bool = True) -> List[Dict]:
        """
        バックアップ一覧を表示
        
        Args:
            verbose: 詳細出力フラグ
        
        Returns:
            バックアップ情報のリスト
        """
        backups = self.config_manager.get_backups_list()
        
        if verbose:
            if not backups:
                print("📭 バックアップがありません")
            else:
                print(f"\n📋 バックアップ履歴 ({len(backups)} 個)")
                print("-" * 70)
                for idx, backup in enumerate(backups, 1):
                    size_mb = backup['size'] / (1024 * 1024)
                    print(f"{idx}. {backup['name']}")
                    print(f"   📅 {backup['modified']}")
                    print(f"   📊 {size_mb:.2f} MB")
                print("-" * 70)
        
        return backups
    
    def show_config(self, verbose: bool = True) -> Dict:
        """
        現在の設定を表示
        
        Args:
            verbose: 詳細出力フラグ
        
        Returns:
            設定情報
        """
        if verbose:
            print(f"\n⚙️ 現在の RAG Agent 設定")
            print("-" * 70)
            print(self.config_manager.get_config_summary())
            print("-" * 70)
        
        return self.config
    
    def export_config(self, filename: str, verbose: bool = False) -> bool:
        """
        設定をエクスポート
        
        Args:
            filename: エクスポート先ファイル名
            verbose: 詳細出力フラグ
        
        Returns:
            成功フラグ
        """
        try:
            export_path = Path(filename)
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            if verbose:
                print(f"✅ 設定をエクスポートしました")
                print(f"   ファイル: {export_path.absolute()}")
            return True
        except Exception as e:
            print(f"❌ エクスポートエラー: {str(e)}")
            return False
    
    def import_config(self, filename: str, verbose: bool = False) -> bool:
        """
        設定をインポート
        
        Args:
            filename: インポート元ファイル名
            verbose: 詳細出力フラグ
        
        Returns:
            成功フラグ
        """
        try:
            import_path = Path(filename)
            if not import_path.exists():
                print(f"❌ ファイルが見つかりません: {filename}")
                return False
            
            with open(import_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
            
            # バリデーション
            if not self.config_manager.validate_config(new_config):
                print(f"❌ 設定の検証に失敗しました")
                return False
            
            # バックアップを作成してから上書き
            self.config_manager.backup_config()
            self.config_manager.save_config(new_config)
            self.config = new_config
            
            if verbose:
                print(f"✅ 設定をインポートしました")
                print(f"   ファイル: {import_path.absolute()}")
            return True
        except Exception as e:
            print(f"❌ インポートエラー: {str(e)}")
            return False


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="自律型 RAG Agent - バックアップ・リストア統合",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python autonomous_rag_agent.py --query "ドキュメントについて質問"
  python autonomous_rag_agent.py --backup
  python autonomous_rag_agent.py --restore
  python autonomous_rag_agent.py --list-backups
  python autonomous_rag_agent.py --show-config
  python autonomous_rag_agent.py --export-config config_export.json
  python autonomous_rag_agent.py --import-config config_import.json
        """
    )
    
    parser.add_argument('--query', type=str, help='質問を実行')
    parser.add_argument('--backup', action='store_true', help='設定をバックアップ')
    parser.add_argument('--restore', type=str, nargs='?', const='latest', 
                        metavar='FILE', help='設定をリストア（FILEを指定しない場合は最新）')
    parser.add_argument('--list-backups', action='store_true', help='バックアップ一覧を表示')
    parser.add_argument('--show-config', action='store_true', help='現在の設定を表示')
    parser.add_argument('--export-config', type=str, metavar='FILE', help='設定をエクスポート')
    parser.add_argument('--import-config', type=str, metavar='FILE', help='設定をインポート')
    parser.add_argument('--human-in-the-loop', action='store_true',
                        help='回答表示前に確認プロンプトを挟む')
    parser.add_argument('--strict-ethics', action='store_true',
                        help='倫理監査がwarning/failの場合は回答本文をブロックする')
    parser.add_argument('--show-ethics-report', action='store_true',
                        help='倫理監査サマリーレポートを表示する')
    parser.add_argument('--ethics-report-hours', type=int, default=24,
                        help='倫理レポートの集計期間（時間）')
    parser.add_argument('--save-response-log', action='store_true',
                        help='応答を logs/agent_responses.jsonl に保存する')
    parser.add_argument('-v', '--verbose', action='store_true', help='詳細出力')
    
    args = parser.parse_args()
    
    # RAG Agent 初期化
    agent = AutonomousRAGAgent()
    
    # コマンド処理
    if args.query:
        print(f"\n🔍 RAG Query を実行...")
        response = agent.query(
            args.query,
            verbose=args.verbose,
            strict_ethics=args.strict_ethics,
            save_response_log=args.save_response_log,
        )

        if args.human_in_the_loop:
            print(f"\n🧭 HITL確認")
            print(f"   推定信頼度: {response['confidence']:.2f}")
            print(f"   要レビュー: {'はい' if response['needs_human_review'] else 'いいえ'}")
            approve = input("この回答を表示しますか？ [y/N]: ").strip().lower()
            if approve not in ("y", "yes"):
                print("⏹️ ユーザー判断により出力を中止しました。")
                return 2

        print(f"\n💬 応答:")
        print(response['answer'])
        print(f"\n📈 推定信頼度: {response['confidence']:.2f}")
        ethics = response.get('ethics_audit', {})
        risk = response.get('risk_assessment', {})
        print(
            f"🛡️ 倫理監査: status={ethics.get('status')} "
            f"score={ethics.get('overall_score')}"
        )
        print(
            f"⚠️ 複合リスク: level={risk.get('risk_level')} "
            f"score={risk.get('risk_score')}"
        )
        if ethics.get('violations'):
            print("   検出事項:")
            for v in ethics['violations']:
                print(f"   - {v}")
        print(f"🧾 実行トレース: {response['execution_trace']}")
        print(f"\n📚 参照ドキュメント ({response['source_count']} 個):")
        for idx, source in enumerate(response['sources'], 1):
            print(f"  {idx}. {source['name']} ({source['category']})")
        return 0
    
    elif args.backup:
        print(f"\n💾 バックアップを実行...")
        if agent.backup_config(verbose=True):
            return 0
        else:
            return 1
    
    elif args.restore is not None:
        print(f"\n⬇️ リストアを実行...")
        backup_file = None if args.restore == 'latest' else args.restore
        if agent.restore_config(backup_file=backup_file, verbose=True):
            return 0
        else:
            return 1
    
    elif args.list_backups:
        print(f"\n📋 バックアップ一覧...")
        agent.list_backups(verbose=True)
        return 0
    
    elif args.show_config:
        print(f"\n⚙️ 設定情報...")
        agent.show_config(verbose=True)
        return 0

    elif args.show_ethics_report:
        print(f"\n🛡️ 倫理監査レポート...")
        report = agent.get_ethics_report(period_hours=max(1, args.ethics_report_hours))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    
    elif args.export_config:
        print(f"\n📤 設定をエクスポート...")
        if agent.export_config(args.export_config, verbose=True):
            return 0
        else:
            return 1
    
    elif args.import_config:
        print(f"\n📥 設定をインポート...")
        if agent.import_config(args.import_config, verbose=True):
            return 0
        else:
            return 1
    
    else:
        # デフォルトは設定表示
        print(f"\n🤖 自律型 RAG Agent")
        print(f"ヘルプ: python autonomous_rag_agent.py --help\n")
        agent.show_config(verbose=True)
        return 0


if __name__ == '__main__':
    sys.exit(main())
