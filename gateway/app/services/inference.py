"""
Inference service for calling LLM endpoints.
Currently uses mock responses; will be updated when GPU pods are configured.
"""

from typing import Optional, List, Dict, Any
import httpx

from app.config import Settings, get_settings


class InferenceService:
    """Service for LLM inference calls."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.instant_url = settings.inference_instant_url
        self.thinking_url = settings.inference_thinking_url
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        mode: str = "instant",
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            mode: 'instant' or 'thinking'
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Dict with 'content', 'tokens_used', 'mode_used'
        """
        # Select endpoint based on mode
        endpoint_url = self.thinking_url if mode == "thinking" else self.instant_url
        
        # If no endpoint configured, use mock response
        if not endpoint_url:
            return await self._mock_response(messages, mode)
        
        # Call real inference endpoint (OpenAI-compatible API)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{endpoint_url}/v1/chat/completions",
                    json={
                        "model": "default",
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "tokens_used": data.get("usage", {}).get("total_tokens"),
                    "mode_used": mode,
                }
        except Exception as e:
            # Fallback to mock on error
            print(f"Inference error: {e}, falling back to mock")
            return await self._mock_response(messages, mode)
    
    async def _mock_response(
        self,
        messages: List[Dict[str, str]],
        mode: str
    ) -> Dict[str, Any]:
        """Generate a mock response for testing."""
        last_message = messages[-1]["content"] if messages else ""
        
        # Simple mock responses
        if "hello" in last_message.lower():
            content = "Hello! I'm your AI assistant. How can I help you today?"
        elif "2+2" in last_message or "2 + 2" in last_message:
            content = "2 + 2 equals 4."
        elif "?" in last_message:
            content = f"That's a great question! I'm currently running in mock mode ({mode}). Once the inference endpoints are configured, I'll be able to provide real AI-powered responses."
        else:
            content = f"I received your message: \"{last_message[:100]}{'...' if len(last_message) > 100 else ''}\"\n\nI'm currently running in mock mode ({mode}). Configure the inference endpoints to enable real AI responses."
        
        return {
            "content": content,
            "tokens_used": len(content.split()) * 2,  # Rough estimate
            "mode_used": mode,
        }


# Singleton instance
_inference_service: Optional[InferenceService] = None


def get_inference_service() -> InferenceService:
    """Get inference service instance."""
    global _inference_service
    if _inference_service is None:
        _inference_service = InferenceService(get_settings())
    return _inference_service
