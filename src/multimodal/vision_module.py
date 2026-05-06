"""ビジョン（画像認識）モジュール

画像の解析、説明生成、特徴抽出などの機能を提供します。
"""

import logging
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysis:
    """画像分析結果"""
    image_path: str
    timestamp: str
    description: str
    objects: List[str]
    text_content: str
    colors: List[Dict[str, Any]]
    size: Dict[str, int]
    confidence: float
    metadata: Dict[str, Any] = None


class VisionAnalyzer:
    """画像認識・分析モジュール"""
    
    def __init__(self, model_name: str = "clip", cache_dir: str = None):
        """
        Args:
            model_name: 使用モデル（clip, blip, llava など）
            cache_dir: モデルキャッシュディレクトリ
        """
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir else Path("models/vision")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.analysis_history: List[ImageAnalysis] = []
        self._load_model()
    
    def _load_model(self):
        """ビジョンモデルをロード"""
        try:
            if self.model_name == "clip":
                from transformers import CLIPProcessor, CLIPModel
                logger.info("Loading CLIP model...")
                self.model = CLIPModel.from_pretrained(
                    "openai/clip-vit-base-patch32",
                    cache_dir=str(self.cache_dir)
                )
                self.processor = CLIPProcessor.from_pretrained(
                    "openai/clip-vit-base-patch32",
                    cache_dir=str(self.cache_dir)
                )
                logger.info("✅ CLIP model loaded successfully")
            elif self.model_name == "blip":
                from transformers import BlipProcessor, BlipForConditionalGeneration
                logger.info("Loading BLIP model...")
                self.model = BlipForConditionalGeneration.from_pretrained(
                    "Salesforce/blip-image-captioning-base",
                    cache_dir=str(self.cache_dir)
                )
                self.processor = BlipProcessor.from_pretrained(
                    "Salesforce/blip-image-captioning-base",
                    cache_dir=str(self.cache_dir)
                )
                logger.info("✅ BLIP model loaded successfully")
            else:
                logger.warning(f"Model {self.model_name} not supported. Using CLIP.")
                from transformers import CLIPProcessor, CLIPModel
                self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        except ImportError:
            logger.warning("Transformers not installed. Vision module will use basic image processing.")
            self.model = None
            self.processor = None
    
    def analyze_image(
        self,
        image_path: str,
        detailed: bool = True,
    ) -> ImageAnalysis:
        """
        画像を分析
        
        Args:
            image_path: 画像ファイルパス
            detailed: 詳細分析するか
        
        Returns:
            ImageAnalysis オブジェクト
        """
        try:
            from PIL import Image
        except ImportError:
            logger.error("Pillow not installed. Cannot analyze images.")
            raise ImportError("Pillow is required for vision module")
        
        image_path = Path(image_path)
        
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        try:
            image = Image.open(image_path)
            
            # 基本情報
            size = {"width": image.width, "height": image.height}
            
            # 説明生成
            description = self._generate_description(image)
            
            # オブジェクト検出
            objects = self._detect_objects(image) if detailed else []
            
            # テキスト抽出
            text_content = self._extract_text(image)
            
            # 色分析
            colors = self._analyze_colors(image) if detailed else []
            
            analysis = ImageAnalysis(
                image_path=str(image_path),
                timestamp=datetime.now().isoformat(),
                description=description,
                objects=objects,
                text_content=text_content,
                colors=colors,
                size=size,
                confidence=0.85,  # 概算信頼度
                metadata={
                    "format": image.format,
                    "mode": image.mode,
                    "dpi": image.info.get("dpi", None),
                }
            )
            
            self.analysis_history.append(analysis)
            logger.info(f"✅ Image analyzed: {image_path.name}")
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            raise
    
    def _generate_description(self, image) -> str:
        """
        画像の自然言語説明を生成
        
        Args:
            image: PIL Image オブジェクト
        
        Returns:
            説明テキスト
        """
        if self.model is None:
            return self._generate_basic_description(image)
        
        try:
            if self.model_name == "blip":
                import torch
                # BLIPで画像キャプション生成
                inputs = self.processor(image, return_tensors="pt")
                out = self.model.generate(**inputs, max_length=77)
                description = self.processor.decode(out[0], skip_special_tokens=True)
                return description
            
            elif self.model_name == "clip":
                # CLIPでテキスト類似度スコアリング
                texts = [
                    "a photo of a scene",
                    "a photo with people",
                    "a photo of nature",
                    "a photo of objects",
                    "a technical diagram"
                ]
                inputs = self.processor(text=texts, images=image, return_tensors="pt", padding=True)
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image
                best_idx = logits_per_image.argmax().item()
                return texts[best_idx]
        
        except Exception as e:
            logger.warning(f"Model inference failed: {e}. Using basic description.")
            return self._generate_basic_description(image)
    
    def _generate_basic_description(self, image) -> str:
        """基本的な画像説明を生成"""
        w, h = image.size
        ratio = "landscape" if w > h else "portrait" if h > w else "square"
        
        try:
            # 支配的な色を判定
            colors = self._analyze_colors(image)
            if colors:
                dominant_color = colors[0]["name"]
                return f"A {ratio} image with dominant {dominant_color} color ({w}x{h}px)"
            return f"A {ratio} image ({w}x{h}px)"
        except:
            return f"An image ({w}x{h}px)"
    
    def _detect_objects(self, image) -> List[str]:
        """
        オブジェクト検出
        
        Returns:
            検出されたオブジェクトのリスト
        """
        try:
            from transformers import DetrImageProcessor, DetrForObjectDetection
            processor = DetrImageProcessor.from_pretrained("facebook/detr-resnet-50")
            model = DetrForObjectDetection.from_pretrained("facebook/detr-resnet-50")
            
            inputs = processor(images=image, return_tensors="pt")
            outputs = model(**inputs)
            
            target_sizes = [image.size[::-1]]
            results = processor.post_process_object_detection(
                outputs, target_sizes=target_sizes, threshold=0.9
            )
            
            detected = []
            for result in results:
                for label_id in result["labels"]:
                    label = model.config.id2label.get(label_id.item(), "unknown")
                    if label not in detected:
                        detected.append(label)
            
            return detected[:10]  # 上位10個まで
        
        except Exception as e:
            logger.debug(f"Object detection not available: {e}")
            return []
    
    def _extract_text(self, image) -> str:
        """
        画像からテキストを抽出（OCR）
        
        Returns:
            抽出されたテキスト
        """
        try:
            import pytesseract
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.debug(f"Text extraction not available: {e}")
            return ""
    
    def _analyze_colors(self, image, num_colors: int = 5) -> List[Dict[str, Any]]:
        """
        支配的な色を分析
        
        Args:
            image: PIL Image オブジェクト
            num_colors: 抽出する色数
        
        Returns:
            色情報のリスト
        """
        try:
            import numpy as np
            from PIL import Image
            
            # RGB変換
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # ピクセルを取得
            pixels = np.array(image.resize((100, 100)))
            pixels = pixels.reshape(-1, 3)
            
            # K-means でクラスタリング
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=min(num_colors, 5), random_state=42)
            kmeans.fit(pixels)
            
            colors = []
            for i, center in enumerate(kmeans.cluster_centers_):
                r, g, b = int(center[0]), int(center[1]), int(center[2])
                name = self._rgb_to_color_name(r, g, b)
                colors.append({
                    "rgb": (r, g, b),
                    "hex": f"#{r:02x}{g:02x}{b:02x}",
                    "name": name,
                    "percentage": round((np.sum(kmeans.labels_ == i) / len(pixels)) * 100, 1)
                })
            
            return sorted(colors, key=lambda x: x["percentage"], reverse=True)
        
        except Exception as e:
            logger.debug(f"Color analysis not available: {e}")
            return []
    
    def _rgb_to_color_name(self, r: int, g: int, b: int) -> str:
        """RGB値から色名を取得"""
        if max(r, g, b) - min(r, g, b) < 50:  # グレースケール
            if max(r, g, b) < 100:
                return "black"
            elif max(r, g, b) > 200:
                return "white"
            else:
                return "gray"
        
        # 最も値が大きい成分
        max_idx = [r, g, b].index(max(r, g, b))
        colors = ["red", "green", "blue"]
        
        # 微調整
        if max_idx == 0:  # Red
            if g > b:
                return "orange"
            return "red"
        elif max_idx == 1:  # Green
            if b > r:
                return "cyan"
            return "green"
        else:  # Blue
            if r > g:
                return "purple"
            return "blue"
    
    def get_analysis_as_text(self, analysis: ImageAnalysis) -> str:
        """
        分析結果をテキスト形式で取得（LLMに提供用）
        
        Args:
            analysis: ImageAnalysis オブジェクト
        
        Returns:
            フォーマットされたテキスト
        """
        text = f"""画像分析結果:
        
📋 説明: {analysis.description}

🏷️ 検出オブジェクト: {', '.join(analysis.objects) if analysis.objects else 'なし'}

📝 テキスト内容: {analysis.text_content if analysis.text_content else 'テキストなし'}

🎨 支配的な色:
{chr(10).join(f"  - {c['name']}: {c['hex']} ({c['percentage']}%)" for c in analysis.colors[:3])}

📐 サイズ: {analysis.size['width']}x{analysis.size['height']}px

🔍 信頼度: {analysis.confidence:.0%}
"""
        return text
    
    def batch_analyze(self, image_paths: List[str]) -> List[ImageAnalysis]:
        """
        複数の画像を一括分析
        
        Args:
            image_paths: 画像ファイルパスのリスト
        
        Returns:
            分析結果のリスト
        """
        results = []
        for path in image_paths:
            try:
                result = self.analyze_image(path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {path}: {e}")
        
        return results
    
    def get_history(self, limit: int = 10) -> List[ImageAnalysis]:
        """分析履歴を取得"""
        return self.analysis_history[-limit:]
