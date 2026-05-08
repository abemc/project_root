from src.model import GPTConfig

# 小型モデル（124M相当）
small_124M = GPTConfig(
    vocab_size=50257,
    n_layer=12,
    n_head=12,
    n_embd=768,
    block_size=512
)

# 中型モデル（355M相当）
medium_355M = GPTConfig(
    vocab_size=50257,
    n_layer=24,
    n_head=16,
    n_embd=1024,
    block_size=512
)

# 数学特化モデル（700M相当）
math_700M = GPTConfig(
    vocab_size=50257,
    n_layer=32,
    n_head=16,
    n_embd=1280,
    block_size=1024
)