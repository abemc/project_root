# マルチモーダルシステム実装ガイド

## 概要

マルチモーダルシステムは、自立型LLMに以下の機能を統合します：

- **🖼️ ビジョン（画像認識）**: 画像の説明、オブジェクト検出、テキスト抽出、色分析
- **🎙️ オーディオ（音声処理）**: 音声認識、テキスト音声合成
- **🔗 統合処理**: 複数モーダルを組み合わせてLLMで処理

## アーキテクチャ

```
┌─────────────────────────────────────────┐
│        マルチモーダル入力                 │
│  (テキスト + 画像 + 音声)                │
└──────────────┬──────────────────────────┘
               │
         ┌─────┴─────┐
         │             │
       ┌──▼──┐    ┌──▼──┐
       │Vision│    │Audio │
       └──┬──┘    └──┬──┘
         │             │
    ┌────▼─────┐  ┌────▼────┐
    │画像分析    │  │音声処理 │
    └────┬─────┘  └────┬────┘
         │             │
    ┌────▼─────────────▼────┐
    │ MultimodalIntegrator   │
    │  (コンテキスト生成)      │
    └────┬──────────────────┘
         │
    ┌────▼──────────┐
    │ LLMプロンプト  │
    └────┬──────────┘
         │
    ┌────▼──────────────┐
    │レスポンス生成      │
    │(オプション:音声合成)│
    └────────────────────┘
```

## モジュール概要

### 1. VisionAnalyzer（ビジョン分析）

画像からのインサイト抽出：

```python
from src.multimodal import VisionAnalyzer

analyzer = VisionAnalyzer(model_name="clip")
analysis = analyzer.analyze_image("image.png")

print(analysis.description)      # 画像説明
print(analysis.objects)          # 検出オブジェクト
print(analysis.text_content)     # OCRテキスト
print(analysis.colors)           # 主な色
```

**機能:**
- **画像説明**: CLIP/BLIPモデルで自然言語説明を生成
- **オブジェクト検出**: DETRで物体を検出・分類
- **OCR**: Tesseractでテキストを抽出
- **色分析**: K-meansで主要色を抽出
- **バッチ処理**: 複数画像の効率的な処理

### 2. AudioProcessor（オーディオ処理）

音声のテキスト化と合成：

```python
from src.multimodal import AudioProcessor

processor = AudioProcessor(
    tts_engine="edge-tts",
    default_language="ja"
)

# 音声認識
transcription = processor.transcribe_audio("audio.mp3")
print(transcription.text)        # 認識テキスト
print(transcription.language)    # 言語
print(transcription.confidence)  # 信頼度

# テキスト音声合成
synthesis = processor.synthesize_speech(
    text="こんにちは",
    output_path="output.mp3",
    language="ja"
)
print(synthesis.output_path)     # 出力ファイルパス
print(synthesis.duration)        # 音声長
```

**機能:**
- **音声認識**: Whisperで多言語対応の転記
- **テキスト音声合成**: edge-tts（推奨）またはgTTS
- **言語選択**: 自動言語検出と手動指定
- **バッチ処理**: 複数ファイルの処理

### 3. MultimodalIntegrator（統合エンジン）

マルチモーダル入出力を管理：

```python
from src.multimodal import MultimodalIntegrator

integrator = MultimodalIntegrator()

# ステップ1: マルチモーダル入力を処理
multimodal_input = integrator.process_multimodal_input(
    text="この画像は？",
    image_paths=["image.png"],
    audio_paths=["query.mp3"]
)

# ステップ2: コンテキストプロンプトを生成
context_prompt = integrator.generate_context_prompt(multimodal_input)
# LLMに送信

# ステップ3: レスポンスを作成（オプション音声合成）
multimodal_output = integrator.create_response(
    response_text="レスポンステキスト",
    multimodal_input=multimodal_input,
    synthesize_speech=True,
    language="ja"
)
```

**ワークフロー:**
1. 入力の受け取り（テキスト/画像/音声）
2. 各モーダルの個別処理
3. コンテキストの統合
4. LLMプロンプトの生成
5. レスポンスの処理（オプション音声出力）

## 配置ガイド

### ファイル構成

