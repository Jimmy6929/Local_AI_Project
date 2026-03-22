# GRPO Training Guide — Qwen3.5-9B on M4 Pro 48GB

## What is GRPO?

Group Relative Policy Optimization — simplified RL that improves model reasoning without a separate reward model. The model generates multiple completions per prompt, scores them with verifiable rewards (code execution, math checks), and learns from the best ones.

This is the practical, Apple Silicon-compatible version of what Absolute Zero does on datacenter GPUs.

## Hardware Requirements

| Component | Qwen3.5-9B QLoRA |
|-----------|-----------------|
| Base model (4-bit) | ~4.5GB |
| LoRA adapters | ~50MB |
| Activations (batch=2) | ~2-4GB |
| Optimizer states | ~4.5GB |
| KV cache (4 generations) | ~0.5-2.5GB |
| **Total peak** | **~13-15GB** |
| **M4 Pro 48GB headroom** | ~33GB free |

## Setup

### Option A: MLX-GRPO (Recommended, pure MLX)

```bash
git clone https://github.com/Doriandarko/MLX-GRPO.git
cd MLX-GRPO
pip install uv
uv pip install -e .
```

### Option B: mlx-tune

```bash
pip install mlx-tune
```

### Option C: mlx-lm native LoRA (for SFT, not GRPO)

```bash
pip install "mlx-lm[train]"
```

## Training Data

### Format (JSONL)

```jsonl
{"input": "What is 37 x 29?", "output": "<start_working_out>\n37 x 29 = 37 x (30 - 1) = 1110 - 37 = 1073\n</start_working_out>\n<SOLUTION>1073</SOLUTION>"}
```

### Bootstrap from GSM8K (math reasoning)

```python
from datasets import load_dataset
import json

ds = load_dataset("gsm8k", "main", split="train")
with open("train.jsonl", "w") as f:
    for item in ds:
        f.write(json.dumps({
            "input": item["question"],
            "output": item["answer"]
        }) + "\n")
# Creates ~7,472 math reasoning examples
```

## Reward Functions

### Math Verification

```python
import re

def math_reward(prompt, completion, reference_answer):
    match = re.search(r'<SOLUTION>([^<]+)</SOLUTION>', completion)
    if not match:
        return 0.0
    extracted = match.group(1).strip()
    try:
        if float(extracted.replace(',', '')) == float(reference_answer.replace(',', '')):
            return 1.0
    except ValueError:
        pass
    return 1.0 if extracted == reference_answer else 0.0
```

### Code Execution

```python
import subprocess, tempfile, os

def code_reward(prompt, completion, reference):
    match = re.search(r'```python\n(.*?)\n```', completion, re.DOTALL)
    if not match:
        return 0.0
    code = match.group(1)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(['python3', f.name], capture_output=True, timeout=5)
            return 1.0 if result.returncode == 0 else 0.0
        except:
            return 0.0
        finally:
            os.unlink(f.name)
```

### Format Compliance

```python
def format_reward(prompt, completion, reference):
    checks = [
        '<start_working_out>' in completion,
        '</start_working_out>' in completion,
        '<SOLUTION>' in completion,
        '</SOLUTION>' in completion,
    ]
    return sum(checks) / len(checks)
```

## Run Training

### MLX-GRPO

```bash
# Create config
cat > configs/qwen35.toml << 'EOF'
[model]
model_name = "Qwen/Qwen3.5-9B"
quantize = 4

[training]
num_generations = 4
max_completion_tokens = 256
batch_size = 2
iters = 500
learning_rate = 1e-4
beta = 0.05

[data]
dataset_name = "gsm8k"
split = "train"

[rewards]
accuracy_weight = 1.0
format_weight = 0.5
EOF

uv run mlx-grpo.py --config configs/qwen35.toml
```

### mlx-tune

```bash
python -m mlx_tune.grpo \
  --model Qwen/Qwen3.5-9B \
  --adapter-path ./adapters/qwen35_grpo \
  --train \
  --data train.jsonl \
  --training-mode grpo \
  --group-size 4 \
  --beta 0.05 \
  --batch-size 2 \
  --iters 500 \
  --learning-rate 1e-4
```

## Training Time Estimates (M4 Pro 48GB)

| Dataset | Config | Time |
|---------|--------|------|
| 100 samples, 100 iters | Quick test | ~5 min |
| 1,000 samples, 500 iters | Real training | ~45 min |
| 7,472 samples (full GSM8K), 2000 iters | Full convergence | ~4-6 hours |

## Export & Deploy

### 1. Merge LoRA adapters into base model

```bash
python -m mlx_lm.fuse \
  --model Qwen/Qwen3.5-9B \
  --adapter-file ./adapters/qwen35_grpo/adapters.safetensors \
  --save-path ./qwen35_grpo_merged
```

### 2. Quantize to 4-bit for deployment

```bash
python -m mlx_lm.convert \
  --hf-path ./qwen35_grpo_merged \
  -q \
  --output-file ./qwen35_grpo_4bit
```

### 3. Deploy back on M2 Pro

Copy `./qwen35_grpo_4bit/` to the M2 Pro, then:

```bash
mlx_vlm.server --host 0.0.0.0 --port 8080 \
  --model ./qwen35_grpo_4bit \
  --enable-thinking \
  --thinking-budget 2048 \
  --thinking-start-token "<think>" \
  --thinking-end-token "</think>"
```

## Memory Safety

Keep total under ~35GB to avoid macOS disk swap:

```
Safe:       batch_size=2, num_generations=4, max_tokens=256  (~13GB)
Aggressive: batch_size=4, num_generations=8, max_tokens=256  (~20GB)
Too much:   batch_size=8, num_generations=16, max_tokens=512 (~35GB+, will swap)
```

Monitor during training: `top -l 1 | grep PhysMem`

## Gotchas

- **KV cache explosion**: Each generation stores its own KV cache. More generations = more memory.
- **Tokenizer mismatch**: Always use the official Qwen tokenizer, not custom ones.
- **Partial verifiers**: If your reward function misses edge cases, the model will exploit them. Test on 100+ samples first.
- **Entropy collapse**: Model can overfit to training distribution. Use diverse prompts.

## References

- [MLX-GRPO](https://github.com/Doriandarko/MLX-GRPO)
- [mlx-tune](https://github.com/ARahim3/mlx-tune)
- [mlx-lm LoRA docs](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
- [Absolute Zero paper](https://arxiv.org/abs/2505.03335) (inspiration, not runnable on Apple Silicon)
- [GRPO explained](https://cameronrwolfe.substack.com/p/grpo)
- [Unsloth GRPO guide](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/)
