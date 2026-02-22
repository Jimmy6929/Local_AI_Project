# GPU Pod Setup Guide — Instant Inference

This guide walks through provisioning a GPU pod and setting up a model
server that exposes an **OpenAI-compatible** `/v1/chat/completions` endpoint.

The Gateway is already wired to call this endpoint. Once you start the
server and set `INFERENCE_INSTANT_URL` in your `.env`, everything works.

---

## 1. Choose a Provider

| Provider | GPU Options | Pricing | Notes |
|----------|------------|---------|-------|
| **RunPod** | A100, A40, RTX 4090 | ~$0.40-$2.50/hr | Serverless or on-demand pods |
| **Lambda Labs** | A100, H100 | ~$1.10-$3.00/hr | Cloud instances |
| **Vast.ai** | Consumer & datacenter | ~$0.20-$1.50/hr | Marketplace, variable |
| **Local** | Your own GPU | Free | Requires 16GB+ VRAM |

**Minimum VRAM**: 16GB (for quantized 7B models) — 24GB+ recommended.

---

## 2. Option A: vLLM (Recommended for Production)

vLLM is the fastest inference server with PagedAttention, continuous
batching, and native OpenAI-compatible API.

### Install & Run

```bash
# SSH into your GPU pod
ssh user@<gpu-pod-ip>

# Install vLLM (requires Python 3.9+, CUDA 11.8+)
pip install vllm

# Run with a 7B instruct model
python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --dtype auto

# Verify it's working
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
```

### Gateway config

```env
INFERENCE_INSTANT_URL=http://<gpu-pod-ip>:8000
INFERENCE_MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3
```

### Run as a Service (systemd)

```bash
sudo tee /etc/systemd/system/vllm.service > /dev/null <<'EOF'
[Unit]
Description=vLLM Inference Server
After=network.target

[Service]
User=root
WorkingDirectory=/root
ExecStart=/usr/local/bin/python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --host 0.0.0.0 --port 8000 \
    --max-model-len 8192 --gpu-memory-utilization 0.90 --dtype auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now vllm
sudo systemctl status vllm
```

---

## 3. Option B: Ollama (Easiest for Local / Quick Setup)

Ollama is the simplest way to run models. Great for local development.

### Install & Run

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull mistral:7b-instruct

# Serve (runs on port 11434 by default)
ollama serve &

# Verify
curl http://localhost:11434/v1/models
```

### Gateway config

```env
INFERENCE_INSTANT_URL=http://localhost:11434
INFERENCE_MODEL_NAME=mistral:7b-instruct
```

> **Note**: Ollama supports the OpenAI-compatible `/v1/chat/completions`
> endpoint natively since v0.1.14+.

---

## 4. Option C: Text Generation Inference (TGI)

Hugging Face's TGI — good Docker-based option.

```bash
docker run --gpus all -p 8080:80 \
    -v /data:/data \
    ghcr.io/huggingface/text-generation-inference:latest \
    --model-id mistralai/Mistral-7B-Instruct-v0.3 \
    --max-input-length 4096 \
    --max-total-tokens 8192

# Gateway config:
# INFERENCE_INSTANT_URL=http://<gpu-pod-ip>:8080
```

> **Note**: TGI uses a slightly different API format. The Gateway's
> OpenAI-compatible client works with TGI's `/v1/chat/completions`.

---

## 5. Networking & Security

The inference endpoint should **not** be on the public internet.

### Option A: Tailscale (Recommended)

```bash
# On GPU pod
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey=<your-tailscale-key>

# Note the Tailscale IP (e.g., 100.x.y.z)
tailscale ip -4

# On your dev machine (Gateway)
# Use the Tailscale IP:
# INFERENCE_INSTANT_URL=http://100.x.y.z:8000
```

### Option B: SSH Tunnel (Quick & Dirty)

```bash
# From your dev machine
ssh -L 8000:localhost:8000 user@<gpu-pod-ip>

# Gateway connects to localhost:
# INFERENCE_INSTANT_URL=http://localhost:8000
```

### Option C: Firewall Rules

```bash
# On GPU pod — allow only your IP
sudo ufw default deny incoming
sudo ufw allow from <your-ip> to any port 8000
sudo ufw enable
```

---

## 6. Verify End-to-End

Once your GPU pod is running, update `.env` and restart the Gateway:

```bash
# 1. Edit .env
cd /Users/pong/projects/assistant-staging/gateway
# Set INFERENCE_INSTANT_URL and INFERENCE_MODEL_NAME

# 2. Restart Gateway
# (kill the old process, then)
cd /Users/pong/projects/assistant-staging/gateway
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Check inference health
curl http://localhost:8000/health/inference | python -m json.tool

# 4. Test a real chat (get a token first)
TOKEN=$(curl -s -X POST 'http://127.0.0.1:54321/auth/v1/token?grant_type=password' \
  -H 'apikey: sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"testpassword123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?", "mode": "instant"}'

# 5. Test streaming
curl -N http://localhost:8000/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a joke", "mode": "instant"}'
```

---

## 7. Recommended Models

| Model | VRAM | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `mistralai/Mistral-7B-Instruct-v0.3` | 16GB | ⚡ Fast | Good | General |
| `meta-llama/Llama-3.1-8B-Instruct` | 16GB | ⚡ Fast | Good | General |
| `Qwen/Qwen2.5-7B-Instruct` | 16GB | ⚡ Fast | Good | General + Code |
| `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct` | 16GB | ⚡ Fast | Good | Code-focused |
| `mistralai/Mixtral-8x7B-Instruct-v0.1` | 48GB | Medium | Great | Complex tasks |

> **Tip**: Start with Mistral-7B-Instruct or Llama-3.1-8B-Instruct.
> They're fast, high quality, and fit on a single GPU.
