"""
Database service for Supabase interactions via direct REST API.
"""

from typing import Optional, List, Dict, Any
from functools import lru_cache
import httpx

from app.config import Settings, get_settings


class DatabaseService:
    """Service for database operations via Supabase REST API."""
    
    def __init__(self, settings: Settings):
        self.base_url = f"{settings.supabase_url}/rest/v1"
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make a synchronous HTTP request to Supabase REST API."""
        url = f"{self.base_url}/{endpoint}"
        headers = {**self.headers, **kwargs.pop("headers", {})}
        
        with httpx.Client() as client:
            response = client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json() if response.text else None
    
    # ==================== Sessions ====================
    
    def create_session(self, user_id: str, title: str = "New Chat") -> Dict[str, Any]:
        """Create a new chat session."""
        result = self._request("POST", "chat_sessions", json={
            "user_id": user_id,
            "title": title,
        })
        return result[0] if result else None
    
    def get_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID (only if owned by user)."""
        result = self._request(
            "GET",
            f"chat_sessions?id=eq.{session_id}&user_id=eq.{user_id}&select=*"
        )
        return result[0] if result else None
    
    def list_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List user's chat sessions, newest first."""
        result = self._request(
            "GET",
            f"chat_sessions?user_id=eq.{user_id}&is_archived=eq.false&order=updated_at.desc&limit={limit}"
        )
        return result or []
    
    def update_session_title(self, session_id: str, user_id: str, title: str) -> bool:
        """Update session title."""
        result = self._request(
            "PATCH",
            f"chat_sessions?id=eq.{session_id}&user_id=eq.{user_id}",
            json={"title": title}
        )
        return bool(result)
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session (cascades to messages)."""
        self._request(
            "DELETE",
            f"chat_sessions?id=eq.{session_id}&user_id=eq.{user_id}"
        )
        return True
    
    # ==================== Messages ====================
    
    def create_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        mode_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new chat message."""
        data = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        }
        if mode_used:
            data["mode_used"] = mode_used
        if tokens_used:
            data["tokens_used"] = tokens_used
            
        result = self._request("POST", "chat_messages", json=data)
        return result[0] if result else None
    
    def get_session_messages(
        self,
        session_id: str,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get messages for a session, oldest first."""
        result = self._request(
            "GET",
            f"chat_messages?session_id=eq.{session_id}&user_id=eq.{user_id}&order=created_at.asc&limit={limit}"
        )
        return result or []
    
    # ==================== User Profile ====================
    
    def get_or_create_profile(self, user_id: str, email: Optional[str] = None) -> Dict[str, Any]:
        """Get user profile, creating if needed."""
        # Try to get existing profile
        result = self._request("GET", f"profiles?id=eq.{user_id}&select=*")
        if result:
            return result[0]
        
        # Profile should be auto-created by trigger, but fallback just in case
        if email:
            result = self._request("POST", "profiles", json={
                "id": user_id,
                "email": email,
            })
            return result[0] if result else None
        
        return None


@lru_cache
def get_database_service() -> DatabaseService:
    """Get cached database service instance."""
    return DatabaseService(get_settings())
