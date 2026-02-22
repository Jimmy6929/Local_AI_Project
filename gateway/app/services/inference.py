"""
Inference service for calling LLM endpoints.
Supports OpenAI-compatible APIs (vLLM, TGI, Ollama, etc.)
with streaming, health checks, and fallback to mock.
"""

from typing import Optional, List, Dict, Any, AsyncIterator
import json
import httpx

from app.config import Settings, get_settings


class InferenceService:
    """Service for LLM inference calls via OpenAI-compatible API."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.instant_url = settings.inference_instant_url
        self.thinking_url = settings.inference_thinking_url
        self.model_name = settings.inference_model_name
        self.default_max_tokens = settings.inference_max_tokens
        self.default_temperature = settings.inference_temperature
        self.timeout = settings.inference_timeout
    
    def _get_endpoint(self, mode: str) -> Optional[str]:
        """Get the inference endpoint URL for the given mode."""
        if mode == "thinking":
            return self.thinking_url or None
        return self.instant_url or None
    
    # ==================== Health Check ====================
    
    async def check_health(self, mode: str = "instant") -> Dict[str, Any]:
        """
        Check if the inference endpoint is healthy.
        Returns status info about the endpoint.
        """
        endpoint = self._get_endpoint(mode)
        if not endpoint:
            return {
                "status": "not_configured",
                "mode": mode,
                "url": None,
                "message": f"No {mode} inference endpoint configured. Using mock responses.",
            }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try /health first (vLLM), then /v1/models (OpenAI standard)
                for path in ["/health", "/v1/models"]:
                    try:
                        response = await client.get(f"{endpoint}{path}")
                        if response.status_code == 200:
                            return {
                                "status": "healthy",
                                "mode": mode,
                                "url": endpoint,
                                "endpoint_checked": path,
                                "model": self.model_name,
                            }
                    except Exception:
                        continue
                
                return {
                    "status": "unhealthy",
                    "mode": mode,
                    "url": endpoint,
                    "message": "Endpoint reachable but no health endpoint responded",
                }
        except httpx.ConnectError:
            return {
                "status": "unreachable",
                "mode": mode,
                "url": endpoint,
                "message": f"Cannot connect to {endpoint}. Is the GPU pod running?",
            }
        except Exception as e:
            return {
                "status": "error",
                "mode": mode,
                "url": endpoint,
                "message": str(e),
            }
    
    # ==================== Non-Streaming ====================
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        mode: str = "instant",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete response from the LLM.
        
        Args:
            messages: Conversation history with 'role' and 'content'
            mode: 'instant' or 'thinking'
            max_tokens: Override default max tokens
            temperature: Override default temperature
            
        Returns:
            Dict with 'content', 'tokens_used', 'mode_used'
        """
        endpoint = self._get_endpoint(mode)
        
        if not endpoint:
            return await self._mock_response(messages, mode)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{endpoint}/v1/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "max_tokens": max_tokens or self.default_max_tokens,
                        "temperature": temperature if temperature is not None else self.default_temperature,
                        "stream": False,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                
                choice = data["choices"][0]
                usage = data.get("usage", {})
                
                return {
                    "content": choice["message"]["content"],
                    "tokens_used": usage.get("total_tokens"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "mode_used": mode,
                    "model": data.get("model", self.model_name),
                    "finish_reason": choice.get("finish_reason"),
                }
        except httpx.ConnectError:
            print(f"[inference] Cannot connect to {endpoint} — using mock")
            return await self._mock_response(messages, mode)
        except httpx.TimeoutException:
            print(f"[inference] Timeout calling {endpoint} — using mock")
            return await self._mock_response(messages, mode)
        except Exception as e:
            print(f"[inference] Error: {e} — using mock")
            return await self._mock_response(messages, mode)
    
    # ==================== Streaming ====================
    
    async def generate_response_stream(
        self,
        messages: List[Dict[str, str]],
        mode: str = "instant",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response from the LLM (SSE format).
        
        Yields:
            Server-sent event strings in OpenAI format
        """
        endpoint = self._get_endpoint(mode)
        
        if not endpoint:
            # Stream mock response word by word
            mock = await self._mock_response(messages, mode)
            words = mock["content"].split()
            for i, word in enumerate(words):
                chunk = {
                    "choices": [{
                        "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                        "index": 0,
                        "finish_reason": None if i < len(words) - 1 else "stop",
                    }],
                    "model": "mock",
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{endpoint}/v1/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "max_tokens": max_tokens or self.default_max_tokens,
                        "temperature": temperature if temperature is not None else self.default_temperature,
                        "stream": True,
                    },
                    headers={"Content-Type": "application/json"},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.strip():
                            yield f"{line}\n\n"
        except Exception as e:
            print(f"[inference] Stream error: {e} — using mock")
            mock = await self._mock_response(messages, mode)
            chunk = {
                "choices": [{
                    "delta": {"content": mock["content"]},
                    "index": 0,
                    "finish_reason": "stop",
                }],
                "model": "mock",
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
    
    # ==================== Mock ====================
    
    async def _mock_response(
        self,
        messages: List[Dict[str, str]],
        mode: str
    ) -> Dict[str, Any]:
        """Generate a mock response for testing when no endpoint is configured."""
        last_message = messages[-1]["content"] if messages else ""
        
        if "hello" in last_message.lower() or "hi" in last_message.lower():
            content = "Hello! I'm your AI assistant. How can I help you today?"
        elif "2+2" in last_message or "2 + 2" in last_message:
            content = "2 + 2 equals 4."
        elif "?" in last_message:
            content = (
                f"That's a great question! I'm currently running in **mock mode** "
                f"({mode}). Once the inference endpoints are configured, I'll be "
                f"able to provide real AI-powered responses.\n\n"
                f"To connect a real model, set `INFERENCE_INSTANT_URL` in your `.env` "
                f"file to point to your GPU pod running vLLM, TGI, or Ollama."
            )
        else:
            content = (
                f"I received your message. I'm currently running in **mock mode** "
                f"({mode}). Configure `INFERENCE_INSTANT_URL` in your `.env` to "
                f"connect a real model server."
            )
        
        return {
            "content": content,
            "tokens_used": len(content.split()) * 2,
            "prompt_tokens": sum(len(m["content"].split()) for m in messages),
            "completion_tokens": len(content.split()),
            "mode_used": mode,
            "model": "mock",
            "finish_reason": "stop",
        }


# Singleton instance
_inference_service: Optional[InferenceService] = None


def get_inference_service() -> InferenceService:
    """Get inference service instance."""
    global _inference_service
    if _inference_service is None:
        _inference_service = InferenceService(get_settings())
    return _inference_service
