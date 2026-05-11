# src/rag/train.py

import os
import sys

try:
    from unsloth import FastLanguageModel, is_bfloat16_supported
    from datasets import load_dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments
except ImportError as e:
    print(f"[Error] Failed to import training dependencies: {e}")
    print("Please install Unsloth and other libraries:")
    print('  pip install "unsloth[cu121-torch240] @ git+https://github.com/unslothai/unsloth.git"')
    print('  pip install --no-deps "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes')
    sys.exit(1)

# ---------------------------------------------------------
# 設定
# ---------------------------------------------------------
# ベースモデル（Qwen2.5-7B-Instruct の 4bit量子化版を使用）
MODEL_NAME = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"

# プロジェクトルートとデータセットのパス
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_PATH = os.path.join(PROJECT_ROOT, "logs", "finetune_dataset.jsonl")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "fine_tuned_model")

# ハイパーパラメータ
MAX_SEQ_LENGTH = 2048
LORA_RANK = 16
EPOCHS = 3
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 4
LEARNING_RATE = 2e-4

def train():
    print(f"Loading dataset from: {DATASET_PATH}")
    if not os.path.exists(DATASET_PATH):
        print(f"Error: Dataset file not found at {DATASET_PATH}")
        print("Please run the 'Generate Dataset' feature from the app first.")
        return

    # 1. モデルとトークナイザーのロード
    print(f"Loading model: {MODEL_NAME}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = MODEL_NAME,
        max_seq_length = MAX_SEQ_LENGTH,
        dtype = None,
        load_in_4bit = True,
    )

    # 2. LoRAアダプターの設定
    model = FastLanguageModel.get_peft_model(
        model,
        r = LORA_RANK,
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"],
        lora_alpha = 16,
        lora_dropout = 0,
        bias = "none",
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
        use_rslora = False,
        loftq_config = None,
    )

    # 3. データセットの準備とフォーマット
    # Qwen2.5用のチャットテンプレートを適用して学習データに変換する
    dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
    
    def formatting_prompts_func(examples):
        convos = examples["messages"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
        return { "text": texts }

    dataset = dataset.map(formatting_prompts_func, batched=True)

    print(f"Dataset size: {len(dataset)} samples")

    # 4. Trainerの設定
    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = dataset,
        dataset_text_field = "text",
        max_seq_length = MAX_SEQ_LENGTH,
        dataset_num_proc = 2,
        packing = False,
        args = TrainingArguments(
            per_device_train_batch_size = BATCH_SIZE,
            gradient_accumulation_steps = GRADIENT_ACCUMULATION_STEPS,
            warmup_steps = 5,
            num_train_epochs = EPOCHS,
            learning_rate = LEARNING_RATE,
            fp16 = not is_bfloat16_supported(),
            bf16 = is_bfloat16_supported(),
            logging_steps = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            lr_scheduler_type = "linear",
            seed = 3407,
            output_dir = OUTPUT_DIR,
        ),
    )

    # 5. 学習実行
    print("Starting training...")
    trainer_stats = trainer.train()
    print(f"Training complete. Stats: {trainer_stats}")

    # 6. 保存 (LoRAアダプター)
    print(f"Saving LoRA adapters to {OUTPUT_DIR}...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # 7. GGUFへの変換と保存 (Ollama用)
    # quantize options: q4_k_m, q5_k_m, q8_0, f16
    gguf_path = "model_q4_k_m.gguf"
    print(f"Converting to GGUF ({gguf_path})... This may take a while.")
    try:
        model.save_pretrained_gguf(OUTPUT_DIR, tokenizer, quantization_method="q4_k_m")
        print(f"GGUF model saved to: {os.path.join(OUTPUT_DIR, gguf_path)}")
        print("\n" + "="*60)
        print("🎉 学習と変換が完了しました！ (Training and Conversion Complete)")
        print("="*60)
        print("\n[次のステップ] 生成されたモデルを Ollama で使用する手順:")
        print("\n1. プロジェクトルートに 'Modelfile' という名前のファイルを作成し、以下を記述します:")
        print(f"   FROM {os.path.join(OUTPUT_DIR, gguf_path)}")
        print("   SYSTEM \"あなたはRAGエージェントです。ユーザーの質問に対して、知識ベースに基づき正確に回答してください。\"")
        print("\n2. ターミナルで以下のコマンドを実行してモデルを作成します:")
        print("   ollama create my-rag-model -f Modelfile")
        print("\n3. アプリ(app.py)のサイドバー設定で 'LLM Model Name' に以下を入力します:")
        print("   my-rag-model")
        print("="*60 + "\n")
    except Exception as e:
        print(f"GGUF conversion failed: {e}")

if __name__ == "__main__":
    train()