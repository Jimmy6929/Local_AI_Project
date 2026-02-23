# GPU Pod Setup Guide — Thinking Inference (Step 2.1)

This guide walks through deploying a **Thinking tier** endpoint — a
stronger model for complex reasoning, deployed on serverless GPU
infrastructure that scales to zero when idle.

The Gateway treats both tiers identically: same OpenAI-compatible
`/v1/chat/completions` API, same model-agnostic approach. The only
differences are the model loaded, token limits, and timeout values.

> **Prerequisite**: You should already have the Instant tier working
> (see `GPU_SETUP_GUIDE.md`). The Thinking tier is independent but
> shares the same Gateway routing.

---

## 1. Understanding the Two-Tier Architecture

| Aspect | Instant | Thinking |
|--------|---------|----------|
| **Purpose** | Fast daily tasks | Complex reasoning |
| **Models** | 7B-13B params | 30B-72B params |
| **Latency** | <2s first token | 10-30s cold start OK |
| **Infra** | Always-on GPU pod | Serverless, scale-to-zero |
| **Cost** | Fixed hourly rate | Pay per request |
| **Timeout** | 120s | 300s (5 min) |
| **Max tokens** | 2048 | 4096 |
| **Temperature** | 0.7 | 0.5 (more focused) |

Both tiers use the **same** `/v1/chat/completions` endpoint format.
Any open-source model works with either tier.

---

## 2. Choose a Serverless GPU Platform

| Platform | Scale-to-Zero | Cold Start | GPU Options | Pricing |
|----------|:------------:|:----------:|-------------|---------|
| **RunPod Serverless** | ✅ | ~15-30s | A100, A40, L40S | ~$0.0002/s |
| **Modal** | ✅ | ~10-20s | A100, A10G, H100 | ~$0.001/s |
| **Replicate** | ✅ | ~10-30s | A100, A40 | ~$0.0023/s |
| **Banana** | ✅ | ~15-30s | A100 | ~$0.002/s |
| **Together.ai** | ✅ | ~5-10s | Various | Per-token pricing |
| **Vast.ai** | ❌ (on-demand) | N/A | Various | ~$0.20-$1.50/hr |

**Recommendation**: RunPod Serverless or Modal for self-hosted models.
Together.ai if you prefer a managed API (still OpenAI-compatible).

---

## 3. Recommended Thinking Models (All Open Source)

All models below use permissive licenses and expose an OpenAI-compatible
API through vLLM, TGI, or the platform's built-in serving.

### Tier 1: Best Quality (70B+ class)

| Model | VRAM | Quality | Speed | License | Best For |
|-------|------|---------|-------|---------|----------|
| `meta-llama/Llama-3.1-70B-Instruct` | 40GB (AWQ) | ⭐⭐⭐⭐⭐ | Slow | Llama 3.1 | General reasoning |
| `Qwen/Qwen2.5-72B-Instruct` | 40GB (AWQ) | ⭐⭐⭐⭐⭐ | Slow | Apache 2.0 | General + Code |
| `deepseek-ai/DeepSeek-V2.5` | 40GB+ | ⭐⭐⭐⭐⭐ | Slow | DeepSeek | Code + Analysis |
| `mistralai/Mixtral-8x22B-Instruct-v0.1` | 48GB | ⭐⭐⭐⭐ | Medium | Apache 2.0 | MoE efficiency |

### Tier 2: Good Balance (30B-40B class)

| Model | VRAM | Quality | Speed | License | Best For |
|-------|------|---------|-------|---------|----------|
| `Qwen/Qwen2.5-32B-Instruct` | 20GB (AWQ) | ⭐⭐⭐⭐ | Medium | Apache 2.0 | General + Code |
| `deepseek-ai/DeepSeek-Coder-V2-Instruct` | 20GB+ | ⭐⭐⭐⭐ | Medium | DeepSeek | Code-focused |
| `meta-llama/Llama-3.3-70B-Instruct` | 40GB (AWQ) | ⭐⭐⭐⭐⭐ | Slow | Llama 3.3 | Latest Llama |
| `mistralai/Mistral-Small-24B-Instruct-2501` | 16GB (AWQ) | ⭐⭐⭐⭐ | Fast | Apache 2.0 | Efficient reasoning |

