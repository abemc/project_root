"""
ドメイン特化モデル開発 - テストスイート
"""

import pytest
from src.domain_specialization.domain_models import (
    DomainType, DomainVocabulary,
    DomainDetector,
    DomainSpecificPrompter, DomainKnowledgeRetriever,
    DomainQualityAssurance, DomainModelManager
)
from src.domain_specialization.lora_adapter import (
    LoRAConfig, LoRAAdapterModule, DomainSpecificLoRA, MultiDomainLoRAManager
)


# ==================== DomainDetector Tests ====================

class TestDomainDetector:
    """ドメイン検出エンジンのテスト"""
    
    def test_legal_domain_detection(self):
        """法務ドメイン検出テスト"""
        detector = DomainDetector()
        text = "The contract between the plaintiff and defendant includes liability limitations."
        domain = detector.detect_domain(text)
        assert domain == DomainType.LEGAL
    
    def test_medical_domain_detection(self):
        """医療ドメイン検出テスト"""
        detector = DomainDetector()
        text = "The patient showed symptoms of disease and required clinical treatment."
        domain = detector.detect_domain(text)
        assert domain == DomainType.MEDICAL
    
    def test_technical_domain_detection(self):
        """技術ドメイン検出テスト"""
        detector = DomainDetector()
        text = "The algorithm requires code deployment with proper API documentation."
        domain = detector.detect_domain(text)
        assert domain == DomainType.TECHNICAL
    
    def test_financial_domain_detection(self):
        """金融ドメイン検出テスト"""
        detector = DomainDetector()
        text = "Investment portfolio management and dividend forecasting."
        domain = detector.detect_domain(text)
        assert domain == DomainType.FINANCIAL
    
    def test_general_domain_fallback(self):
        """一般ドメインへのフォールバックテスト"""
        detector = DomainDetector()
        text = "This is a simple text without domain-specific keywords."
        domain = detector.detect_domain(text)
        assert domain == DomainType.GENERAL
    
    def test_domain_confidence_calculation(self):
        """ドメイン信頼度計算テスト"""
        detector = DomainDetector()
        text = "contract law agreement attorney lawsuit"
        confidence = detector.get_domain_confidence(text, DomainType.LEGAL)
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.3


# ==================== DomainVocabulary Tests ====================

class TestDomainVocabulary:
    """ドメイン用語集のテスト"""
    
    def test_vocabulary_creation(self):
        """用語集作成テスト"""
        vocab = DomainVocabulary(domain=DomainType.LEGAL)
        assert vocab.domain == DomainType.LEGAL
        assert len(vocab.terms) == 0
    
    def test_add_term(self):
        """用語追加テスト"""
        vocab = DomainVocabulary(domain=DomainType.LEGAL)
        vocab.add_term("plaintiff", "A party who initiates legal action", ["claimant"])
        assert "plaintiff" in vocab.terms
        assert "plaintiff" in vocab.synonyms
    
    def test_get_term_definition(self):
        """用語定義取得テスト"""
        vocab = DomainVocabulary(domain=DomainType.LEGAL)
        vocab.add_term("defendant", "A party being sued")
        definition = vocab.get_term_definition("defendant")
        assert definition == "A party being sued"
        assert vocab.get_term_definition("nonexistent") is None


# ==================== DomainSpecificPrompter Tests ====================

class TestDomainSpecificPrompter:
    """ドメイン特化プロンプティングシステムのテスト"""
    
    def test_get_legal_prompt(self):
        """法務プロンプト取得テスト"""
        prompter = DomainSpecificPrompter()
        prompt = prompter.get_domain_prompt(DomainType.LEGAL, "analyze_contract")
        assert prompt is not None
        assert "contract" in prompt.lower()
    
    def test_get_medical_prompt(self):
        """医療プロンプト取得テスト"""
        prompter = DomainSpecificPrompter()
        prompt = prompter.get_domain_prompt(DomainType.MEDICAL, "diagnosis_assistance")
        assert prompt is not None
        assert "diagnos" in prompt.lower()
    
    def test_augment_query(self):
        """クエリ拡張テスト"""
        prompter = DomainSpecificPrompter()
        original = "Analyze this contract"
        augmented = prompter.augment_query(original, DomainType.LEGAL, "analyze_contract")
        assert len(augmented) > len(original)
        assert "contract" in augmented.lower()
    
    def test_missing_prompt_fallback(self):
        """プロンプト不在時のフォールバックテスト"""
        prompter = DomainSpecificPrompter()
        augmented = prompter.augment_query("Query", DomainType.GENERAL, "unknown_task")
        assert augmented == "Query"


