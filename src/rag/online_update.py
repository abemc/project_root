# src/rag/online_update.py
import os
import sys

try:
    from unsloth import FastLanguageModel, is_bfloat16_supported
    from datasets import load_dataset
    from trl import DPOTrainer
    from transformers import TrainingArguments
except ImportError as e:
    print(f"[Error] Dependencies missing: {e}")
    sys.exit(1)

MODEL_NAME = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 過去のファインチューニング済みモデルがあれば、それをベースにする
PREV_MODEL_DIR = os.path.join(PROJECT_ROOT, "fine_tuned_model")
if os.path.exists(PREV_MODEL_DIR) and os.path.exists(os.path.join(PREV_MODEL_DIR, "adapter_config.json")):
    MODEL_NAME = PREV_MODEL_DIR
    print(f"Continuing from previous fine-tuned model: {MODEL_NAME}")

DPO_DATASET_PATH = os.path.join(PROJECT_ROOT, "logs", "dpo_dataset.jsonl")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "fine_tuned_model")

MAX_SEQ_LENGTH = 2048
LORA_RANK = 16
EPOCHS = 2 
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 2
LEARNING_RATE = 5e-5

def train_dpo():
    print(f"Loading DPO dataset from: {DPO_DATASET_PATH}")
    if not os.path.exists(DPO_DATASET_PATH):
        print(f"Error: {DPO_DATASET_PATH} not found.")
        return

    print(f"Loading model: {MODEL_NAME}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = MODEL_NAME,
        max_seq_length = MAX_SEQ_LENGTH,
        dtype = None,
        load_in_4bit = True,
    )

    if MODEL_NAME != PREV_MODEL_DIR:
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
        )

    dataset = load_dataset("json", data_files=DPO_DATASET_PATH, split="train")

    def formatting_dpo(examples):
        prompts = []
        chosens = []
        rejecteds = []
        for p, c, r in zip(examples["prompt"], examples["chosen"], examples["rejected"]):
            prompt_chat = [{"role": "user", "content": p}]
            prompts.append(tokenizer.apply_chat_template(prompt_chat, tokenize=False, add_generation_prompt=True))
            chosens.append(c + "<|im_end|>\n")
            rejecteds.append(r + "<|im_end|>\n")
        return {"prompt": prompts, "chosen": chosens, "rejected": rejecteds}

    dataset = dataset.map(formatting_dpo, batched=True)
    print(f"DPO dataset size: {len(dataset)}")

    trainer = DPOTrainer(
        model = model,
        ref_model = None, 
        tokenizer = tokenizer,
        train_dataset = dataset,
        beta = 0.1,
        max_length = MAX_SEQ_LENGTH,
        max_prompt_length = MAX_SEQ_LENGTH // 2,
        args = TrainingArguments(
            per_device_train_batch_size = BATCH_SIZE,
            gradient_accumulation_steps = GRADIENT_ACCUMULATION_STEPS,
            warmup_steps = 2,
            num_train_epochs = EPOCHS,
            learning_rate = LEARNING_RATE,
            fp16 = not is_bfloat16_supported(),
            bf16 = is_bfloat16_supported(),
            logging_steps = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            output_dir = OUTPUT_DIR,
            remove_unused_columns=False,
        ),
    )

    print("Starting DPO incremental training...")
    trainer.train()

    print(f"Saving updated model to {OUTPUT_DIR}...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    gguf_path = "model_q4_k_m_dpo.gguf"
    print(f"Converting to GGUF ({gguf_path})...")
    try:
        model.save_pretrained_gguf(OUTPUT_DIR, tokenizer, quantization_method="q4_k_m")
        print(f"DPO model saved to {os.path.join(OUTPUT_DIR, gguf_path)}")
        import subprocess
        # Modelfileを動的に生成してOllamaを再ロード
        modelfile_path = os.path.join(PROJECT_ROOT, "Modelfile")
        with open(modelfile_path, "w") as f:
            f.write(f'FROM {os.path.join(OUTPUT_DIR, gguf_path)}\n')
            f.write('SYSTEM "あなたはRAGエージェントです。ユーザーの質問に対して、知識ベースに基づき正確に回答してください。"\n')
        
        subprocess.run(["ollama", "create", "my-rag-model", "-f", modelfile_path])
        print("✅ Ollamaモデルの再ロードが完了しました (my-rag-model)")

    except Exception as e:
        print(f"Failed to convert to GGUF or reload Ollama: {e}")

if __name__ == "__main__":
    train_dpo()
