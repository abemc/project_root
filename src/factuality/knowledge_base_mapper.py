"""
知識ベースマッパー
外部知識ベース（Wikipedia、DBpedia等）との統合
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntity:
    """知識ベースエンティティ"""
    name: str
    entity_type: str  # person, place, organization, etc.
    description: str
    aliases: List[str] = None
    source: str = "unknown"
    confidence: float = 1.0
    last_updated: Optional[str] = None
    related_entities: List[str] = None
    facts: List[Dict] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.related_entities is None:
            self.related_entities = []
        if self.facts is None:
            self.facts = []


@dataclass
class Relationship:
    """エンティティ間の関係"""
    source_entity: str
    target_entity: str
    relationship_type: str  # "is_capital_of", "is_located_in", "authored", etc.
    confidence: float = 1.0
    source: str = "unknown"


class KnowledgeBase(ABC):
    """知識ベースの抽象インターフェース"""
    
    @abstractmethod
    def lookup_entity(self, entity_name: str) -> Optional[KnowledgeEntity]:
        """エンティティを検索"""
        pass
    
    @abstractmethod
    def lookup_relationship(
        self,
        entity1: str,
        entity2: str,
        relationship_type: Optional[str] = None,
    ) -> List[Relationship]:
        """エンティティ間の関係を検索"""
        pass
    
    @abstractmethod
    def search_entities(self, query: str, entity_type: Optional[str] = None) -> List[KnowledgeEntity]:
        """エンティティを検索クエリで検索"""
        pass


class MockKnowledgeBase(KnowledgeBase):
    """テスト用モック知識ベース"""
    
    def __init__(self):
        self.entities = self._init_entities()
        self.relationships = self._init_relationships()
    
    def _init_entities(self) -> Dict[str, KnowledgeEntity]:
        """初期エンティティを作成"""
        return {
            "Paris": KnowledgeEntity(
                name="Paris",
                entity_type="city",
                description="Capital and most populous city of France",
                aliases=["Ville-Lumière", "City of Light"],
                source="Wikipedia",
                facts=[
                    {"key": "population", "value": "2161000"},
                    {"key": "country", "value": "France"},
                    {"key": "established", "value": "259 BC"},
                ],
            ),
            "France": KnowledgeEntity(
                name="France",
                entity_type="country",
                description="Country in Western Europe",
                aliases=["French Republic", "La France"],
                source="Wikipedia",
                facts=[
                    {"key": "population", "value": "67000000"},
                    {"key": "capital", "value": "Paris"},
                    {"key": "continent", "value": "Europe"},
                ],
            ),
            "Tokyo": KnowledgeEntity(
                name="Tokyo",
                entity_type="city",
                description="Capital and most populous city of Japan",
                source="Wikipedia",
                facts=[
                    {"key": "population", "value": "13000000"},
                    {"key": "country", "value": "Japan"},
                    {"key": "established", "value": "1868"},
                ],
            ),
            "Japan": KnowledgeEntity(
                name="Japan",
                entity_type="country",
                description="Island nation in East Asia",
                aliases=["Nippon"],
                source="Wikipedia",
                facts=[
                    {"key": "population", "value": "125000000"},
                    {"key": "capital", "value": "Tokyo"},
                    {"key": "continent", "value": "Asia"},
                ],
            ),
            "Albert Einstein": KnowledgeEntity(
                name="Albert Einstein",
                entity_type="person",
                description="Theoretical physicist",
                source="Wikipedia",
                facts=[
                    {"key": "birth_year", "value": "1879"},
                    {"key": "death_year", "value": "1955"},
                    {"key": "nationality", "value": "German-American"},
                    {"key": "famous_for", "value": "Theory of Relativity"},
                ],
            ),
        }
    
    def _init_relationships(self) -> List[Relationship]:
        """初期関係を作成"""
        return [
            Relationship(
                source_entity="Paris",
                target_entity="France",
                relationship_type="is_capital_of",
            ),
            Relationship(
                source_entity="Tokyo",
                target_entity="Japan",
                relationship_type="is_capital_of",
            ),
            Relationship(
                source_entity="Albert Einstein",
                target_entity="Germany",
                relationship_type="born_in",
            ),
        ]
    
    def lookup_entity(self, entity_name: str) -> Optional[KnowledgeEntity]:
        """エンティティを検索"""
        # 完全一致
        if entity_name in self.entities:
            return self.entities[entity_name]
        
        # エイリアス検索
        for entity in self.entities.values():
            if entity_name.lower() in [a.lower() for a in entity.aliases]:
                return entity
        
        # 部分一致
        entity_lower = entity_name.lower()
        for ent_name, entity in self.entities.items():
            if entity_lower in ent_name.lower():
                return entity
        
        return None
    
    def lookup_relationship(
        self,
        entity1: str,
        entity2: str,
        relationship_type: Optional[str] = None,
    ) -> List[Relationship]:
        """エンティティ間の関係を検索"""
        results = []
        
        for rel in self.relationships:
            if rel.source_entity == entity1 and rel.target_entity == entity2:
                if relationship_type is None or rel.relationship_type == relationship_type:
                    results.append(rel)
        
        return results
    
    def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
    ) -> List[KnowledgeEntity]:
        """エンティティを検索クエリで検索"""
        results = []
        query_lower = query.lower()
        
        for entity in self.entities.values():
            # タイプフィルター
            if entity_type and entity.entity_type != entity_type:
                continue
            
            # 名前で検索
            if query_lower in entity.name.lower():
                results.append(entity)
            # 説明で検索
            elif query_lower in entity.description.lower():
                results.append(entity)
            # エイリアスで検索
            elif any(query_lower in alias.lower() for alias in entity.aliases):
                results.append(entity)
        
        return results


class KnowledgeBaseMapper:
    """知識ベースマッパー"""
    
    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None):
        self.knowledge_base = knowledge_base or MockKnowledgeBase()
    
    def map_claim_to_knowledge(self, claim: str) -> Dict:
        """クレイムを知識ベースにマッピング"""
        
        # クレイムからエンティティ抽出（簡略版）
        entities = self._extract_entities_from_claim(claim)
        
        mapped_entities = []
        for entity_name in entities:
            kb_entity = self.knowledge_base.lookup_entity(entity_name)
            if kb_entity:
                mapped_entities.append({
                    "original": entity_name,
                    "mapped": kb_entity.name,
                    "type": kb_entity.entity_type,
                    "confidence": kb_entity.confidence,
                    "facts": kb_entity.facts,
                })
        
        return {
            "claim": claim,
            "mapped_entities": mapped_entities,
            "coverage": len(mapped_entities) / max(1, len(entities)),
        }
    
    def verify_relationship(self, entity1: str, entity2: str, relationship_type: str) -> bool:
        """知識ベース内に関係が存在するか確認"""
        relationships = self.knowledge_base.lookup_relationship(
            entity1, entity2, relationship_type
        )
        return len(relationships) > 0
    
    def get_related_facts(self, entity_name: str) -> List[Dict]:
        """エンティティに関連する事実を取得"""
        entity = self.knowledge_base.lookup_entity(entity_name)
        if entity:
            return entity.facts
        return []
    
    def find_similar_entities(self, entity_name: str, limit: int = 5) -> List[KnowledgeEntity]:
        """似たエンティティを検索"""
        return self.knowledge_base.search_entities(entity_name)[:limit]
    
    def _extract_entities_from_claim(self, claim: str) -> List[str]:
        """クレイムからエンティティを抽出（簡略版）"""
        # 実際にはNERモデルを使用
        # ここでは簡略化されたアプローチ
        import re
        
        entities = []
        
        # 固有名詞候補（大文字で始まる単語）
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', claim)
        entities.extend(proper_nouns)
        
        # よく知られた都市・国名
        known_places = ["Paris", "Tokyo", "France", "Japan", "London", "New York"]
        for place in known_places:
            if place in claim:
                if place not in entities:
                    entities.append(place)
        
        # よく知られた人物
        known_people = ["Albert Einstein", "Isaac Newton", "Marie Curie"]
        for person in known_people:
            if person in claim:
                if person not in entities:
                    entities.append(person)
        
        return entities
    
    def generate_knowledge_context(self, entities: List[str]) -> str:
        """エンティティのコンテキスト情報を生成"""
        contexts = []
        
        for entity_name in entities:
            entity = self.knowledge_base.lookup_entity(entity_name)
            if entity:
                context_parts = [
                    f"{entity.name}: {entity.description}",
                ]
                
                # 事実を追加
                if entity.facts:
                    fact_strs = [f"{f['key']}: {f['value']}" for f in entity.facts[:3]]
                    context_parts.append(f"Facts: {', '.join(fact_strs)}")
                
                contexts.append(" | ".join(context_parts))
        
        return "\n".join(contexts)