# ==================== DomainKnowledgeRetriever Tests ====================

class TestDomainKnowledgeRetriever:
    """ドメイン知識検索エンジンのテスト"""
    
    @pytest.mark.asyncio
    async def test_retrieve_context(self):
        """コンテキスト検索テスト"""
        retriever = DomainKnowledgeRetriever()
        context = await retriever.retrieve_context(
            "contract law",
            DomainType.LEGAL,
            top_k=3
        )
        assert isinstance(context, list)
        assert len(context) <= 3
    
    @pytest.mark.asyncio
    async def test_retrieve_medical_context(self):
        """医療コンテキスト検索テスト"""
        retriever = DomainKnowledgeRetriever()
        context = await retriever.retrieve_context(
            "diagnosis treatment",
            DomainType.MEDICAL,
            top_k=2
        )
        assert isinstance(context, list)


# ==================== DomainQualityAssurance Tests ====================

class TestDomainQualityAssurance:
    """ドメイン別品質保証のテスト"""
    
    @pytest.mark.asyncio
    async def test_validate_legal_output(self):
        """法務出力検証テスト"""
        qa = DomainQualityAssurance()
        output = "According to the contract cited in Smith v. Jones precedent, liability is limited."
        result = await qa.validate_output(output, DomainType.LEGAL)
        
        assert "valid" in result
        assert result["domain"] == DomainType.LEGAL.value
        assert result["checks_total"] > 0
    
    @pytest.mark.asyncio
    async def test_validate_medical_output(self):
        """医療出力検証テスト"""
        qa = DomainQualityAssurance()
        output = "Consult a medical professional. This is not medical advice."
        result = await qa.validate_output(output, DomainType.MEDICAL)
        
        assert result["domain"] == DomainType.MEDICAL.value
        assert result["checks_total"] > 0
    
    @pytest.mark.asyncio
    async def test_validation_issues_detected(self):
        """検証問題検出テスト"""
        qa = DomainQualityAssurance()
        output = "Some generic text"
        result = await qa.validate_output(output, DomainType.LEGAL)
        
        assert "issues" in result
        assert isinstance(result["issues"], list)


# ==================== LoRAConfig Tests ====================

class TestLoRAConfig:
    """LoRA設定のテスト"""
    
    def test_default_config(self):
        """デフォルト設定テスト"""
        config = LoRAConfig()
        assert config.rank == 16
        assert config.alpha == 32
        assert config.scaling == 32 / 16
    
    def test_custom_config(self):
        """カスタム設定テスト"""
        config = LoRAConfig(rank=8, alpha=16)
        assert config.rank == 8
        assert config.alpha == 16
        assert config.scaling == 2.0
    
    def test_target_modules(self):
        """ターゲットモジュール設定テスト"""
        config = LoRAConfig(target_modules=["q_proj", "v_proj", "fc1"])
        assert len(config.target_modules) == 3


# ==================== LoRAAdapterModule Tests ====================

class TestLoRAAdapterModule:
    """LoRAアダプターモジュールのテスト"""
    
    def test_module_initialization(self):
        """モジュール初期化テスト"""
        config = LoRAConfig(rank=8)
        module = LoRAAdapterModule(
            in_features=768,
            out_features=768,
            config=config,
            layer_name="layer_0.q_proj"
        )
        
        assert module.in_features == 768
        assert module.out_features == 768
        assert len(module.lora_a) == 768
        assert len(module.lora_b[0]) == 768
    
    def test_forward_pass(self):
        """フォワードパステスト"""
        config = LoRAConfig(rank=4)
        module = LoRAAdapterModule(4, 4, config, "test_layer")
        
        x = [[1.0, 2.0, 3.0, 4.0]]
        output = module.forward(x)
        
        assert len(output) == 1
        assert len(output[0]) == 4
    
    def test_parameter_count(self):
        """パラメータ数テスト"""
        config = LoRAConfig(rank=16)
        module = LoRAAdapterModule(768, 768, config, "test")
        
        expected_params = (768 * 16) + (16 * 768)
        assert module.total_params == expected_params
    
    def test_save_weights(self):
        """重み保存テスト"""
        config = LoRAConfig(rank=8)
        module = LoRAAdapterModule(64, 64, config, "layer_test")
        
        weights = module.save_weights()
        assert weights.layer_name == "layer_test"
        assert len(weights.A) == 64
        assert len(weights.B) == 8


# ==================== DomainSpecificLoRA Tests ====================