```
src/multimodal/
├── __init__.py                    # パッケージ初期化
├── vision_module.py              # VisionAnalyzer実装
├── audio_module.py               # AudioProcessor実装
├── multimodal_integration.py      # MultimodalIntegrator実装
├── config.py                      # 設定クラス
├── streamlit_ui.py              # Streamlit UI（オプション）
└── README.md                      # このファイル

tests/
└── test_multimodal.py            # テストスイート

logs/
└── multimodal/                   # ログディレクトリ
    ├── multimodal.log            # ログファイル
    └── interaction_history.jsonl # インタラクション履歴
```

## 設定

### VisionConfig

```python
from src.multimodal.config import VisionConfig

config = VisionConfig(
    model_name="clip",                # clip, blip, detr
    clip_model="openai/clip-vit-base-patch32",
    blip_model="Salesforce/blip-image-captioning-base",
    max_image_size=1024,
    batch_size=4,
    enable_detection=True,            # オブジェクト検出
    enable_ocr=True,                  # テキスト抽出
    enable_color_analysis=True,       # 色分析
    cache_dir="models/multimodal/vision"
)
```

### AudioConfig

```python
from src.multimodal.config import AudioConfig

config = AudioConfig(
    transcription_model="whisper-small",
    tts_engine="edge-tts",           # edge-tts または gtts
    default_language="ja",
    supported_languages=["ja", "en", "zh", "es", "fr", "de", "ko"],
    sample_rate=16000,
    cache_dir="models/multimodal/audio"
)
```

## 使用例

### 例1: 画像クエリの処理

```python
from src.multimodal import MultimodalIntegrator

integrator = MultimodalIntegrator()

# ステップ1: 画像と質問を入力
inp = integrator.process_multimodal_input(
    text="この画像に何が写っていますか？",
    image_paths=["scene.jpg"]
)

# ステップ2: コンテキストを確認
prompt = integrator.generate_context_prompt(inp)
print(prompt)

# ステップ3: LLMで処理（疑似コード）
llm_response = llm.generate(prompt)

# ステップ4: 音声応答を作成
out = integrator.create_response(
    response_text=llm_response,
    multimodal_input=inp,
    synthesize_speech=True
)

print(f"音声ファイル: {out.audio_output.output_path}")
```

### 例2: 音声コマンドの処理

```python
# 音声をテキストに変換して処理
inp = integrator.process_multimodal_input(
    audio_paths=["command.mp3"]
)

# 認識テキストを確認
if inp.audio:
    print(f"認識: {inp.audio.text}")
    
    # さらに処理...
    prompt = integrator.generate_context_prompt(inp)
    llm_response = llm.generate(prompt)
    
    # 結果を音声で返す
    out = integrator.create_response(
        response_text=llm_response,
        multimodal_input=inp,
        synthesize_speech=True
    )
```

### 例3: 複数モーダルの統合処理

```python
# テキスト + 画像 + 音声の統合
inp = integrator.process_multimodal_input(
    text="これについての質問があります",
    image_paths=["context.png"],
    audio_paths=["question.mp3"]
)

# 統合コンテキスト
context_prompt = integrator.generate_context_prompt(inp)
"""
ユーザー入力: これについての質問があります

🎙️ 音声内容: より詳しく説明してください
言語: ja
信頼度: 95%

🖼️ 画像分析 (1個):
  画像 1:
    説明: 会议室での複数人の会議シーン
    検出オブジェクト: person, chair, table, screen
    テキスト内容: "Project Timeline"
    主な色: white(45%), gray(30%)
"""

# LLMで処理
response = llm.generate(context_prompt)
```

## Streamlit UI統合

### 基本的な使用方法

```python
import streamlit as st
from src.multimodal.streamlit_ui import render_multimodal_dashboard

def main():
    render_multimodal_dashboard()

if __name__ == "__main__":
    main()
```

### UI コンポーネント

**画像入力:**
- 画像アップロード（複数ファイル対応）
- リアルタイムプレビュー
- 自動形式検出

**音声入力:**
- 音声ファイルアップロード
- インライン再生
- 多形式対応（MP3, WAV, M4A, OGG）

**テキスト表示:**
- 処理結果の詳細表示
- インタラクション履歴
- 統計ダッシュボード

**レスポンス生成:**
- テキストレスポンス入力
- 音声合成オプション
- 言語選択

## テストの実行

```bash
# マルチモーダルテストの実行
python -m pytest tests/test_multimodal.py -v

# または直接実行
python tests/test_multimodal.py
```

