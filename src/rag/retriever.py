import faiss
import numpy as np
import json
import torch
from transformers import AutoTokenizer, AutoModel
from src.utils.async_helpers import run_in_executor, await_future
from typing import Union

import os
from pathlib import Path
try:
    from PIL import Image
    import pytesseract
    import hashlib
except ImportError:
    pass

import datetime

# プロジェクトルートをこのファイルの2階層上として解決
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = PROJECT_ROOT / "corpus"

class Retriever:
    def __init__(self, index_path: Union[str, Path] = DEFAULT_CORPUS_PATH / "corpus.index", meta_path: Union[str, Path] = DEFAULT_CORPUS_PATH / "corpus_meta.json"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Retriever is using device: {self.device}")
        print("Loading local embedding model (bge-m3, safetensors)...")

        # safetensors のみロード（torch.load を使わない）
        print("Loading local embedding model (bge-m3) in background...")
        tok_fut = run_in_executor(AutoTokenizer.from_pretrained, "BAAI/bge-m3", trust_remote_code=True)
        model_fut = run_in_executor(AutoModel.from_pretrained, "BAAI/bge-m3", use_safetensors=True, trust_remote_code=True)

        # Await results (may take time) with sensible timeouts
        self.tokenizer = await_future(tok_fut, timeout=60)
        self.model = await_future(model_fut, timeout=180)
        try:
            self.model = self.model.to(self.device)
        except Exception:
            pass
        print("Local embedding model loaded successfully.")

        # パスを保存（strに統一）
        self.index_path = str(index_path)
        self.meta_path = str(meta_path)
        
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

        # インデックスとメタデータをロード
        self.load()

    # -----------------------------
    # 永続化
    # -----------------------------
    def load(self):
        """インデックスとメタデータをファイルからロードする"""
        try:
            print(f"Loading FAISS index from {self.index_path}...")
            self.index = faiss.read_index(str(self.index_path))
            print(f"Loading metadata from {self.meta_path}...")
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.meta = json.load(f)
            print(f"Loaded {len(self.meta)} metadata entries")
        except (FileNotFoundError, RuntimeError) as e:
            print(f"Could not load knowledge base ({e}). Initializing a new one.")
            # モデルの次元数を取得
            dim = 1024
            if hasattr(self.model, "config") and hasattr(self.model.config, "hidden_size"):
                dim = self.model.config.hidden_size
            # 空のインデックスとメタデータを作成
            self.index = faiss.IndexFlatIP(dim)
            self.meta = []

    def save(self):
        """現在のインデックスとメタデータをファイルに保存する"""
        try:
            print(f"Saving FAISS index to {self.index_path}...")
            # self.index_path を明示的に文字列型に変換
            faiss.write_index(self.index, str(self.index_path))

            print(f"Saving metadata to {self.meta_path}...")
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2)

            print("Knowledge base saved successfully.")
        except Exception as e:
            print(f"[Error] Failed to save knowledge base: {e}")

    
    # -----------------------------
    # クエリ埋め込み（bge-m3）
    # -----------------------------
    def embed_query(self, text: str):
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
            emb = outputs.last_hidden_state[:, 0, :]  # CLS token
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)

        return emb[0].cpu().numpy().astype("float32")

    # -----------------------------
    # 検索
    # -----------------------------
    def search(self, query: str, top_k: int = 5, score_threshold: float = -1.0, source_filter: str = None):
        q_emb = self.embed_query(query)
        # フィルタがある場合は多めに取得してフィルタリング
        search_k = top_k * 5 if source_filter else top_k
        scores, indices = self.index.search(np.array([q_emb]), search_k)

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0:
                continue
            if score < score_threshold:
                continue

            item = self.meta[idx].copy()
            
            # ソースフィルタリング
            if source_filter:
                item_src = item.get("meta", {}).get("source") or item.get("source")
                if item_src != source_filter:
                    continue
            
            item["score"] = float(score)
            results.append(item)
            
            if len(results) >= top_k:
                break

        return results

    # -----------------------------
    # 最近のドキュメント取得
    # ---------------------------------------------
    def get_recent_docs(self, top_k: int = 5):
        """
        最近追加されたドキュメントを取得する。
        メタデータリストの末尾から取得する。
        """
        if not self.meta:
            return []
        
        # リストの末尾から top_k 件を取得（新しい順にするため reverse）
        recent_items = self.meta[-top_k:][::-1]
        
        results = []
        for item in recent_items:
            res_item = item.copy()
            # スコアは便宜上 1.0 とする（検索キーワードとの関連度ではないため）
            res_item["score"] = 1.0 
            res_item["search_type"] = "recent"
            results.append(res_item)
            
        return results

    # ---------------------------------------------
    # キーワード検索 (簡易実装)
    # -----------------------------
    def search_keyword(self, query: str, top_k: int = 5):
        # 空白区切りで単語リスト化（日本語の場合はMeCab等推奨だが、ここでは簡易的に文字列カウントを行う）
        terms = query.split()
        if not terms:
            return []
        
        scores = []
        # メタデータを走査して出現数をカウント
        for item in self.meta:
            text = item.get("text", "")
            score = 0
            for term in terms:
                # 大文字小文字を無視してカウント
                score += text.lower().count(term.lower())
            
            if score > 0:
                scores.append((item, score))
        
        # 出現数が多い順にソート
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for item, score in scores[:top_k]:
            res_item = item.copy()
            res_item["score"] = float(score)
            res_item["search_type"] = "keyword"
            results.append(res_item)
        
        return results

    # -----------------------------
    # ハイブリッド検索 (RRF: Reciprocal Rank Fusion)
    # -----------------------------
    def hybrid_search(self, query: str, top_k: int = 5, source_filter: str = None):
        # ベクトル検索とキーワード検索をそれぞれ実行 (マージ用に多めに取得)
        candidates_k = top_k * 5
        vec_results = self.search(query, top_k=candidates_k, source_filter=source_filter)
        kw_results = self.search_keyword(query, top_k=candidates_k) # Keyword検索もフィルタ対応したいが、一旦そのまま
        
        # kw_resultsもフィルタリング
        if source_filter:
            kw_results = [
                doc for doc in kw_results 
                if (doc.get("meta", {}).get("source") or doc.get("source")) == source_filter
            ]

        # RRFスコアの計算: Score = 1 / (k + rank)
        rrf_k = 60
        doc_scores = {}
        docs_map = {}

        # 結果リストを統合するヘルパー関数
        def merge_results(results):
            for rank, doc in enumerate(results):
                doc_id = doc.get("id")
                if not doc_id: continue
                
                if doc_id not in docs_map:
                    docs_map[doc_id] = doc
                
                # 既存スコアに加算
                current_score = doc_scores.get(doc_id, 0.0)
                doc_scores[doc_id] = current_score + (1.0 / (rrf_k + rank + 1))

        merge_results(vec_results)
        merge_results(kw_results)
        
        # RRFスコア順にソート
        sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
        
        final_results = []
        for doc_id in sorted_ids[:top_k]:
            doc = docs_map[doc_id]
            doc["score"] = doc_scores[doc_id]  # RRFスコアで上書き
            final_results.append(doc)
            
        return final_results

    # -----------------------------
    # 知識ベース管理
    # -----------------------------
    def clear(self):
        """インデックスとメタデータを全消去する"""
        dim = 1024
        if hasattr(self.model, "config") and hasattr(self.model.config, "hidden_size"):
            dim = self.model.config.hidden_size
            
        self.index = faiss.IndexFlatIP(dim)
        self.meta = []
        print("Knowledge base cleared.")
        self.save()

    def add_texts(self, texts: list[str], source_info: dict):
        """
        テキストのリストを受け取り、インデックスに追加する。
        Web検索結果などの動的な情報ソースからの追加を想定。

        Args:
            texts (list[str]): 追加するテキストのリスト。
            source_info (dict): 出典情報（例: {"source": "web_search", "query": "..."}）
        """
        if not texts:
            return 0

        embeddings = []
        new_meta_entries = []
        
        current_id_start = len(self.meta)
        
        for i, text in enumerate(texts):
            if not text.strip():
                continue
                
            emb = self.embed_query(text)
            embeddings.append(emb)
            
            # メタ情報を作成
            meta_entry = {
                "text": text,
                "meta": source_info.copy(), # 渡されたsource_infoをコピーして使用
                "id": f"web_{current_id_start + i}",
            }
            new_meta_entries.append(meta_entry)
            
        # FAISSに追加
        if embeddings:
            self.index.add(np.array(embeddings, dtype="float32"))
            self.meta.extend(new_meta_entries)
            self.save()
            
        return len(new_meta_entries)

    def add_pdf(self, file_obj, progress_callback=None):
        """PDFファイルからテキストを抽出し、インデックスに追加する"""
        try:
            import pypdf
            # OCR用ライブラリ
            from PIL import Image
            import pytesseract
            import io
            import concurrent.futures
            import hashlib
        except ImportError:
            msg = "pypdf or pytesseract not found. Please install them: pip install pypdf pytesseract"
            print(msg)
            return {"chunks_added": 0, "status": msg}

        # --- Cache Check ---
        # ファイルハッシュを計算してキャッシュを確認
        file_obj.seek(0)
        file_content = file_obj.read()
        file_obj.seek(0)
        file_hash = hashlib.md5(file_content).hexdigest()
        
        # OCRキャッシュもコーパスディレクトリ内に保存する
        corpus_dir = os.path.dirname(self.index_path)
        cache_dir = os.path.join(corpus_dir, "ocr_cache")
        cache_available = True
        
        # キャッシュディレクトリの作成を試みる（失敗してもスキップ）
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            print(f"[Warning] Cannot create cache directory: {e}. Proceeding without cache.")
            cache_available = False
            cache_dir = None
        
        cache_path = os.path.join(cache_dir, f"{file_hash}.txt") if cache_available else None
        
        full_text = ""
        ocr_count = 0
        
        if cache_available and cache_path and os.path.exists(cache_path):
            print(f"Loading cached OCR result for hash: {file_hash}")
            with open(cache_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            if progress_callback:
                progress_callback(0.9, "Loaded text from cache. Skipping OCR.")
        else:
            reader = pypdf.PdfReader(file_obj)
            total_pages = len(reader.pages)
            
            # ページごとのテキストを保持するリスト（順序保持のため）
            page_texts = [""] * total_pages
            # OCRタスクを収集するリスト
            ocr_tasks = [] # (page_index, image_bytes)
            
            # 1. テキスト抽出と画像の収集 (スキャンフェーズ: 全体の20%の進捗とする)
            print(f"Scanning PDF ({total_pages} pages)...")
            for i, page in enumerate(reader.pages):
                # 進捗コールバック（テキスト抽出フェーズ）
                if progress_callback:
                    progress_callback(0.2 * (i / total_pages), f"Scanning page {i+1}/{total_pages}...")

                # 1. テキスト抽出を試みる
                txt = page.extract_text()
                if txt and txt.strip():
                    page_texts[i] = txt + "\n"
                else:
                    # 2. テキストがなければOCR用画像を収集
                    try:
                        for img_obj in page.images:
                            ocr_tasks.append((i, img_obj.data))
                    except Exception as e:
                        print(f"[Warning] Failed to extract images from page {i+1}: {e}")

            # 2. OCR並列処理 (OCRフェーズ: 全体の20%〜90%の進捗とする)
            total_ocr = len(ocr_tasks)
            if total_ocr > 0:
                print(f"Starting parallel OCR for {total_ocr} images...")
                
                def process_ocr_task(task):
                    p_idx, img_bytes = task
                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        # OCR実行
                        # Run OCR in background to avoid blocking
                        ocr_fut = run_in_executor(pytesseract.image_to_string, img, 'jpn+eng')
                        text = await_future(ocr_fut, timeout=20)
                        return p_idx, text
                    except Exception:
                        return p_idx, ""

                # スレッドプールで並列実行
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    futures = [executor.submit(process_ocr_task, task) for task in ocr_tasks]
                    
                    for j, future in enumerate(concurrent.futures.as_completed(futures)):
                        if progress_callback:
                            # 0.2 + (0.7 * 進捗率)
                            current_prog = 0.2 + (0.7 * ((j + 1) / total_ocr))
                            progress_callback(current_prog, f"OCR Processing {j+1}/{total_ocr} images...")
                        
                        try:
                            p_idx, res_text = future.result()
                            if res_text and res_text.strip():
                                page_texts[p_idx] += res_text + "\n"
                                ocr_count += 1
                        except Exception as e:
                            print(f"[OCR Error] {e}")

            full_text = "".join(page_texts)
            
            # 結果をキャッシュに保存
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
                print(f"Saved OCR result to cache: {cache_path}")
            except Exception as e:
                print(f"[Warning] Failed to save cache: {e}")

        # 簡易的なチャンク分割 (文字数ベース)
        chunk_size = 400
        overlap = 50
        chunks = []
        if len(full_text) > chunk_size:
            for i in range(0, len(full_text), chunk_size - overlap):
                chunks.append(full_text[i:i + chunk_size])
        elif full_text.strip():
            chunks.append(full_text)
        
        if not chunks:
            return {"chunks_added": 0, "status": "No text could be extracted from the PDF."}

        # ベクトル化
        embeddings = []
        new_meta_entries = []
        
        # ファイル名取得 (Streamlit UploadedFile has .name)
        source_name = getattr(file_obj, "name", "uploaded_pdf")

        current_id_start = len(self.meta)

        # このPDFファイル全体で共通のメタデータ
        source_info = {
            "source": source_name,
            "uploaded_at": datetime.datetime.now().isoformat()
        }

        for i, chunk in enumerate(chunks):
            emb = self.embed_query(chunk)
            embeddings.append(emb)
            new_meta_entries.append({
                "text": chunk,
                "meta": source_info,
                "id": f"up_{current_id_start + i}",
            })
            
        # FAISSに追加
        if embeddings:
            self.index.add(np.array(embeddings, dtype="float32"))
            self.meta.extend(new_meta_entries)
            self.save()
            
        return {
            "chunks_added": len(chunks),
            "source_name": source_name,
            "ocr_pages": ocr_count,
            "status": "Successfully added to the knowledge base."
        }

    def add_image(self, file_obj, progress_callback=None):
        """画像ファイルからテキストをOCR抽出し、インデックスに追加する"""
        try:
            import io
        except ImportError:
            return {"chunks_added": 0, "status": "Required libraries not found."}

        # --- Cache Check ---
        file_obj.seek(0)
        file_content = file_obj.read()
        file_obj.seek(0)
        file_hash = hashlib.md5(file_content).hexdigest()
        
        corpus_dir = os.path.dirname(self.index_path)
        cache_dir = os.path.join(corpus_dir, "ocr_cache")
        cache_available = True
        
        # キャッシュディレクトリの作成を試みる（失敗してもスキップ）
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            print(f"[Warning] Cannot create cache directory: {e}. Proceeding without cache.")
            cache_available = False
            cache_dir = None
        
        cache_path = os.path.join(cache_dir, f"img_{file_hash}.txt") if cache_available else None
        
        extracted_text = ""
        
        if cache_available and cache_path and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
            if progress_callback:
                progress_callback(0.9, "Loaded text from cache.")
        else:
            if progress_callback:
                progress_callback(0.3, "Performing OCR on image...")
            try:
                img = Image.open(file_obj)
                ocr_fut = run_in_executor(pytesseract.image_to_string, img, 'jpn+eng')
                extracted_text = await_future(ocr_fut, timeout=20)
                
                if cache_available and cache_path:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        f.write(extracted_text)
            except Exception as e:
                return {"chunks_added": 0, "status": f"OCR Error: {e}"}

        if not extracted_text.strip():
            return {"chunks_added": 0, "status": "No text detected in the image."}

        # チャンク分割 (画像の場合は通常1つのチャンクで十分)
        source_name = getattr(file_obj, "name", "uploaded_image")
        current_id_start = len(self.meta)
        source_info = {
            "source": source_name,
            "uploaded_at": datetime.datetime.now().isoformat(),
            "type": "image"
        }

        # 埋め込みと保存
        emb = self.embed_query(extracted_text)
        self.index.add(np.array([emb], dtype="float32"))
        self.meta.append({
            "text": extracted_text,
            "meta": source_info,
            "id": f"img_{current_id_start}",
        })
        self.save()
        
        if progress_callback:
            progress_callback(1.0, "Complete")
            
        return {
            "chunks_added": 1,
            "source_name": source_name,
            "status": "Successfully added image content to knowledge base."
        }

    def delete_source(self, source_name: str):
        """
        指定されたソース名のドキュメントを削除する。
        
        Args:
            source_name (str): 削除対象のソース名（ファイル名など）。
            
        Returns:
            int: 削除されたチャンク数。
        """
        print(f"Deleting source: {source_name}...")
        
        indices_to_remove = []
        new_meta = []
        
        for i, item in enumerate(self.meta):
            # メタデータからsourceを取得
            meta_info = item.get("meta", {})
            src = meta_info.get("source")
            if not src:
                src = item.get("source") # レガシー互換

            # UI側のロジックと合わせ、sourceがなければ "unknown" として扱う
            current_item_source = src if src else "unknown"

            if current_item_source == source_name:
                indices_to_remove.append(i)
            else:
                new_meta.append(item)
        
        if not indices_to_remove:
            return 0
            
        # FAISSインデックスから削除
        ids_to_remove = np.array(indices_to_remove, dtype=np.int64)
        self.index.remove_ids(ids_to_remove)
        
        # メタデータを更新して保存
        self.meta = new_meta
        self.save()
        
        return len(indices_to_remove)

    def delete_document(self, doc_id: str):
        """
        指定されたIDのドキュメント（チャンク）を削除する。
        
        Args:
            doc_id (str): 削除対象のドキュメントID。
            
        Returns:
            bool: 削除に成功した場合はTrue。
        """
        print(f"Attempting to delete document: {doc_id}...")
        
        idx_to_remove = -1
        
        for i, item in enumerate(self.meta):
            if item.get("id") == doc_id:
                idx_to_remove = i
                break
        
        if idx_to_remove == -1:
            print(f"Document ID {doc_id} not found.")
            return False
            
        # FAISSインデックスから削除
        ids_to_remove = np.array([idx_to_remove], dtype=np.int64)
        self.index.remove_ids(ids_to_remove)
        
        # メタデータリストから削除
        self.meta.pop(idx_to_remove)
        self.save()
        
        print(f"Document {doc_id} deleted successfully.")
        return True

    def update_document_metadata(self, doc_id: str, updates: dict):
        """
        指定されたIDのドキュメントのメタデータを更新する。
        
        Args:
            doc_id (str): 更新対象のドキュメントID。
            updates (dict): 更新または追加するメタデータの辞書。
            
        Returns:
            bool: 更新に成功した場合はTrue。
        """
        for item in self.meta:
            if item.get("id") == doc_id:
                # metaフィールドがない場合は初期化
                if "meta" not in item or item["meta"] is None:
                    item["meta"] = {}
                
                # 更新を適用
                item["meta"].update(updates)
                self.save()
                print(f"Metadata for {doc_id} updated successfully.")
                return True
        
        print(f"Document ID {doc_id} not found.")
        return False