class TestDomainSpecificLoRA:
    """ドメイン特化LoRAのテスト"""
    
    def test_lora_creation(self):
        """LoRA作成テスト"""
        lora = DomainSpecificLoRA(
            model_hidden_size=768,
            num_attention_heads=12,
            num_layers=12
        )
        
        config = LoRAConfig(rank=16)
        adapters = lora.create_lora_adapter("legal", config)
        
        assert len(adapters) > 0
        assert "legal" in lora.adapters
    
    def test_total_params_calculation(self):
        """パラメータ総数計算テスト"""
        lora = DomainSpecificLoRA(model_hidden_size=768, num_layers=2)
        config = LoRAConfig(rank=16)
        lora.create_lora_adapter("legal", config)
        
        total_params = lora.get_total_lora_params("legal")
        assert total_params > 0
    
    def test_adapter_statistics(self):
        """アダプター統計テスト"""
        lora = DomainSpecificLoRA()
        config = LoRAConfig(rank=16)
        lora.create_lora_adapter("medical", config)
        
        stats = lora.get_adapter_statistics("medical")
        assert "total_modules" in stats
        assert "total_parameters" in stats
        assert stats["total_modules"] > 0


# ==================== MultiDomainLoRAManager Tests ====================

class TestMultiDomainLoRAManager:
    """マルチドメインLoRA管理のテスト"""
    
    def test_manager_initialization(self):
        """管理器初期化テスト"""
        config = {
            "hidden_size": 768,
            "num_attention_heads": 12,
            "num_layers": 12
        }
        manager = MultiDomainLoRAManager(config)
        
        assert manager.active_domain is None
    
    def test_register_domain(self):
        """ドメイン登録テスト"""
        manager = MultiDomainLoRAManager({"hidden_size": 768})
        success = manager.register_domain("legal", lora_rank=16)
        
        assert success
        assert "legal" in manager.domain_configs
    
    def test_activate_domain(self):
        """ドメイン有効化テスト"""
        manager = MultiDomainLoRAManager({"hidden_size": 768})
        manager.register_domain("legal")
        success = manager.activate_domain("legal")
        
        assert success
        assert manager.active_domain == "legal"
    
    def test_deactivate_domain(self):
        """ドメイン無効化テスト"""
        manager = MultiDomainLoRAManager({"hidden_size": 768})
        manager.register_domain("legal")
        manager.activate_domain("legal")
        manager.deactivate_domain()
        
        assert manager.active_domain is None
    
    def test_adapter_info(self):
        """アダプター情報取得テスト"""
        manager = MultiDomainLoRAManager({"hidden_size": 768})
        manager.register_domain("legal")
        manager.register_domain("medical")
        
        info = manager.get_adapter_info()
        assert len(info["registered_domains"]) == 2
    
    def test_efficiency_report(self):
        """効率性レポートテスト"""
        manager = MultiDomainLoRAManager({
            "hidden_size": 768,
            "num_layers": 12
        })
        manager.register_domain("legal", lora_rank=16)
        
        report = manager.get_efficiency_report()
        assert "base_model_parameters" in report
        assert "total_lora_parameters" in report
        assert "parameter_overhead_percent" in report


# ==================== DomainModelManager Tests ====================

class TestDomainModelManager:
    """ドメインモデル統合管理のテスト"""
    
    @pytest.mark.asyncio
    async def test_process_legal_query(self):
        """法務クエリ処理テスト"""
        manager = DomainModelManager()
        result = await manager.process_query(
            "Analyze this contract clause",
            task_type="analyze_contract"
        )
        
        assert "detected_domain" in result
        assert "augmented_query" in result
    
    @pytest.mark.asyncio
    async def test_process_medical_query(self):
        """医療クエリ処理テスト"""
        manager = DomainModelManager()
        result = await manager.process_query(
            "What are the symptoms of this disease?",
            task_type="general"
        )
        
        assert result["detected_domain"] == DomainType.MEDICAL.value
    
    @pytest.mark.asyncio
    async def test_domain_report(self):
        """ドメインレポートテスト"""
        manager = DomainModelManager()
        report = await manager.get_domain_report()
        
        assert "registered_domains" in report
        assert "adapters" in report
        assert "timestamp" in report
    
    @pytest.mark.asyncio
    async def test_multiple_domain_queries(self):
        """複数ドメインクエリテスト"""
        manager = DomainModelManager()
        
        queries = [
            "Legal contract analysis",
            "Medical diagnosis help",
            "Technical architecture review",
            "Financial investment advice"
        ]
        
        for query in queries:
            result = await manager.process_query(query)
            assert result["detected_domain"] in [d.value for d in DomainType]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
