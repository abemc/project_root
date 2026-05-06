import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class GPTConfig:
    def __init__(self, vocab_size, n_layer, n_head, n_embd, block_size):
        self.vocab_size = vocab_size
        self.n_layer = n_layer
        self.n_head = n_head
        self.n_embd = n_embd
        self.block_size = block_size


class CausalSelfAttention(nn.Module):
    def __init__(self, config):
        super().__init__()
        assert config.n_embd % config.n_head == 0

        self.key = nn.Linear(config.n_embd, config.n_embd)
        self.query = nn.Linear(config.n_embd, config.n_embd)
        self.value = nn.Linear(config.n_embd, config.n_embd)

        self.n_head = config.n_head
        self.dropout = nn.Dropout(0.1)

        self.proj = nn.Linear(config.n_embd, config.n_embd)

        # causal mask
        mask = torch.tril(torch.ones(config.block_size, config.block_size))
        self.register_buffer("mask", mask)

    def forward(self, x):
        B, T, C = x.size()
        H = self.n_head
        head_dim = C // H

        k = self.key(x).view(B, T, H, head_dim).transpose(1, 2)
        q = self.query(x).view(B, T, H, head_dim).transpose(1, 2)
        v = self.value(x).view(B, T, H, head_dim).transpose(1, 2)

        att = (q @ k.transpose(-2, -1)) / math.sqrt(head_dim)
        att = att.masked_fill(self.mask[:T, :T] == 0, float("-inf"))
        att = F.softmax(att, dim=-1)
        att = self.dropout(att)

        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)

        return self.proj(y)


class Block(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.n_embd)
        self.attn = CausalSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.n_embd)
        self.mlp = nn.Sequential(
            nn.Linear(config.n_embd, 4 * config.n_embd),
            nn.GELU(),
            nn.Linear(4 * config.n_embd, config.n_embd),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, config):
        super().__init__()

        self.token_emb = nn.Embedding(config.vocab_size, config.n_embd)
        self.pos_emb = nn.Parameter(torch.zeros(1, config.block_size, config.n_embd))

        self.blocks = nn.Sequential(*[Block(config) for _ in range(config.n_layer)])
        self.ln_f = nn.LayerNorm(config.n_embd)
        self.head = nn.Linear(config.n_embd, config.vocab_size, bias=False)

        self.block_size = config.block_size

    def forward(self, idx):
        B, T = idx.size()
        assert T <= self.block_size

        tok = self.token_emb(idx)
        pos = self.pos_emb[:, :T, :]
        x = tok + pos

        x = self.blocks(x)
        x = self.ln_f(x)
        logits = self.head(x)

        return logits


@torch.no_grad()
def generate(model, config, idx, max_new_tokens):
    for _ in range(max_new_tokens):
        idx_cond = idx[:, -config.block_size:]
        logits = model(idx_cond)
        logits = logits[:, -1, :]
        probs = F.softmax(logits, dim=-1)
        next_id = torch.multinomial(probs, num_samples=1)
        idx = torch.cat((idx, next_id), dim=1)
    return idx