**テストカバレッジ:**
- MultimodalIntegrator 初期化・処理・出力
- VisionAnalyzer 初期化・画像分析
- AudioProcessor 初期化
- 設定クラス
- データクラス構造

## パフォーマンスのヒント

### メモリ最適化

```python
# モデル共有で効率化
integrator = MultimodalIntegrator(
    vision_model="clip",      # 軽量モデルを選択
    audio_model="whisper-tiny"  # 小さいモデルオプション
)
```

### バッチ処理

```python
# 複数画像の効率的処理
images = integrator.vision.batch_analyze(
    image_paths=["img1.jpg", "img2.jpg", "img3.jpg"],
    batch_size=2
)

# 複数音声の処理
transcriptions = integrator.audio.batch_transcribe(
    audio_paths=["audio1.mp3", "audio2.mp3"]
)
```

### キャッシング

自動キャッシング機能により、同じ入力の処理が高速化されます：

```python
# 最初の処理（モデルロード）
analysis1 = analyzer.analyze_image("test.jpg")

# 2回目以降（キャッシュから）
analysis2 = analyzer.analyze_image("test.jpg")  # 高速
```

## トラブルシューティング

### モデルダウンロードのエラー

```python
# HF_HOMEを設定
import os
os.environ["HF_HOME"] = "path/to/hf_cache"

from src.multimodal import VisionAnalyzer
analyzer = VisionAnalyzer()
```

### CUDA/GPUメモリ不足

```python
# CPUで実行
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# または小さいモデルを使用
integrator = MultimodalIntegrator(
    vision_model="clip",
    audio_model="whisper-tiny"
)
```

### 音声ファイルのフォーマットエラー

```python
# ffmpegを確認
import subprocess
subprocess.run(["ffmpeg", "-version"])

# 対応フォーマット: MP3, WAV, M4A, OGG, FLAC
```

## ログとモニタリング

### ロギング設定

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("src.multimodal")
```

### インタラクション履歴

```python
# インタラクション統計
summary = integrator.get_interaction_summary()
print(f"入力: {summary['input_count']}")
print(f"画像: {summary['total_images_processed']}")
print(f"音声: {summary['total_audio_duration']:.1f}秒")

# ログをエクスポート
log_path = integrator.export_interaction_log()
```

## LLMシステムとの統合

### app.pyでの使用例

```python
from src.multimodal import MultimodalIntegrator
from src.self_improvement import FeedbackManager

# マルチモーダル処理
integrator = MultimodalIntegrator()

# ユーザーの画像・音声入力を処理
multimodal_input = integrator.process_multimodal_input(
    text=user_text,
    image_paths=user_images,
    audio_paths=user_audio
)

# コンテキストプロンプト生成
context = integrator.generate_context_prompt(multimodal_input)

# LLM処理
response = llm.generate(context)

# 音声応答（オプション）
output = integrator.create_response(
    response_text=response,
    multimodal_input=multimodal_input,
    synthesize_speech=True
)

# フィードバック記録
feedback_mgr = FeedbackManager()
feedback_mgr.record_feedback(
    response=response,
    rating=user_rating,
    context={"multimodal": True}
)
```

## 依存関係

### 必須

- `transformers` - モデル管理
- `torch` - ディープラーニング
- `Pillow` - 画像処理

### 音声処理

- `openai-whisper` - 音声認識
- `edge-tts` - テキスト音声合成（推奨）
- `gTTS` - テキスト音声合成（フォールバック）

### 画像処理

- `scikit-learn` - K-means色分析
- `pytesseract` - OCR
- `opencv-python` - 画像処理（オプション）

### UI

- `streamlit` - Webインターフェース

### 開発

- `pytest` - テストフレームワーク
- `soundfile` - 音声ファイル処理（テスト用）

## ライセンス

各モデルのライセンスに従ってください：
- CLIP: Open source
- BLIP: Open source  
- Whisper: MIT
- Tesseract: Apache 2.0

## 次のステップ

1. **マルチモーダルフィードバック**: ユーザーフィードバックを複数モーダルで記録
2. **キャッシング最適化**: LRUキャッシュの実装
3. **リアルタイムストリーミング**: 音声・画像のリアルタイム処理
4. **マルチ言語対応の強化**: さらなる言語サポート
5. **エッジデバイス対応**: 軽量モデルの検証