### Tier 3: Quantized 70B (fits smaller VRAM)

| Model | VRAM | Quality | Speed | Notes |
|-------|------|---------|-------|-------|
| `Llama-3.1-70B-Instruct-AWQ` | ~38GB | ⭐⭐⭐⭐ | Medium | 4-bit quantized |
| `Qwen2.5-72B-Instruct-GPTQ-Int4` | ~38GB | ⭐⭐⭐⭐ | Medium | 4-bit quantized |
| `Llama-3.1-70B-Instruct-GGUF Q4_K_M` | ~40GB | ⭐⭐⭐⭐ | Medium | GGUF format for llama.cpp |

> **Tip**: Start with `Qwen/Qwen2.5-72B-Instruct` or `Llama-3.1-70B-Instruct`.
> Both are top-quality, well-supported, and compatible with all serving frameworks.

---

## 4. Option A: RunPod Serverless (Recommended)

### 4.1 Create a Serverless Endpoint

1. Go to [runpod.io](https://runpod.io) → Serverless
2. Create new endpoint:
   - **Container Image**: `runpod/worker-vllm:stable` (built-in vLLM)
   - **Model**: `Qwen/Qwen2.5-72B-Instruct-AWQ`
   - **GPU**: A100 80GB (or 2x A40 for tensor parallel)
   - **Max Workers**: 2
   - **Min Workers**: 0 (scale-to-zero)
   - **Idle Timeout**: 5 minutes

### 4.2 RunPod vLLM Worker Config

```json
{
  "model": "Qwen/Qwen2.5-72B-Instruct-AWQ",
  "max_model_len": 8192,
  "gpu_memory_utilization": 0.90,
  "dtype": "auto",
  "quantization": "awq",
  "enforce_eager": false
}
```

### 4.3 Gateway Config

```env
# Thinking tier — RunPod Serverless
INFERENCE_THINKING_URL=https://<endpoint-id>-runpod.a]].runpod.net
INFERENCE_THINKING_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ
INFERENCE_THINKING_MAX_TOKENS=4096
INFERENCE_THINKING_TEMPERATURE=0.5
INFERENCE_THINKING_TIMEOUT=300
```

> RunPod Serverless exposes an OpenAI-compatible `/v1/chat/completions`
> endpoint automatically when using the vLLM worker.

---

## 5. Option B: Modal

### 5.1 Deploy with Modal

```python
# modal_thinking.py
import modal

app = modal.App("thinking-inference")

vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm>=0.6.0", "torch", "transformers")
)

@app.cls(
    gpu=modal.gpu.A100(count=1, size="80GB"),
    image=vllm_image,
    container_idle_timeout=300,  # Scale to zero after 5 min
    timeout=600,
)
class ThinkingModel:
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        self.llm = LLM(
            model="Qwen/Qwen2.5-72B-Instruct-AWQ",
            quantization="awq",
            max_model_len=8192,
            gpu_memory_utilization=0.90,
        )

    @modal.web_endpoint(method="POST")
    def chat_completions(self, request: dict):
        # OpenAI-compatible endpoint
        from vllm import SamplingParams
        messages = request.get("messages", [])
        params = SamplingParams(
            max_tokens=request.get("max_tokens", 4096),
            temperature=request.get("temperature", 0.5),
        )
        # ... generate and return OpenAI-format response
```

```bash
# Deploy
modal deploy modal_thinking.py

# Test
curl https://<your-modal-app>.modal.run/chat_completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"Explain recursion"}]}'
```

### 5.2 Gateway Config

```env
INFERENCE_THINKING_URL=https://<your-modal-app>.modal.run
INFERENCE_THINKING_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ
```

---

## 6. Option C: Self-Hosted vLLM on GPU Pod

If you already have a GPU pod with enough VRAM (80GB+ for 70B models),
you can run vLLM directly — same setup as Instant but with a bigger model.

### 6.1 Install & Run

```bash
# SSH into your GPU pod
ssh user@<gpu-pod-ip>

# Install vLLM
pip install vllm

# Run a 72B model (quantized to fit in 80GB)
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct-AWQ \
    --host 0.0.0.0 \
    --port 8001 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --quantization awq \
    --dtype auto

# Verify
curl http://localhost:8001/health
curl http://localhost:8001/v1/models
```

> **Note**: Use port 8001 so it doesn't conflict with Instant on 8000.

### 6.2 Gateway Config

```env
INFERENCE_THINKING_URL=http://<gpu-pod-ip>:8001
INFERENCE_THINKING_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ
```

### 6.3 Run as Service (systemd)

```bash
sudo tee /etc/systemd/system/vllm-thinking.service > /dev/null <<'EOF'
[Unit]
Description=vLLM Thinking Inference Server
After=network.target

[Service]
User=root
WorkingDirectory=/root
ExecStart=/usr/local/bin/python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-72B-Instruct-AWQ \
    --host 0.0.0.0 --port 8001 \
    --max-model-len 8192 --gpu-memory-utilization 0.90 \
    --quantization awq --dtype auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now vllm-thinking
sudo systemctl status vllm-thinking
```

---

## 7. Option D: Ollama (Local / Quick Testing)

Good for testing the thinking pipeline locally before deploying to cloud.

```bash
# Pull a larger model
ollama pull qwen2.5:32b
# or for code-heavy reasoning:
ollama pull deepseek-coder-v2:16b

# Serve on a different port to avoid conflict with instant
OLLAMA_HOST=0.0.0.0:11435 ollama serve &

# Verify
curl http://localhost:11435/v1/models
```

### Gateway Config

```env
INFERENCE_THINKING_URL=http://localhost:11435
INFERENCE_THINKING_MODEL=qwen2.5:32b
```

---

## 8. Option E: llama.cpp Server

Works with GGUF models, great for CPU+GPU hybrid or lower VRAM setups.

```bash
# Build llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && make -j

# Download a GGUF model
# (e.g., from HuggingFace — search for "70B GGUF Q4_K_M")

# Run the server (OpenAI-compatible mode)
./llama-server \
    -m /path/to/model.gguf \
    --host 0.0.0.0 \
    --port 8001 \
    -ngl 99 \
    -c 8192 \
    --api-key "" \
    -t 8

# Verify
curl http://localhost:8001/v1/models
```

### Gateway Config

```env
INFERENCE_THINKING_URL=http://localhost:8001
INFERENCE_THINKING_MODEL=llama-70b-q4
```

---

## 9. Model Compatibility Matrix

The Gateway is **model-agnostic**. Any model served via an OpenAI-compatible
`/v1/chat/completions` endpoint works for either tier. Here's what's
been tested:

| Serving Framework | Instant Models | Thinking Models | Streaming | Notes |
|-------------------|:-------------:|:--------------:|:---------:|-------|
| **vLLM** | ✅ | ✅ | ✅ | Recommended for production |
| **Ollama** | ✅ | ✅ | ✅ | Easiest local setup |
| **TGI** | ✅ | ✅ | ✅ | Good Docker option |
| **llama.cpp** | ✅ | ✅ | ✅ | GGUF models, CPU+GPU |
| **SGLang** | ✅ | ✅ | ✅ | Fast, supports TP |
| **Together.ai** | ✅ | ✅ | ✅ | Managed API |
| **OpenRouter** | ✅ | ✅ | ✅ | Multi-model proxy |

### Mix and Match

You can use **different frameworks** for each tier. For example:

```env
# Instant: Ollama locally with a 7B model
INFERENCE_INSTANT_URL=http://localhost:11434
INFERENCE_INSTANT_MODEL=mistral:7b-instruct

# Thinking: RunPod Serverless with a 72B model
INFERENCE_THINKING_URL=https://api-xxxxx.runpod.net
INFERENCE_THINKING_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ
```

Or use the same framework with different models:

```env
# Both on vLLM, different pods
INFERENCE_INSTANT_URL=http://100.64.1.10:8000
INFERENCE_INSTANT_MODEL=mistralai/Mistral-7B-Instruct-v0.3

INFERENCE_THINKING_URL=http://100.64.1.11:8001
INFERENCE_THINKING_MODEL=meta-llama/Llama-3.1-70B-Instruct
```

---

## 10. Cost Controls

### Scale-to-Zero Verification

After deploying, verify your endpoint actually scales to zero:

```bash
# 1. Make a request to warm up
curl $INFERENCE_THINKING_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"test","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'

# 2. Wait for idle timeout (e.g., 5 minutes)
sleep 300

# 3. Check — should get connection refused or slow cold start
time curl $INFERENCE_THINKING_URL/health
```

### Gateway Cost Defaults

These are configured in your `.env`:

```env
# Max thinking requests per user per day
THINKING_DAILY_REQUEST_LIMIT=100

# Max concurrent thinking requests (controls GPU cost)
THINKING_MAX_CONCURRENT=2

# Cold start timeout — how long to wait for serverless pod
ROUTING_COLD_START_TIMEOUT=60
```

### Per-Request Token Caps

| Setting | Instant | Thinking |
|---------|---------|----------|
| `max_tokens` | 2048 | 4096 |
| `timeout` | 120s | 300s |
| `temperature` | 0.7 | 0.5 |

---

## 11. Networking & Security

Same as Instant tier — the thinking endpoint should **not** be public.

### Tailscale (Recommended)

```bash
# On thinking GPU pod
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey=<your-tailscale-key>
tailscale ip -4
# e.g., 100.64.2.20

# Gateway .env
INFERENCE_THINKING_URL=http://100.64.2.20:8001
```

### For Serverless (RunPod, Modal)

These platforms provide HTTPS endpoints with optional API keys.
The Gateway connects over HTTPS — no VPN needed.

---

## 12. Verify End-to-End

```bash
# 1. Check inference health (both tiers)
curl http://localhost:8000/health/inference | python3 -m json.tool

# 2. Test thinking mode (get a token first)
TOKEN=$(curl -s -X POST 'http://127.0.0.1:54321/auth/v1/token?grant_type=password' \
  -H 'apikey: <your-anon-key>' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"testpassword123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. Send a thinking-mode request
curl http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze the time complexity of merge sort and explain why it is O(n log n)",
    "mode": "thinking"
  }' | python3 -m json.tool

# 4. Check the response includes inference metadata
# Look for: mode_used, model, fallback_used, latency_ms

# 5. Test fallback — stop thinking endpoint, send thinking request
# Should fall back to instant with fallback_used: true
```

---

## 13. Fallback Behavior

The Gateway automatically handles failures:

| Scenario | Behavior |
|----------|----------|
| Thinking endpoint not configured | Falls back to Instant |
| Thinking endpoint unreachable | Falls back to Instant |
| Thinking request times out | Falls back to Instant |
| Thinking HTTP error | Falls back to Instant |
| Both endpoints down | Returns mock response |
| Fallback disabled | Returns mock response |

To disable fallback:

```env
ROUTING_THINKING_FALLBACK_TO_INSTANT=false
```

---

## Quick Reference

### Start both tiers locally (Ollama example)

```bash
# Terminal 1: Instant (default port 11434)
ollama serve

# Terminal 2: Thinking (port 11435)
OLLAMA_HOST=0.0.0.0:11435 ollama serve

# Pull models
ollama pull mistral:7b-instruct
OLLAMA_HOST=localhost:11435 ollama pull qwen2.5:32b
```

### Gateway .env for local dual-tier

```env
# Instant
INFERENCE_INSTANT_URL=http://localhost:11434
INFERENCE_INSTANT_MODEL=mistral:7b-instruct

# Thinking
INFERENCE_THINKING_URL=http://localhost:11435
INFERENCE_THINKING_MODEL=qwen2.5:32b

# Routing
ROUTING_THINKING_FALLBACK_TO_INSTANT=true
ROUTING_COLD_START_TIMEOUT=60
```
